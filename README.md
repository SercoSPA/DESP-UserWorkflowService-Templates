# DestinE Jupyter Notebook Tutorials for the Insula's Code Lab

Welcome to the repository for DestinE Platform Jupyter Notebook Tutorials!

This repository is designed to guide users through the [DestinE Platform Services](https://platform.destine.eu/services/), exploiting DestinE Digital Twin data as well as data from many other data sources within the [Insula Code Lab Service](https://platform.destine.eu/services/service/insula-code/) interactive Jupyter environment.

➡️ [Register](https://auth.destine.eu/realms/desp/account) on the Destination Earth Platform  and start using Jupyter Notebooks on [Insula Code Lab](https://code.insula.destine.eu)! Example notebooks are seamlessly integrated into the default Python environment for all registered users.

⚠️ To start exploiting DestinE Digital Twin data please make sure to request the *upgraded access* permission by visiting [this link](https://platform.destine.eu/access-policy-upgrade/).

## Jupyter Notebooks Examples

All examples are written in Python and are designed to work seamlessly with any DestinE Platform Data Access service.

* Access DestinE Climate Adaptation Digital Twin data on the [cacheb](./cacheb/cacheb-quickstart.ipynb) ➡️ *upgraded access* required.
* Access DestinE Climate Adaptation and Weather Extremes Digital Twin [data from Polytope](./polytope/polytope-earthkit.ipynb) and visualize it ➡️ *upgraded access* required.
* Discover DestinE Climate Adaptation Digital Twin [Data Streams](./DestineStreamer) on DestinEStreamer ➡️ *upgraded access* required.
* Discover and access Copernicus ERA5 data with [Earth Data Hub](./EarthDataHub) Service examples.
* Access data on the [Data Lake via EDEN](./EDEN/EDEN-example.ipynb) Service example. 
* Compute the `Standard Evapotranspiration` variable from ERA5 data using the [Drought Assessment](./Insula/Drought_assessment.ipynb) example.
* Search and download Copernicus Sentinels data via STAC on the [cachea](./cachea/search_and_download.ipynb) example.
* Create a [DEA](https://dea.destine.eu/web/) data story on Jupyter Notebook using [dea](./dea/create-asset/create-asset.ipynb) Service example.

Notebook templates are all a quickstart to DestinE Platform services, including also ECMWF's Polytope and EUMETSAT's HDA.

Stay tuned for more contents and feel free to contribute!

## Credits

* [Earth Data Hub](https://earthdatahub.com) tutorials and Cache-B original content created by [nicolamasotti](https://github.com/nicolamasotti) from [B-Open](https://www.bopen.eu). 
* [EDEN](https://finder.eden.destine.eu/) notebooks original content created by [MEEO](https://www.meeo.it/).
* [DestineStreamer](https://streamer.destine.eu/) examples created by [SamCarraro](https://github.com/SamCarraro) from [GeoVille](https://www.geoville.com/).
* [DEA](https://dea.destine.eu/web/) and Cache-A tutorials created by [Alia Space Systems](https://www.alia-space.com/).
* [Insula](https://insula.destine.eu/) contributions by [Bea07](https://github.com/Bea07) from [CGI](https://cgi.com).
* Polytope example is a slightly modified version of the examples available at ECMWF's [Destination Earth Digital Twins's polytope examples](https://github.com/destination-earth-digital-twins/polytope-examples/).

## Installation
The CodeLab environment includes some Python packages pre-installed in the user's environment. The overall list of dependencies is provided in the file [requirements.txt](./requirements.txt).
> **Note**: Pre-installed Python packages listed in this file provide a snapshot of dependencies needed to run the example notebooks provided in this repository.

To install new packages persistently in the coding environment, users can create their own virtual environment in Insula Code Lab by following the guidelines below.

## How to create a virtual environment
Open a Terminal window and create a virtual environment named `my_env`: 
```
python -m venv /home/jovyan/my_env
```
Activate it:
```
source /home/jovyan/my_env/bin/activate
```
### Install dependencies
Install Python dependencies in the virtual environment as follows.<br>
* Open a terminal window and install a single module singularly:
```
pip install <package>
```
Or install modules in batch by means of a requirements file:
* Open a terminal window and type:
```
pip install -r requirements.txt
```
### Install the kernel
Install the Jupyter kernel `my_env`:
```
ipython kernel install --user --name=my_env
```
> **Note**: Do not forget to change the kernel to `my_env` using the upper-right button within the Jupyter user interface every time you want to run your code.
> Occasionally, a stop/start of the service is required to apply environment changes. Users can manage the server stop/start commands via the *File* dropdown menu under *Hub Control Panel*.

## Contact
If you have questions or need support with these examples contact the ➡️ [DestinE support](https://platform.destine.eu/support).
