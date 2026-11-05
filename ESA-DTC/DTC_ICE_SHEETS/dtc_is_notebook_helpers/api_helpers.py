"""Helper functions for interacting with the DTC Query API for mass balance and sea-level response computations."""

import io
import json
import os
import time
from datetime import datetime

import requests
import tenacity
import xarray as xr
from shapely.geometry import MultiPolygon, Polygon, mapping

DTC_QUERY_API_URL = "https://query.dtc-ice-sheets.org"

WORKFLOW_API_TIMEOUT = 600  # seconds
GENERAL_API_TIMEOUT = 10  # seconds


def get_auth_headers() -> dict:
    """Get authentication headers for DTC Query API requests."""
    return {"Authorization": f"Bearer {os.environ['DTC_API_TOKEN']}"}


def upload_mass_balance_csv(file_upload_value: dict) -> str:
    """
    Upload a custom mass balance CSV file to the DTC Query API and return the dataset URL.

    Parameters
    ----------
    file_upload_value : dict
        The value from the file upload widget containing the CSV file. This should contain, at minimum, the key
        "content" with the binary content of the file and optionally "name" for the filename.

    Returns
    -------
    str
        The URL of the uploaded dataset.

    Raises
    ------
    ValueError
        If the file upload value is not a valid type.
    """
    if "content" not in file_upload_value:
        raise ValueError("file_upload_value must contain 'content' key with file data")
    files = {
        "file": (file_upload_value.get("name", "custom_data.csv"), io.BytesIO(file_upload_value["content"]), "text/csv")
    }
    response = requests.post(
        f"{DTC_QUERY_API_URL}/mass-balance/upload-csv",  # adjust URL as needed
        files=files,
        timeout=WORKFLOW_API_TIMEOUT,
        headers=get_auth_headers(),
    )

    response.raise_for_status()

    return response.json()["url"]


@tenacity.retry(
    wait=tenacity.wait_fixed(2),
    stop=tenacity.stop_after_attempt(5),
    retry=tenacity.retry_if_exception_type(requests.exceptions.RequestException),
)
def get_precomputed_mass_balance_dataset_url(dataset: str) -> str:
    """
    Handle loading the selected dataset and returns vmb, time_filtered_vmb, mb_str, and a status message.

    Parameters
    ----------
    dataset : str
        The dataset to load ( "greenland", "antarctic", or "greenland_and_antarctic").

    Returns
    -------
    str
        The URL of the precomputed mass balance dataset.

    Raises
    ------
    ValueError
        If an unknown dataset is specified.
    """
    if dataset not in ["greenland", "antarctic", "greenland_and_antarctic"]:
        raise ValueError(f"Unknown dataset: {dataset}")
    return requests.get(
        f"{DTC_QUERY_API_URL}/mass-balance/{dataset}", timeout=GENERAL_API_TIMEOUT, headers=get_auth_headers()
    ).json()["url"]


def run_selrem_module(
    vmb_url: str,
    scale: float,
    start_year: int,
    end_year: int,
    analysis_mode: str = "global",
) -> xr.Dataset:
    """
    Run the SELREM module to compute and plot sea-level response from mass balance data.

    Parameters
    ----------
    vmb_url : str
        The S3 URL of the volume mass balance dataset.
    scale : float
        The scaling factor to apply to the mass balance data.
    start_year : int
        The start year for the analysis period.
    end_year : int
        The end year for the analysis period.
    analysis_mode : str, optional
        The analysis mode to use, should be either "global" or "annual", by default "global"

    Returns
    -------
    xr.Dataset
        The xarray dataset containing the sea-level response data.

    Raises
    ------
    RuntimeError
        If the SELREM job fails or is cancelled.
    """
    start_time = datetime(start_year, 1, 1)
    end_time = datetime(end_year, 12, 31)
    """Run the SELREM module to compute and plot sea-level response from mass balance data."""
    resp = requests.post(
        f"{DTC_QUERY_API_URL}/sea-level-response",
        headers=get_auth_headers(),
        data=json.dumps(
            {
                "mass_balance_url": vmb_url,
                "scaling_factor": scale,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "analysis_mode": analysis_mode,
            }
        ),
        timeout=WORKFLOW_API_TIMEOUT,
    )
    resp.raise_for_status()
    job_id = resp.json()["job_id"]
    job_output = _poll_for_job_completion(job_id)
    slr_url = job_output["outputs"]["main"]["output_path"]
    ds = xr.open_dataset(slr_url, engine="zarr")
    return ds


def run_data_download(
    dataset_id: str,
    start_time: datetime,
    end_time: datetime,
    epsg4326_polygon: Polygon | MultiPolygon,
    variables: list[str] | None = None,
) -> str:
    """
    Run data download from the DTC Query API for a specified dataset and time range, optionally filtering by variables.

    Parameters
    ----------
    dataset_id : str
        The ID of the dataset to download.
    start_time : datetime
        The start datetime for the data download.
    end_time : datetime
        The end datetime for the data download.
    epsg4326_polygon : Polygon | MultiPolygon
        Spatial filter polygon in EPSG:4326 (lon/lat) coordinates.
    variables : list[str] | None
        A list of variables to filter the data by, or None to download all variables.

    Returns
    -------
    str
        The public HTTP URL to a GeoZarr containing the downloaded data.

    Raises
    ------
    RuntimeError
        If the data download fails.
    """
    resp = requests.post(
        f"{DTC_QUERY_API_URL}/datasets/download",
        headers=get_auth_headers(),
        data=json.dumps(
            {
                "dataset_id": dataset_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "epsg4326_polygon_json": mapping(epsg4326_polygon),
                "variables": variables,
            }
        ),
        timeout=WORKFLOW_API_TIMEOUT,
    )
    resp.raise_for_status()

    job_id = resp.json()["job_id"]
    job_output = _poll_for_job_completion(job_id)
    result_url = job_output["outputs"]["main"]["output_path"]
    return result_url


def mass_balance_from_thickness(
    thickness_zarr_url: str,
    prep_for_selrem: bool = True,
    coarsen_factor: int = 1,
) -> str:
    """
    Derive mass balance from thickness data using the DTC Query API.

    Parameters
    ----------
    thickness_zarr_url : str
        The URL to the thickness data in GeoZarr format. Should have been retrieved by the `run_data_download` function
        ran for an ISMIP6 dataset.
    prep_for_selrem : bool
        If set to false, the derived mass balance will be returned on the same grid as the input thickness data. If set
        to true, the derived mass balance will be converted to annual timesteps, converted to EPSG:4326 if necesary,
        and flattened to point data with any NaN values removed. This is the format required for input to the SELREM
        module for sea-level response computations.
    coarsen_factor : int
        The factor by which to coarsen the data. Please note this is only applied if `prep_for_selrem` is set to true.

    Returns
    -------
    str
        The public HTTP URL to a GeoZarr containing the derived mass balance data.

    Raises
    ------
    RuntimeError
        If the mass balance derivation job fails or is cancelled.
    """
    resp = requests.post(
        f"{DTC_QUERY_API_URL}/mass-balance/from-thickness",
        headers=get_auth_headers(),
        data=json.dumps(
            {
                "thickness_geozarr_url": thickness_zarr_url,
                "prep_for_selrem": prep_for_selrem,
                "coarsen_factor": coarsen_factor,
            }
        ),
        timeout=WORKFLOW_API_TIMEOUT,
    )
    resp.raise_for_status()
    job_id = resp.json()["job_id"]
    job_output = _poll_for_job_completion(job_id)
    result_url = job_output["outputs"]["main"]["output_path"]
    return result_url


def _poll_for_job_completion(job_id: str) -> dict:
    """Poll the DTC Query API for job completion and return the job result."""
    while True:
        time.sleep(2)
        resp = requests.get(
            f"{DTC_QUERY_API_URL}/jobs/{job_id}", headers=get_auth_headers(), timeout=WORKFLOW_API_TIMEOUT
        )
        resp.raise_for_status()
        res = resp.json()
        if res["status"] in ["Failed", "Error", "Cancelled", "Terminated"]:
            raise RuntimeError(f"Job {job_id} failed or was cancelled")
        if res["status"] == "Succeeded":
            return res
