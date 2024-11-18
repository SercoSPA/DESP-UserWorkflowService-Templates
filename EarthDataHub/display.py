from cartopy import crs, feature
from matplotlib import pyplot as plt
import numpy as np
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
    return axs


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
    
    line1 = historic_quantile.isel(quantile=0).plot.line(x="dayofyear", c="green", alpha=0.8, linewidth=0.8, add_legend=True, ax=ax)
    line2 = historic_quantile.isel(quantile=1).plot.line(x="dayofyear", c="orange", alpha=0.8, linewidth=0.8, add_legend=True, ax=ax)

    line4 = historic_mean.plot.line(x="dayofyear", c="black", alpha=0.8, linewidth=0.8, add_legend=True, ax=ax)
    line5 = data_sum.plot.line(x="dayofyear", c="red", linewidth=1.5, add_legend=True, ax=ax, label = 'something')

    line3 = historic_sum.plot.line(x="dayofyear", c="black", alpha=0.05, linewidth=1, add_legend=False, ax=ax)

    ax.fill_between(
        historic_quantile.dayofyear,
        historic_quantile.sel(quantile=0.9),
        historic_quantile.sel(quantile=0.1),
        alpha=0.5,
        facecolor="gray"
    )


    month_starts = [1,32,61,92,122,153,183,214,245,275,306,336]
    month_names = ['Jan', 'Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  
    ax.set(xlim=[-10, 366], ylim=ylim, title=None)
    ax.set_yticks(ticks=np.arange(0,int(data_sum[-1].values), 200))
    ax.set_xticks(month_starts)
    ax.set_xticklabels(month_names)
    ax.set_xlabel(None)
    ax.set_ylabel(None);
    plt.xticks(fontsize=10)
    plt.yticks(fontsize=10)
    
    return ax

