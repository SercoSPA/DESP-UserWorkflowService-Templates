"""
Helpers for accessing DestinE climate data through the streamer's Zarr proxy API.

Replaces the ffmpeg/video-frame based dtelib_climate.DTEStreamer with a
token-exchange -> Zarr HTTP store -> dask/xarray pipeline: the whole stream is
opened as one lazily-loaded, geo-referenced xarray.DataArray, and callers slice
it with normal xarray indexing instead of iterating frame by frame.
"""

import os

import dask.array as da
import pandas as pd
import requests
import xarray as xr
import zarr
import zarrav1  # noqa: F401  registers the DTE zarr codec on import
from obstore.store import HTTPStore
from zarr.storage import ObjectStore

# Override with e.g. DTE_API_BASE_URL="http://127.0.0.1:8081" to hit a locally
# running dte_api_v2 instead of the prod server (no "/api" prefix locally --
# that's only added by the reverse proxy in front of the real prod host).
API_BASE_URL = os.environ.get("DTE_API_BASE_URL", "https://streamer.destine.eu/api")

ENDPOINT_STREAMING_OVERVIEW = f"{API_BASE_URL}/streaming/data/overview/"
ENDPOINT_LAUNCHCODE = f"{API_BASE_URL}/statonedge/zarr/launch/prefix"
ENDPOINT_ZARR_TOKEN = f"{API_BASE_URL}/statonedge/zarr/auth/launch"
API_ZARR_BASE_URL = f"{API_BASE_URL}/statonedge/zarr/dte-streams-bucket/"


def _auth_headers(token: str) -> dict:
    return {"Accept": "application/json", "Authorization": f"Bearer {token}"}


def _raise_for_status(response: requests.Response, step: str) -> None:
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise requests.exceptions.HTTPError(
            f"{step} failed ({response.status_code}): {response.text}",
            response=response,
        ) from exc


def get_stream_overview(token: str) -> dict:
    """Fetches metadata for all available DTE streams, keyed by program subset."""
    response = requests.get(ENDPOINT_STREAMING_OVERVIEW, headers=_auth_headers(token))
    _raise_for_status(response, "fetching stream overview")
    return response.json()


def stream_overview_table(overview: dict, program_subset: str) -> pd.DataFrame:
    """Case-insensitive lookup of one program subset's entries as a display-friendly table."""
    for subset_name, entries in overview.items():
        if subset_name.lower() == program_subset.lower():
            return pd.DataFrame(entries)
    raise KeyError(f"program subset {program_subset!r} not found")


def _get_launch_code(prefix: str, token: str) -> tuple[str, str]:
    response = requests.post(
        ENDPOINT_LAUNCHCODE,
        headers=_auth_headers(token),
        json={"allowed_prefix": prefix, "dataset_id": prefix},
    )
    _raise_for_status(response, "requesting launch code")
    body = response.json()
    return body["launch_code"], body["allowed_prefix"]


def _get_zarr_token(prefix: str, token: str) -> tuple[str, str]:
    launch_code, allowed_prefix = _get_launch_code(prefix, token)
    response = requests.post(
        ENDPOINT_ZARR_TOKEN,
        headers=_auth_headers(token),
        json={"launch_code": launch_code},
    )
    _raise_for_status(response, "requesting zarr token")
    return response.json()["access_token"], allowed_prefix


def find_variable(overview: dict, program_subset: str, variable: str) -> dict:
    """Case-insensitive lookup of one variable's stream entry in the overview response."""
    for subset_name, entries in overview.items():
        if subset_name.lower() != program_subset.lower():
            continue
        for entry in entries:
            if entry["short_name"] == variable:
                return entry
    raise KeyError(f"{variable!r} not found in program subset {program_subset!r}")


def open_stream(token: str, program_subset: str, variable: str) -> xr.DataArray:
    """
    Opens one variable of a DTE stream as a lazily-loaded, geo-referenced,
    time-indexed xarray.DataArray backed by dask and the streamer's Zarr proxy.

    Longitude is normalized to -180..180 and latitude to north-first (descending)
    so existing lat/lon bounding boxes and polygons keep working unchanged.
    """
    overview = get_stream_overview(token)
    entry = find_variable(overview, program_subset, variable)

    stream_prefix, array_name = entry["stream_file"].split("/", 1)
    zarr_token, allowed_prefix = _get_zarr_token(stream_prefix, token)

    store_url = f"{API_ZARR_BASE_URL}{allowed_prefix}"
    obs_store = HTTPStore.from_url(
        store_url,
        client_options={
            "default_headers": {"Authorization": f"Bearer {zarr_token}"},
            # obstore is https-only by default; only relaxed when store_url itself
            # is plain http (i.e. DTE_API_BASE_URL was overridden for local testing).
            # Reverts itself automatically once DTE_API_BASE_URL points at https again.
            "allow_http": store_url.startswith("http://"),
        },
    )
    zarr_store = ObjectStore(obs_store, read_only=True)

    def open_var(name):
        return zarr.open_array(zarr_store, path=name, mode="r")

    arr = open_var(array_name)
    zarrav1.configure_zarr_array(arr)  # fixes rav1e edge-chunk decoding under Zarr V2
    dims = arr.attrs.get("_ARRAY_DIMENSIONS")
    if dims is None:
        dims = getattr(arr.metadata, "dimension_names", None) or ()
    dims = list(dims)

    time_dim = next(d for d in dims if d not in ("latitude", "longitude"))
    lat = open_var("latitude")[:]
    lon = open_var("longitude")[:]
    start_date = entry["period"].split(" - ")[0]
    time = pd.date_range(start_date, periods=arr.shape[dims.index(time_dim)], freq="h")

    out = xr.DataArray(
        da.from_zarr(arr),
        dims=dims,
        coords={time_dim: time, "latitude": lat, "longitude": lon},
        name=array_name,
        attrs={"units": arr.attrs.get("units", "")},
    ).rename({time_dim: "time"})

    out = out.assign_coords(longitude=(((out.longitude + 180) % 360) - 180)).sortby(
        "longitude"
    )
    if out.latitude[0] < out.latitude[-1]:
        out = out.isel(latitude=slice(None, None, -1))

    return out
