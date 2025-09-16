import requests
import json
from colorama import Fore,Style
import time


# ----------------Visualizazing the list of datasets-------------------

def display_stac_dataset(response):
    count_results = response['numberMatched']
    print(Style.BRIGHT + Fore.BLUE + 'Number of datasets in the catalogue: ', count_results)

    dataset_list = response['collections']
    list(response.keys())

    print(Fore.BLUE + '\033[1m' + 'List of available datasets:')
    print('----------------------------------------------------------------------')
    print('\033[0m')

    for k in dataset_list:
        print(k['title'])
        print("\033[1m" + " datasetId " + "\033[0m" + "= " + k['id'])

        print('---------------------------------------------------------------')


def display_stac_dataset_metadata(response):
    print('Metadata of ' + Style.BRIGHT + response['title'])
    print('Description: ' + Style.BRIGHT +  response['description'])
    print(
        'Temporal coverage: ' + Style.BRIGHT +
        response['extent']['temporal']['interval'][0][0] + ' - ' +
        response['extent']['temporal']['interval'][0][1]
    )

def display_stac_product(response):
    for i in response["features"]:
        print('-----------------------------------------------')
        print('product: ' + i['id'])
        print('product start date: ' + i['properties']['start_datetime'])
        print('direct download: ' + i['assets']['data']['href'])


def display_metadata(endpoint,datasetId,response):

    results = response['properties']['totalResults']
    pages = results // 10
    for i in range(0, pages + 1):
        getPage = requests.get(endpoint + '/opensearch/datasets?startIndex=' + str(i * 10)).json()
        for k in getPage['features']:
            if k['datasetId'] == datasetId:
                print('\033[1;31m' + Fore.BLACK + 'Metadata of ' + Style.BRIGHT + Fore.RED +  k['title'] + ':')
                print ('\033[0;0m')
                print('\033[1;31m' + Fore.BLACK + 'Description: ' + Style.BRIGHT + Fore.BLUE +  k['description'])
                print('\033[1;31m' + Fore.BLACK + 'Format for download: ' + Style.BRIGHT + Fore.BLUE +  k['format'])
                print('\033[1;31m' + Fore.BLACK + 'Temporal coverage: ' + Style.BRIGHT + Fore.BLUE +  k['minDate']+ ' - ' + k['maxDate'])
                print('\033[1;31m' + Fore.BLACK + 'Variables: ' + Style.BRIGHT + Fore.BLUE + str(k['subDatasets'].keys())[9:])
                print('\033[1;31m' + Fore.BLACK + 'Total number of products: ' + Style.BRIGHT + Fore.BLUE +  str(k['numberOfRecords']))


#-------------------------------------------visualizing the results of a search request------------------------------------

def display_result(response, maxRecords):

    total = response['properties']['totalResults']
    print('\033[1;31m' + Fore.BLACK + 'Total number of products: ' + Style.BRIGHT + Fore.BLUE +  str(total))

    if total>int(maxRecords):
        print(Fore.BLACK + 'List of the ' + str(maxRecords) + ' most recent products')
    else:
        print(Fore.BLACK + 'List of the ' + str(total)+ ' most recent products')
    count = 1
    for i in response["features"]:
        print("\033[1;30;1m" + '-----------------------------------------------')
        print("\033[1;30;1m" + "#" + str(count))
        print ('\033[0m')
        print(Style.BRIGHT + Fore.RED + 'product: ' + Fore.GREEN + i['productId'])
        print(Style.BRIGHT + Fore.RED + 'product date: ' + Fore.GREEN + i['productDate'])
        print(Style.BRIGHT + Fore.RED + 'direct download: ' + Fore.BLUE + i['directDownload'])
        count = count+1



#--------------visualizing the results of a temporal search request, with product selection----------------

def temporal_search(response, maxRecords):

    total = response['properties']['totalResults']
    print('\033[1;31m' + Fore.BLACK + 'Total number of products: ' + Style.BRIGHT + Fore.BLUE +  str(total))

    if total>int(maxRecords):
        print(Fore.BLACK + 'List of the ' + str(maxRecords) + ' most recent products')
    else:
        print(Fore.BLACK + 'List of the ' + str(total)+ ' most recent products')
    count = 1
    list_result = []
    for i in response["features"]:
        print("\033[1;30;1m" + '-----------------------------------------------')
        print("\033[1;30;1m" + "#" + str(count))
        print ('\033[0m')
        print(Style.BRIGHT + Fore.RED + 'product: ' + Fore.GREEN + i['productId'])
        print(Style.BRIGHT + Fore.RED + 'product date: ' + Fore.GREEN + i['productDate'])
        print(Style.BRIGHT + Fore.RED + 'direct download: ' + Fore.BLUE + i['directDownload'])
        count = count+1
        result = {'product_id': i['productId'], 'location':i['directDownload']}
        list_result.append(result)
    return list_result


#------------------------------------------Download process----------------------------------------

def download_request(endpoint, location, access_token, sleep = 5):
    """
    This function is the full process on to download an ARCO product.

    :param endpoint: The URL of the ARCO Product downloading service.
    :param location: A string that describes the product to download.
    :param access_token: The HIGHWAY access token of the user.
    :param sleep: How long to sleep between each request (in seconds).

    :return: The filename of the downloaded file.
    """
    filename = ""
    headers = {"Authorization": "Bearer %s " % access_token}

    data = {"downloadLink": location}

    # -- the first step is to request the system to generate a ZIP file for the product.
    r_processor = requests.post(
        endpoint + '/dap/api/v1/processes/zipper',
        headers=headers,
        data=json.dumps(data)
    )
    print(r_processor.status_code)
    if r_processor.status_code == 200:
        # -- If the product exists, the system creates a job to generate the ZIP file.
        # we need to check that the file is ready
        job_id = r_processor.json()['job_id']
        code = 202
        while code == 202:
            # a loop is done to check the status of the JOB.
            r_job = requests.head(
                endpoint + "/dap/api/v1/jobs/" + job_id,
                headers=headers
            )
            time.sleep(sleep)
            print(r_job.status_code)

            if r_job.status_code == 200:
                # the ZIP file is finalized.
                break

        # -- when the ZIP file is finalized, we start the ARCO product download.
        r_download = requests.get(
            endpoint + "/dap/api/v1/downloads/" + job_id,
            headers=headers
        )
        filename = r_download.headers['content-disposition'].split('=')[1][1:-1]
        with open(filename, "wb") as f:
            f.write(r_download.content)
            print('Download complete!')

    return filename
