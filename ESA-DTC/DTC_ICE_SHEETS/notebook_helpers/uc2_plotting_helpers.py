"""
uc2_plotting_helpers.py.

Helper functions for processing, analyzing, and visualizing mass balance and sea-level response data
in the Digital Twin of the Cryosphere use case.

This module provides:
- Plotting functions for global and local sea-level response visualizations.
- Interfaces for use in Jupyter notebooks and interactive workflows.

Dependencies: numpy, pandas, xarray, matplotlib, cartopy, scipy, numba

Authors: Tabea Rettelbach, Carsten Ludwigsen, DTU Space
"""

from datetime import datetime

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.gridspec import GridSpec

MASS_BALANCE_COL_NAME = "land_ice_surface_specific_mass_balance_flux"
MASS_BALANCE_ERROR_COL_NAME = "land_ice_surface_specific_mass_balance_flux_uncertainty"


def compute_mean_mass_balance_over_time_window(
    ds: xr.Dataset, start_time: datetime | None = None, end_time: datetime | None = None
) -> xr.Dataset:
    """
    Compute the mean mass balance and associated error over the selected time range, collapsing the time dimension.

    Parameters
    ----------
    ds : xr.Dataset
        Input mass balance dataset with a time dimension.
    start_time : datetime | None, optional
        Start time for slicing, by default None. If both start_time and end_time are provided, the dataset is sliced
        accordingly before computing the mean. Otherwise, the entire time range is used.
    end_time : datetime | None, optional
        End time for slicing, by default None. If both start_time and end_time are provided, the dataset is sliced
        accordingly before computing the mean. Otherwise, the entire time range is used.

    Returns
    -------
    xr.Dataset
        Dataset with the same spatial dimensions ('point', 'x', 'y'), where the 'time' dimension has been removed and
        each variable represents the mean value across the specified years.
    """
    if start_time and end_time:
        ds = ds.sel(time=slice(start_time, end_time))
    return xr.Dataset(
        {
            MASS_BALANCE_COL_NAME: (["point"], ds[MASS_BALANCE_COL_NAME].mean(dim="time", skipna=True).data),
            MASS_BALANCE_ERROR_COL_NAME: (
                ["point"],
                ds[MASS_BALANCE_ERROR_COL_NAME].mean(dim="time", skipna=True).data,
            ),
        },
        coords={
            "y": ds["y"].data,
            "x": ds["x"].data,
            "point": ds["point"].data,
        },
    )


def plot_scaled_mean_mass_balance(
    mean_mb_ds: xr.Dataset,
    dataset_value: str,
    plot_description_str: str,
    scale: float = 1.0,
    infer_from_lat: bool = False,
) -> None:
    """
    Plot the scaled mass balance field on a map, with projection depending on dataset_value.

    Parameters
    ----------
    mean_mb_ds : xr.Dataset
        Dataset containing mean mass balance data. Likely output from compute_mean_mass_balance_over_time_window.
    dataset_value : str
        Name of mean_mb_ds dataset, used to determine projection and extent. Must be one of "GrIS", "AIS",
        "AIS and GrIS", or "custom". If an unknown value is supplied and ``infer_from_lat`` is ``False`` (the
        default), a ``KeyError`` is raised. Set ``infer_from_lat=True`` to automatically infer the region from
        the latitude coverage of the data instead.
    plot_description_str : str
        Description of the data being plotted. Used in the plot title or suptitle, depending on dataset_value.
    scale : float
        Scaling factor for the mass balance values, by default 1.0
    infer_from_lat : bool
        When ``True``, unknown ``dataset_value`` strings are silently resolved by inspecting the latitude
        coverage of ``mean_mb_ds`` rather than raising a ``KeyError``. Defaults to ``False``.
    """
    mean_mb_ds_scaled = mean_mb_ds[MASS_BALANCE_COL_NAME] * scale
    mean_mb_ds_masked = np.ma.masked_where(mean_mb_ds_scaled == 0, mean_mb_ds_scaled)
    lat = mean_mb_ds["y"].values
    lon = mean_mb_ds["x"].values

    def _plot_data_on_axis(
        ax: plt.Axes, extent: list[float], sub_lon: np.ndarray, sub_lat: np.ndarray, sub_vmb: np.ndarray
    ) -> None:
        """Plot data on axis."""
        ax.set_extent(extent, crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor="lightblue")
        ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="navajowhite")
        ax.coastlines(resolution="50m", color="black", linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5, edgecolor="gray")
        sc = ax.scatter(sub_lon, sub_lat, c=sub_vmb, cmap="bwr_r", s=10, transform=ccrs.PlateCarree())
        cbar = plt.colorbar(sc, ax=ax, orientation="vertical", shrink=0.7, pad=0.04)
        cbar.set_label("Mass balance (kg per gridcell)", fontsize=12)

    config = {
        "GrIS": {"projection": ccrs.Orthographic(0, 90), "extent": [-180, 180, 50, 90], "figsize": (8, 8)},
        "AIS": {"projection": ccrs.Orthographic(0, -90), "extent": [-180, 180, -90, -50], "figsize": (8, 8)},
        "AIS and GrIS": {"projection": ccrs.PlateCarree(), "extent": [-180, 180, -90, 90], "figsize": (16, 8)},
        "custom": {"projection": ccrs.Robinson(), "extent": [-180, 180, -90, 90], "figsize": (14, 7)},
    }

    def _resolve_dataset_config_key(dataset_name: str, latitudes: np.ndarray) -> str:
        """Resolve plotting config from a known dataset key or infer it from latitude coverage.

        Raises KeyError for unknown dataset names unless ``infer_from_lat`` is True.
        """
        if dataset_name in config:
            return dataset_name

        if not infer_from_lat:
            raise KeyError(
                f"Unknown dataset_value: {dataset_name!r}. Must be one of {list(config.keys())}. "
                "Set infer_from_lat=True to infer the region from latitude coverage."
            )

        valid_latitudes = latitudes[~np.isnan(latitudes)]
        if valid_latitudes.size == 0:
            return "custom"

        has_north = np.any(valid_latitudes > 0)
        has_south = np.any(valid_latitudes < 0)

        if has_north and has_south:
            return "AIS and GrIS"
        if has_south:
            return "AIS"
        if has_north:
            return "GrIS"
        return "custom"

    resolved_dataset_value = _resolve_dataset_config_key(dataset_value, lat)

    if resolved_dataset_value == "AIS and GrIS":
        # Assume vmb contains both GrIS and AIS points, and you can distinguish them by latitude
        # (GrIS: lat > 0, AIS: lat < 0). Adjust if you have a better way to split.
        greenland_config = config["GrIS"]
        antarctica_config = config["AIS"]
        mask_gris = lat > 0
        mask_ais = lat < 0

        _, axes = plt.subplots(1, 2, figsize=(16, 8), subplot_kw={"projection": ccrs.Orthographic(0, 90)})
        # GrIS
        ax_gris = axes[0]
        ax_gris.projection = greenland_config["projection"]
        _plot_data_on_axis(
            ax_gris,
            greenland_config["extent"],
            lon[mask_gris],
            lat[mask_gris],
            mean_mb_ds_masked[mask_gris],
        )
        ax_gris.set_title("Greenland Ice Sheet", fontsize=12)

        axes[1].projection = antarctica_config["projection"]

        _plot_data_on_axis(
            axes[1],
            antarctica_config["extent"],
            lon[mask_ais],
            lat[mask_ais],
            mean_mb_ds_masked[mask_ais],
        )
        axes[1].set_title("Antarctic Ice Sheet", fontsize=12)

        plt.figtext(
            0.5,
            0.15,
            "Note: Different magnitudes for GrIS and AIS may stem from different gridcell sizes.",
            ha="center",
            va="bottom",
            fontsize=8,
            style="italic",
        )

        plt.suptitle(plot_description_str, fontsize=12, fontweight="bold", y=0.87)
        plt.show()
    else:
        dataset_config = config[resolved_dataset_value]
        _ = plt.figure(figsize=dataset_config["figsize"])
        ax = plt.axes(projection=dataset_config["projection"])
        _plot_data_on_axis(ax, dataset_config["extent"], lon, lat, mean_mb_ds_masked)
        plt.title(plot_description_str, fontsize=12, fontweight="bold")
        plt.show()


def plot_global_slr_three_panels(
    global_slr_ds: xr.Dataset, mean_mass_balance_ds: xr.Dataset, plot_description_str: str
) -> None:
    """
    Plot three-panel SELREM sea-level response maps from a mean mass balance dataset.

    Parameters
    ----------
    global_slr_ds : xr.Dataset
        Dataset containing global sea-level response data from SELREM. Likely output from run_selrem_module with
        analysis_mode="global". Should be derived from the same underlying mass balance dataset as mean_mass_balance_ds.
    mean_mass_balance_ds : xr.Dataset
        Dataset containing mean mass balance data, likely output from compute_mean_mass_balance_over_time_window. Should
        be derived from the same underlying mass balance dataset as global_slr_ds.
    plot_description_str : str
        Description of the data being plotted. Used in the plot title or suptitle.
    """
    sdot_corr = global_slr_ds["sdot"].values
    sig_ndot = global_slr_ds["sig_ndot"].values
    sig_udot = global_slr_ds["sig_udot"].values
    combined_unc = np.sqrt(sig_ndot**2 + sig_udot**2)
    lons_t = global_slr_ds["x"].values
    lats_t = global_slr_ds["y"].values

    gmsl = global_slr_ds.attrs["gmsl_sdot"]

    vlim = np.ceil(0.5 + gmsl)

    # Combine uncertainties in quadrature
    combined_unc = np.sqrt(sig_ndot**2 + sig_udot**2)

    # Prepare input points for red dots (exclude NaN or zero mass)
    input_mask = (
        ~np.isnan(mean_mass_balance_ds["y"].values)
        & ~np.isnan(mean_mass_balance_ds["x"].values)
        & (np.abs(mean_mass_balance_ds[MASS_BALANCE_COL_NAME]) > 0)
    )

    # Set up the figure with gridspec for custom layout
    from matplotlib.gridspec import GridSpec

    fig = plt.figure(figsize=(16, 7))
    gs = GridSpec(2, 3, width_ratios=[2.7, 1, 1], height_ratios=[1.25, 1], figure=fig)

    # Large left panel (sdot), fills both rows
    ax0 = fig.add_subplot(gs[:, 0], projection=ccrs.Robinson())
    ax0.set_global()
    im0 = ax0.pcolormesh(
        lons_t,
        lats_t,
        sdot_corr.T,
        cmap="Spectral_r",
        vmin=-(vlim * 1 + 1),
        vmax=(vlim * 1 + 1),
        shading="auto",
        transform=ccrs.PlateCarree(),
    )
    ax0.add_feature(cfeature.LAND, facecolor="white", zorder=10)
    ax0.coastlines(zorder=11)
    ax0.set_title("Relative sea-level change", fontsize=14)
    plt.colorbar(im0, ax=ax0, orientation="horizontal", shrink=0.7, pad=0.05, label="mm/yr")

    # Top-right: combined uncertainty, global
    ax1 = fig.add_subplot(gs[0, 1:], projection=ccrs.Robinson())
    ax1.set_global()
    im1 = ax1.pcolormesh(
        lons_t, lats_t, combined_unc.T, cmap="Reds", vmin=0, vmax=0.5, shading="auto", transform=ccrs.PlateCarree()
    )
    ax1.add_feature(cfeature.LAND, facecolor="white", zorder=10)
    ax1.coastlines(zorder=11)
    ax1.set_title("Uncertainty", fontsize=12)
    plt.colorbar(im1, ax=ax1, orientation="horizontal", shrink=0.4, pad=0.05, label="mm/yr")

    # Bottom-right: input points, global
    ax2 = fig.add_subplot(gs[1, 1:], projection=ccrs.Robinson())
    ax2.set_global()
    ax2.add_feature(cfeature.LAND, facecolor="navajowhite")
    ax2.add_feature(cfeature.OCEAN, facecolor="lightblue")
    ax2.coastlines(zorder=11)
    ax2.set_title("Locations of mass input", fontsize=12)
    ax2.scatter(
        np.array(mean_mass_balance_ds["x"])[input_mask],
        np.array(mean_mass_balance_ds["y"])[input_mask],
        color="red",
        s=10,
        transform=ccrs.PlateCarree(),
    )

    plt.suptitle(
        plot_description_str,
        fontsize=14,
        fontweight="bold",
    )
    plt.tight_layout()
    plt.show()


def _format_latlon(lat: float, lon: float) -> tuple[str, str]:
    """
    Return formatted latitude and longitude strings with correct cardinals: N/S/E/W.

    Parameters
    ----------
    lat : float
        Latitude in decimal degrees.
    lon : float
        Longitude in decimal degrees.

    Returns
    -------
    tuple[str, str]
        Formatted latitude and longitude strings.
    """
    lat_abs = abs(lat)
    lon_abs = abs(lon)
    lat_hem = "N" if lat >= 0 else "S"
    lon_hem = "E" if lon >= 0 else "W"

    return f"{lat_abs:.1f}°{lat_hem}", f"{lon_abs:.1f}°{lon_hem}"


def plot_slr_location_four_panels(annual_slr_ds: xr.Dataset, lat0: float, lon0: float) -> None:
    """
    Plot sea level rise (SLR) location results in the four-panel setup.

    Parameters
    ----------
    annual_slr_ds : xr.Dataset
        Dataset containing annual sea-level response data from SELREM. Likely output from run_selrem_module with
        analysis_mode="annual".
    lat0 : float
        Latitude of the location to plot.
    lon0 : float
        Longitude of the location to plot.

    Raises
    ------
    ValueError
        If lat0 or lon0 are out of bounds.
    """
    if lat0 < -90 or lat0 > 90:
        raise ValueError(f"Latitude must be between -90 and 90 degrees. Got {lat0}.")
    if lon0 < -180 or lon0 > 180:
        raise ValueError(f"Longitude must be between -180 and 180 degrees. Got {lon0}.")
    # Convert to legacy format
    results = {
        "ndot": [annual_slr_ds["ndot"].isel(time=i).values for i in range(len(annual_slr_ds["time"]))],
        "udot": [annual_slr_ds["udot"].isel(time=i).values for i in range(len(annual_slr_ds["time"]))],
        "sdot": [annual_slr_ds["sdot"].isel(time=i).values for i in range(len(annual_slr_ds["time"]))],
        "sig_ndot": [annual_slr_ds["sig_ndot"].isel(time=i).values for i in range(len(annual_slr_ds["time"]))],
        "sig_udot": [annual_slr_ds["sig_udot"].isel(time=i).values for i in range(len(annual_slr_ds["time"]))],
        "sig_sdot": [annual_slr_ds["sig_sdot"].isel(time=i).values for i in range(len(annual_slr_ds["time"]))],
    }

    years = pd.to_datetime(annual_slr_ds["time"].values).year
    lons_t = annual_slr_ds["x"].values
    lats_t = annual_slr_ds["y"].values
    years_numeric = years.astype(float)

    # Find nearest grid cell
    lon2d, lat2d = np.meshgrid(lons_t, lats_t, indexing="ij")
    dist2 = (lat2d - lat0) ** 2 + (lon2d - lon0) ** 2
    ilon, ilat = np.unravel_index(np.argmin(dist2), dist2.shape)

    # Extract annual series
    ndot_series = np.array([fld[ilon, ilat] for fld in results["ndot"]])
    udot_series = np.array([fld[ilon, ilat] for fld in results["udot"]])
    sdot_series = np.array([fld[ilon, ilat] for fld in results["sdot"]])

    sig_ndot_series = np.array([fld[ilon, ilat] for fld in results["sig_ndot"]])
    sig_udot_series = np.array([fld[ilon, ilat] for fld in results["sig_udot"]])
    sig_sdot_series = np.array([fld[ilon, ilat] for fld in results["sig_sdot"]])

    # Accumulate over time
    ndot_cum = np.cumsum(ndot_series)
    udot_cum = np.cumsum(udot_series)
    sdot_cum = np.cumsum(sdot_series)

    sig_ndot_cum = np.sqrt(np.cumsum(sig_ndot_series**2))
    sig_udot_cum = np.sqrt(np.cumsum(sig_udot_series**2))
    sig_sdot_cum = np.sqrt(np.cumsum(sig_sdot_series**2))

    years_numeric = years.astype(float)
    whole_years_mask = years_numeric % 1 == 0
    year_labels = years_numeric[whole_years_mask].astype(int)

    # Compute linear trends (mm/yr)
    slope_ndot, _ = np.polyfit(years_numeric, ndot_cum, 1)
    slope_udot, _ = np.polyfit(years_numeric, udot_cum, 1)
    slope_sdot, _ = np.polyfit(years_numeric, sdot_cum, 1)

    # Set up the figure with gridspec
    fig = plt.figure(figsize=(15, 7))
    gs = GridSpec(2, 3, width_ratios=[2.2, 1, 1], height_ratios=[1, 1], figure=fig)

    # Large left panel: relative sea-level change
    ax0 = fig.add_subplot(gs[:, 0])
    ax0.plot(year_labels, sdot_cum[whole_years_mask], "g-", label="Relative SLR (cum)")
    ax0.fill_between(
        year_labels,
        sdot_cum[whole_years_mask] - sig_sdot_cum[whole_years_mask],
        sdot_cum[whole_years_mask] + sig_sdot_cum[whole_years_mask],
        color="green",
        alpha=0.2,
    )
    ax0.set_title("Relative sea-level change", fontsize=14)
    ax0.set_xlabel("Year")
    ax0.set_ylabel("mm")
    ax0.text(
        0.05,
        0.6,
        f"Trend: {slope_sdot:.2f} mm/yr",
        transform=ax0.transAxes,
        fontsize=12,
        bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"},
    )
    ax0.grid(True)

    # Top-right: absolute sea-level change
    ax1 = fig.add_subplot(gs[0, 1])
    ax1.plot(year_labels, ndot_cum[whole_years_mask], "r-", label="Absolute SLR (cum)")
    ax1.fill_between(
        year_labels,
        ndot_cum[whole_years_mask] - sig_ndot_cum[whole_years_mask],
        ndot_cum[whole_years_mask] + sig_ndot_cum[whole_years_mask],
        color="red",
        alpha=0.2,
    )
    ax1.set_title("Absolute sea level change")
    ax1.set_xlabel("Year")
    ax1.set_ylabel("mm")
    ax1.text(
        0.05,
        0.6,
        f"Trend: {slope_ndot:.2f} mm/yr",
        transform=ax1.transAxes,
        fontsize=10,
        bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"},
    )
    ax1.grid(True)

    # Top-right: vertical deformation
    ax2 = fig.add_subplot(gs[0, 2])
    ax2.plot(year_labels, udot_cum[whole_years_mask], "b-", label="Vertical deformation (cum)")
    ax2.fill_between(
        year_labels,
        udot_cum[whole_years_mask] - sig_udot_cum[whole_years_mask],
        udot_cum[whole_years_mask] + sig_udot_cum[whole_years_mask],
        color="blue",
        alpha=0.2,
    )
    ax2.set_title("Vertical deformation")
    ax2.set_xlabel("Year")
    ax2.set_ylabel("mm")
    ax2.text(
        0.05,
        0.6,
        f"Trend: {slope_udot:.2f} mm/yr",
        transform=ax2.transAxes,
        fontsize=10,
        bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"},
    )
    ax2.grid(True)

    ax3 = fig.add_subplot(gs[1, 1:], projection=ccrs.Robinson())
    ax3.set_global()
    ax3.add_feature(cfeature.LAND, facecolor="navajowhite")
    ax3.add_feature(cfeature.OCEAN, facecolor="lightblue")
    ax3.coastlines(zorder=11)
    # ax3.set_title("Selected location", fontsize=12)
    ax3.scatter([lon0], [lat0], color="red", s=40, transform=ccrs.PlateCarree(), label="Selected location")
    ax3.legend(loc="center left", bbox_to_anchor=(0.83, 0.02), fontsize=10, frameon=False, handletextpad=0.5)

    # Format coordinates for title
    lat_str, lon_str = _format_latlon(lat2d[ilon, ilat], lon2d[ilon, ilat])
    plt.suptitle(f"Sea-level response at closest cell: {lat_str}, {lon_str}", fontsize=15)
    plt.tight_layout()
    plt.show()
