import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

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

#Wet bulb temperature (Davies-Jones, 2008, doi:10.1175/2007MWR2224.1
#                      Bolton, 1980, doi:10.1175/1520‐0493(1980)108⟨1046:TCOEPT⟩2.0.CO;2
#                      Dunne et al., 2013, doi:10.1038/nclimate1827
#Input:
# - t2m_k: temperature in K
# - RH: relative humidity
# - sp: pressure in Pa
#Output:
# - WBT: wet-bulb temperature in °C
def WBT_DavJon(t2m_k, RH, sp):
    
    C    = 273.15 # K
    lamb = 3.504  # lamb = c_pd/R_d, Davies-Jones (2008)
    
    #Saturation vapour pressure (Dunne et al., 2013; Bolton, 1980)
    e_s = np.exp(-2991.2729/t2m_k**2 - 6017.0128/t2m_k + 18.87643854 - 0.028354721 * t2m_k + 1.7838301e-5 * t2m_k**2 - \
                  8.4150417e-10 * t2m_k**3 + 4.4412543e-13 * t2m_k**4 + 2.858487 * np.log(t2m_k))  

    #Saturation water vapour mixing ratio
    w_s = 621.97 * e_s / (sp - e_s)
    
    #Water vapour mixing ratio and vapour pressure
    w = RH/100 * w_s
    e = RH/100 * e_s
    
    # Temperature at condensation level
    T_L = (1 / (t2m_k - 55) - np.log(RH/100) / 2840)**(-1) + 55

    #Equivalent potential temperature (Bolton, 1980, equation 43; Dunne et al., 2013)
    theta_E = t2m_k * (100000 / sp)**(0.2854 * (1 - 0.28e-3 * w)) * np.exp( (3.376 / T_L - 0.00254) * w * (1 + 0.81e-3 * w))

    #Wet bulb temperature (Davies-Jones, 2008)
    WBT = 45.114 - 51.489 * (theta_E/C)**(-lamb)

    #Set data type to float32
    WBT = WBT.astype('float32')
    
    return WBT


#Wet-bulb globe temperature (e.g., Blazejczyk et al., 2012, doi:10.1007/s00484‐011‐0453‐2)
#Input:
# - t2m_K: temperature in K
# - RH: relative humidity
# - sp: pressure in Pa
#Output:
# - WBGT: wet-bulb globe temperature in °C
def WBGT(t2m_K, RH, sp):
    
    #Calculate wet bulb temperature 
    T_w = WBT_DavJon(t2m_K, RH, sp)

    #Wet-bulb globe temperature indoors
    WBGT = 0.7 * T_w + 0.3 * (t2m_K-273.15)
    WBGT = WBGT.astype('float32')
    return WBGT

def categorize_WBGT(wgbt_value):
    if 25 <= wgbt_value < 27.7:
        return 'Low'# Low heat stress
    elif 27.7 <= wgbt_value < 29.4:
        return 'Moderate' #  heat stress
    elif 29.4 <= wgbt_value < 31.6:
        return 'High'#  heat stress
    elif wgbt_value >= 31.6:
        return 'Extreme'#  heat stress
    else:
        return 'None'


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

    labels = ['Low', 'Moderate', 'High', 'Extreme']
    categories = ['Low', 'Moderate', 'High', 'Extreme']
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
    plt.title(f'Wet Bulb Globe Temperature for {location} in {yoi}')
    plt.xticks(range(1, 13), month_names)
    plt.grid(True)
    plt.legend(loc='best')
    plt.show()