# DestinE Jupyter Notebook Tutorials for the Insula's Code Lab

This set of Jupyter Notebook tutorials equips users with the skills to access and exploit Digital Twin data from DestinE for the Insula Code Lab. Examples are all written in Python. <br>
Tutorials are seamlessly integrated into the Insula Code Lab Python environment for all users. 

Notebook templates are all a quickstart to DestinE Platform services, including EDEN, Earth Data Hub, the Data Cache Services (Cache-A and Cache-B), DestinE Streamer, DEA, Polytope, HDA, and more! Stay tuned for more contents and feel free to contribute!

#### ⚠️ Warning: Authorized Access Only
The usage of Insula Code Lab and these example notebooks is reserved only to authorized DestinE user groups.<br>
➡️ Register on the [Destination Earth Platform](https://auth.destine.eu/realms/desp/account)

## Credits

* Cache-B notebooks original content created by B-Open (Earth Data Hub). 
* [Earth Data Hub](https://earthdatahub.com) tutorials created by [B-Open](https://www.bopen.eu). 
* `polytope-earthkit.ipynb` and `desp-authentication.py` are a slightly modified version of the examples available at [Destination Earth Digital Twins's polytope examples](https://github.com/destination-earth-digital-twins/polytope-examples/) by ECMWF.
* EDEN notebooks original content created by MEEO (EDEN).
* DestineStreamer original contents created by GeoVille (DestinE Streamer)
* DEA and Cache-A original contents created by [Alia Space Systems](https://www.alia-space.com/)

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
If you have questions or need support with these examples, contact the support at https://platform.destine.eu/support.
