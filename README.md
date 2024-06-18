# DestinE Jupyter Notebook Tutorials for the Insula's Code Lab

This set of Jupyter Notebook tutorials equips users with the skills to access and exploit Digital Twin data from DestinE for the Insula Code Lab. Examples are all written in Python. <br>
Tutorials are seamlessly integrated into the Insula Code Lab Python environment for all users. 

* [DestinE Platform CacheB data access](./cacheb/cacheb-climate-example.ipynb): this example supports the user in accessing the DESP Data CacheB Service and work with Climate Adaptation DT data.
* [How to access LUMI's Extremes Digital Twin data using earthkit and the Polytope API](./polytope/polytope-earthkit.ipynb): this example supports the user to retrieve Weather Extremes DT data from Polytope and visualize it.
* [How to discover and access data from DestinE Platform](./EDEN/EDEN-example.ipynb): this example supports the user in discover and access DestinE data through EDEN Service.

## Credits

* `cacheb-climate-example.ipynb` and `cacheb-authentication` original content created by B-Open (Earth Data Hub). 
* `polytope-earthkit.ipynb` and `desp-authentication.py` are a slightly modified version of the examples available at [Destination Earth Digital Twins's polytope examples](https://github.com/destination-earth-digital-twins/polytope-examples/) by ECMWF.
* `EDEN-example.ipynb` and `auth.py` original content created by MEEO (EDEN).

## Installation
The CodeLab environment includes some Python packages pre-installed in the user's environment. The overall list of dependencies is provided in the file [requirements.txt](./requirements.txt).
> **Note**: Pre-installed Python packages listed in this file provide a snapshot of dependencies needed to run the example notebooks provided in this repository.

The [destinelab](https://pypi.org/project/destinelab/) package requires a manual installation by the users, as follows:

* Open a terminal window and type:
```
pip install destinelab
```
## How to create a virtual environment
Users can always create their own Python virtual environment following the instructions provided below.<br>
Open a Terminal window and create a virtual environment named `my_env`: 
```
python -m venv /home/jovyan/my_env
```
Activate it:
```
source /home/jovyan/my_env/bin/activate
```
### Install dependencies
Users can install Python dependencies in this environment as follows.<br>
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
> Occasionally, a stop/start of the service is required to apply environment changes. Users can manage the server stop/start commands through the *File* dropdown menu.

## Contact
If you have questions or need support with these examples, contact the support at https://platform.destine.eu/support.
