# DestinE Jupyter Notebook Tutorials for the Insula's Code Lab

This set of Jupyter Notebook tutorials equips users with the skills to access and exploit Digital Twin data from DestinE for the Insula Code Lab. Examples are all written in Python.

* [DestinE Platform CacheB data access](./cacheb/cacheb-climate-example.ipynb): this example supports the user in accessing the DESP Data CacheB Service and work with Climate Adaptation DT data.
* [How to access LUMI's Extremes Digital Twin data using earthkit and the Polytope API](./polytope/polytope-earthkit.ipynb): this example supports the user to retrieve Weather Extremes DT data from Polytope and visualize it.
* [How to discover and access data from DestinE Platform](./EDEN/EDEN-example.ipynb): this example supports the user in discover and access DestinE data through EDEN Service.

## Installation
The collection of Jupyter Notebooks tutorials is seamlessly integrated into your personal Insula Code Lab user environment. To execute these tutorials, simply follow the instructions provided below to install a Python virtual environment.
### Create a virtual environment
Open a Terminal window and create a virtual environment named `getting_started`: 
```
python -m venv /home/jovyan/getting_started
```
Activate it:
```
source /home/jovyan/getting_started/bin/activate
```
### Install dependencies
We collected the needed dependencies in the requirements file `requirements.txt` [here](./requirements.txt). Install these dependencies within the `getting_started` created at the step above.
```
pip install -r requirements.txt
```
> **Note**: These requirements are frozen as of the latest update of this repository, meaning the module versions specified reflect a snapshot of dependencies at that specific point in time.

Install the Jupyter kernel `getting_started`:
```
ipython kernel install --user --name=getting_started
```
> **Note**: Do not forget to change the kernel to `getting_started` every time you want to run the Insula Code Lab Jupyter tutorials.

## Credits

* `cacheb-climate-example.ipynb` and `cacheb-authentication` original content created by B-Open (Earth Data Hub). 
* `polytope-earthkit.ipynb` and `desp-authentication.py` are a slightly modified version of the examples available at [Destination Earth Digital Twins's polytope examples](https://github.com/destination-earth-digital-twins/polytope-examples/) by ECMWF.
* `EDEN-example.ipynb` and `auth.py` original content created by MEEO (EDEN).

## Contact
If you have questions or need support with these examples, contact the support at https://platform.destine.eu/support.
