from cartopy import crs, feature
from matplotlib import pyplot as plt
import xarray as xr

VMAX = 200
PROJECTION = crs.EqualEarth()
CMAP = "Blues"


xr.set_options(keep_attrs=True)


def map(data, location=None, vmax=VMAX, vmin=None, projection=PROJECTION, cmap=CMAP, ax=None, figsize=None, extent=None, **kwargs):
    if ax is None:
        _, ax = plt.subplots(subplot_kw={"projection": projection}, figsize=figsize)

    data.plot(ax=ax, cmap=cmap, vmax=vmax, vmin=vmin, transform=crs.PlateCarree())
    
    if location is not None:
        ax.plot(
            location["longitude"],
            location["latitude"],
            "+",
            edgecolor="red",
            transform=crs.PlateCarree(),
        )

    ax.coastlines(linewidth=0.5)
    ax.add_feature(feature.BORDERS, linewidth=0.5, edgecolor='dimgrey')
    ax.set(**kwargs)
    if extent:
        ax.set_extent(extent)

    return ax


def maps(data, vmax=VMAX, projection=PROJECTION, cmap=CMAP, axs_set=[]):
    f, axs = plt.subplots(
        1, len(data), subplot_kw={"projection": projection}, figsize=(16, 6)
    )
    if len(axs_set) < len(data):
        axs_set.extend([{}] * (len(data) - len(axs_set)))
    for ax, d, kwargs in zip(axs, data, axs_set):
        map(d, vmax=vmax, projection=projection, cmap=cmap, ax=ax, **kwargs)


def compare(data, historic, time="time", ylim=[0, 1300]):
    data_sum = (
        data.resample({time: "D"})
        .sum()
        .assign_coords(dayofyear=data[time].dt.dayofyear)
        .swap_dims({time: "dayofyear"})
        .cumsum("dayofyear")
    ) * 1000
    data_sum.attrs["units"] = "mm"
    historic_sum = (
        historic.resample({time: "D"})
        .sum()
        .assign_coords(
            year=historic[time].dt.year, dayofyear=historic[time].dt.dayofyear
        )
        .set_index({time: ["year", "dayofyear"]})
        .unstack(time)
        .cumsum("dayofyear")
    ) * 1000
    historic_sum.attrs["units"] = "mm"
    historic_quantile = historic_sum.quantile([0.1, 0.9], dim="year")
    historic_mean = historic_sum.mean("year")
    _, ax = plt.subplots(figsize=(10, 6))
    ax.fill_between(
        historic_quantile.dayofyear,
        historic_quantile.sel(quantile=0.9),
        historic_quantile.sel(quantile=0.1),
        alpha=0.2,
        color="gray",
    )
    historic_sum.plot.line(x="dayofyear", c="red", alpha=0.05, add_legend=False, ax=ax)
    historic_mean.plot.line(x="dayofyear", c="red", add_legend=False, ax=ax)
    data_sum.plot.line(x="dayofyear", c="blue", add_legend=False, ax=ax)
    ax.set(xlim=[0, 366], ylim=ylim, title=None)
