import xarray as xr
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

#Heat index according to NOAA (Rothfusz, 1990
#                              Steadman, 1979, doi:10.1175/1520‐0450(1979)018⟨0861:TAOSPI⟩2.0.CO;2)
#Input:
# - t2m_f: temperature in F
# - RH: relative humidity
#Output:
# - HI_C: NOAA heat index in °C
def HI_NOAA(t2m_f, RH):

    #Calculate heat index
    c    = [-42.379, 2.04901523, 10.14333127, -0.22475541, -0.00683783, -0.05481717, 0.00122874, 0.00085282, -0.00000199]
    HI_F = c[0] + c[1]*t2m_f + c[2]*RH + c[3]*t2m_f*RH +c[4]*t2m_f*t2m_f + c[5]*RH*RH + \
           c[6]*t2m_f*t2m_f*RH + c[7]*t2m_f*RH*RH + c[8]*t2m_f*t2m_f*RH*RH

    #Adjustments to HI
    radicand = (17 - np.abs(t2m_f - 95)) / 17
    radicand = xr.where(radicand<0, np.NaN, radicand)
    HI_adj1 =  (13 - RH) / 4 * np.sqrt(radicand)
    HI_adj2 =  (RH - 85) * (87 - t2m_f) / 50
    HI_simple = 0.5 * (t2m_f + 61.0 + ((t2m_f - 68.0) * 1.2) + (RH * 0.094))    
    HI_F = xr.where((RH<13) & (t2m_f>80) & (t2m_f<112), HI_F - HI_adj1, HI_F) #Adjustment 1
    HI_F = xr.where((RH>85) & (t2m_f>80) & (t2m_f<87), HI_F + HI_adj2, HI_F)  #Adjustment 2
    HI_F = xr.where(HI_simple<80, HI_simple, HI_F) #Adjustment 3

    #Convert to degCelsius
    HI_C = (HI_F - 32) * 5/9

    return HI_C

def calculate_relative_humidity(t2m, d2m):
    """
    Calculate relative humidity (RH) using t2m and d2m variables.

    Parameters:
    - t2m: xarray.DataArray, temperature in Celsius
    - d2m: xarray.DataArray, dew point temperature in Celsius

    Returns:
    - RH: xarray.DataArray, relative humidity in percentage
    """
    # Calculate relative humidity (RH)
    RH = 100 * (np.exp(17.625 * d2m / (243.04 + d2m)) / np.exp(17.625 * t2m / (243.04 + t2m)))## https://www.omnicalculator.com/physics/relative-humidity 

    # Add attributes to RH
    RH.attrs["units"] = "%"
    RH.attrs["long_name"] = "Relative Humidity"

    return RH
# Define categories based on HI values
def categorize_hi(hi_value):
    if 27 <= hi_value < 32:
        return 'Caution'
    elif 32 <= hi_value < 41:
        return 'Extreme Caution'
    elif 41 <= hi_value < 54:
        return 'Danger'
    elif hi_value >= 54:
        return 'Extreme Danger'
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

    # Plot the category values per month
    categories = ['Caution', 'Extreme Caution', 'Danger', 'Extreme Danger']
    labels = ['Caution', 'Extreme Caution', 'Danger', 'Extreme Danger']
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
    plt.title(f'NOAA Heat Index categories for {location} in {yoi}')
    plt.xticks(range(1, 13), month_names)
    plt.grid(True)
    plt.legend(loc='best')
    plt.show()