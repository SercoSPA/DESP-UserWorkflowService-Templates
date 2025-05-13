import matplotlib.pyplot as plt

# Function to calculate frost days (min temperature below  0°C)
def calculate_frost_days(data_array):
    df = data_array.to_dataframe().reset_index()
    daily_min_temp = df.resample('D', on='time').min()
    frost_days = daily_min_temp[daily_min_temp['t2m'] < 0]
    frost_days_per_month = frost_days.resample('ME').count()
    return frost_days_per_month

# Function to define the plot of the data
def plot_data(city_name, average_data, std_data, era5_data, era5_std, year_data, yoi, plot_type, ylabel):
    plt.figure(figsize=(12, 6))

    # Plot average data per month (2020-2040) as dashed line with standard deviation spread
    plt.plot(average_data.index, average_data, linestyle='--', label='Average 2020-2040')
    plt.fill_between(average_data.index, 
                     average_data - std_data, 
                     average_data + std_data, 
                     color='orange', alpha=0.2, label='St. Dev. 2020-2040')

    # Plot average data per month for ERA5 data as black line with greyed area for STD range
    plt.plot(era5_data.index, era5_data, color='black', label='Average 1990-2020 ERA5')
    plt.fill_between(era5_data.index, 
                     era5_data - era5_std, 
                     era5_data + era5_std, 
                     color='grey', alpha=0.2, label='St. Dev. 1990-2020 ERA5')

    # Plot data for the specified year as bars
    plt.bar(year_data.index.month, year_data['t2m'], alpha=0.6, label=f'{yoi}')

    # Set x-axis labels to months
    plt.xticks(range(1, 13), ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])

    # Add titles and labels
    plt.title(f'{plot_type} per Month for {city_name} {yoi}')
    plt.xlabel('Month')
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.legend()

    # Show the plot
    plt.tight_layout()
    plt.show()