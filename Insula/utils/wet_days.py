import xarray as xr
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

def summarize_precipitation(data, thresholds):
    """
    Summarize the total values per day and count the days within each month that have more than the specified thresholds.

    Parameters:
    - data: xarray DataArray containing the precipitation data
    - thresholds: list of thresholds to count the days (e.g., [1, 10, 20])

    Returns:
    - summary: xarray Dataset containing the daily sums and counts for each threshold
    """
    # Resample the data to daily sums
    daily_sums = data.resample(time='D').sum()

    # Initialize a dictionary to store the counts for each threshold
    counts = {}

    for threshold in thresholds:
        # Count the number of days within each month that have more than the specified threshold
        counts[f'days_above_{threshold}mm'] = (daily_sums > threshold).resample(time='ME').sum()

    # Combine the daily sums and counts into a single dataset
    summary = xr.Dataset({'daily_sums': daily_sums, **counts})

    # Further summarize to monthly level
    monthly_sums = daily_sums.resample(time='ME').sum()
    monthly_summary = xr.Dataset({'monthly_sums': monthly_sums, **counts})

    return summary, monthly_summary


def plot_data(city_name, data_selected, avg_data, std_data, avg_era5, std_era5, yoi, ylabel, column_name):
    plt.figure(figsize=(12, 6))

    # Plot data for the year of interest as bars
    plt.bar(data_selected.index.month, data_selected[column_name], alpha=0.6, label=f'{yoi}')

    # Plot ERA5 average and std
    plt.plot(avg_era5.index, avg_era5, color='black', label='Average ERA5 (1990-2020)')
    plt.fill_between(avg_era5.index, avg_era5 - std_era5, avg_era5 + std_era5, color='grey', alpha=0.2, label='Std Dev ERA5 (1990-2020)')

    # Plot average and std for the whole period
    plt.plot(avg_data.index, avg_data, linestyle='--', color='orange', label='Average (2020-2040)')
    plt.fill_between(avg_data.index, avg_data - std_data, avg_data + std_data, color='orange', alpha=0.2, label='Std Dev (2020-2040)')

    # Set x-axis labels to months
    plt.xticks(range(1, 13), ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])

    # Add titles and labels
    plt.xlabel('Month')
    plt.ylabel(ylabel)
    plt.title(f'{ylabel} per Month for {city_name}')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()