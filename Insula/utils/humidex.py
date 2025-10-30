import numpy as np
import matplotlib.pyplot as plt
import xarray as xr
import pandas as pd

# Humidex (Masterson & Richardson, 1979
#         Blazejczyk et al. 2012, doi:10.1007/s00484‐011‐0453‐2)
# Input:
#  - t2m_C: temperature in C
#  - d2m: dew point in C
# Output:
#  - Humidex: Humidex in °C

def Humidex(t2m_c, t2d):

    Humidex = t2m_c + 5/9 * (6.11*np.exp(5417.7530*(1/273.15-1/(273.15-t2d))) - 10)

    return Humidex

# Define the categorization function
def categorize_hu(hu_value):
    if 20 <= hu_value < 29.5:
        return 'Little discomfort'
    elif 29.5 <= hu_value < 39.5:
        return 'Some discomfort'
    elif 39.5 <= hu_value < 45:
        return 'Great discomfort'
    elif hu_value >= 45:
        return 'Dangerous'
    else:
        return 'None'

# Apply the categorization function to the xarray DataArray
def apply_categorization(da):
    categorized = xr.apply_ufunc(
        np.vectorize(categorize_hu), 
        da, 
        vectorize=True, 
        dask='parallelized', 
        output_dtypes=[str]
    )
    return categorized

# Function to count unique classes within each month
def monthly_unique_counts(da):
    monthly_counts_list = []
    for month, group in da.resample(time='ME'):
        if group.size > 0:
            unique_counts = group.groupby(group).count()
            # Create a DataFrame with the unique counts and the corresponding month
            unique_counts_df = unique_counts.to_dataframe(name="counts").reset_index()
            unique_counts_df['month'] = pd.to_datetime(month).strftime('%Y-%m')
            monthly_counts_list.append(unique_counts_df)
        else:
            # Handle months with no data
            empty_counts_df = pd.DataFrame(
                {'group': ['L', 'S', 'D', 'G', 'N'], 'counts': [0, 0, 0, 0, 0], 'month': [pd.to_datetime(month).strftime('%Y-%m')]*5}
            )
            monthly_counts_list.append(empty_counts_df)
    return pd.concat(monthly_counts_list)

def plot_heat_index_categories(data_yoi, data_stats, location, yoi):

    # Define the categories and their corresponding labels and colors
    categories = ['L', 'S', 'G', 'D']
    labels = ['Little discomfort', 'Some discomfort', 'Great discomfort', 'Dangerous']
    colors = ['yellow', 'orange', 'red', 'purple']
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    plt.figure(figsize=(12, 8))

    # Plot the category values per month for the specified year
    for i, category in enumerate(categories):
        if category in data_yoi.columns:
            plt.bar(data_yoi.index.month + i*0.2, data_yoi[category], width=0.2, color=colors[i], label=labels[i])

    # Plot the average and standard deviation
    for i, category in enumerate(categories):
        if category in data_stats.columns.get_level_values(0):
            plt.errorbar(data_stats.index + i*0.2, data_stats[(category, 'mean')], 
                         yerr=data_stats[(category, 'std')], fmt='o', color=colors[i], ecolor='black', markersize=8, 
                         markeredgecolor='black', markeredgewidth=1.5, label=f'{labels[i]} Avg and Std (2020-2040)')

    plt.xlabel('Month')
    plt.ylabel('Number of Days')
    plt.title(f'Humidex categories for {location} in {yoi}')
    plt.xticks(range(1, 13), month_names)
    plt.grid(True)
    plt.legend(loc='best')
    plt.show() 