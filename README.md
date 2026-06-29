# DestinE Jupyter Notebook Tutorials for Insula Code Lab

Welcome to the repository for DestinE Platform Jupyter Notebook Tutorials!

This repository is designed to guide users through the [DestinE Platform Services](https://platform.destine.eu/services/), exploiting DestinE Digital Twin data as well as data from many other data sources within the [Insula Code Lab Service](https://platform.destine.eu/services/service/insula-code/) interactive Jupyter environment.

➡️ [Register](https://auth.destine.eu/realms/desp/account) on the Destination Earth Platform  and start using Jupyter Notebooks on [Insula Code Lab](https://code.insula.destine.eu)! Example notebooks are seamlessly integrated into the default Python environment for all registered users.

⚠️ To start exploiting DestinE Digital Twin data please make sure to request the *upgraded access* permission by visiting [this link](https://platform.destine.eu/access-policy-upgrade/).

## Jupyter Notebooks Examples

All examples are written in Python and are designed to work seamlessly with any DestinE Platform Data Access service.

* Access DestinE Climate Adaptation Digital Twin data on the [cacheb](./cacheb/cacheb-quickstart.ipynb) ➡️ *upgraded access* required.
* Discover DestinE Climate Adaptation Digital Twin [Data Streams](./DestineStreamer) on DestinEStreamer ➡️ *upgraded access* required.
* Discover and access Copernicus ERA5 data with [Earth Data Hub](./EarthDataHub) Service examples.
* Access data on the data lake via the [EDEN](./EDEN/EDEN-example.ipynb) service example.
* Try out DestinE Climate Adaptation Digital Twin scenarios in [Insula](./Insula) ➡️ *upgraded access* required.
* Compute the `Standard Evapotranspiration` variable from ERA5 data using the [Drought Assessment](./Insula/Drought_assessment.ipynb) example.
* Create a [DEA data story](./dea/create-asset/create-asset.ipynb) using the service example notebook.
* Try out [destinepyauth](./misc/destinepyauth_example.ipynb) for harmonized authentication against DestinE platform services.

Notebook templates are all a quickstart to DestinE Platform services. [Insula Code Lab](https://code.insula.destine.eu/) includes also ECMWF's Polytope and EUMETSAT's HDA examples in the user's own environment.

Stay tuned for more contents and feel free to contribute!

## Credits

* [Earth Data Hub](https://earthdatahub.destine.eu) tutorials and Cache-B original content created by [nicolamasotti](https://github.com/nicolamasotti) from [B-Open](https://www.bopen.eu). 
* [EDEN](https://finder.eden.destine.eu/) notebooks original content created by [MEEO](https://www.meeo.it/).
* [DestineStreamer](https://streamer.destine.eu/) examples created by [SamCarraro](https://github.com/SamCarraro) from [GeoVille](https://www.geoville.com/).
* [DEA](https://dea.destine.eu/web/) tutorials created by [Alia Space Systems](https://www.alia-space.com/).
* [Insula](https://insula.destine.eu/) contributions by [Bea07](https://github.com/Bea07), [albeCGI](https://github.com/albeCGI), and [crossi202](https://github.com/crossi202) from [CGI](https://cgi.com).
* [destinepyauth](https://github.com/SercoSPA/DestinE-Platform-AuthN) tutorial created by [purnelldj](https://github.com/purnelldj) from [Serco](https://www.serco.com/).

## The CodeLab Environment

The CodeLab environment includes some Python packages pre-installed in the user's environment. The full list of dependencies is provided in the file [requirements.txt](./requirements.txt).
> **Note**: Pre-installed Python packages listed in this file provide a snapshot of dependencies needed to run the example notebooks provided in this repository.

### Install new packages

To install new packages persistently in the coding environment, users can create their own virtual environment in Insula Code Lab by following the guidelines below.

#### Create a new environment

```
python -m venv /home/jovyan/my_env
```

Alternatively, if you also want access to the platform’s pre-installed packages from within the environment, add the `--system-site-packages` flag. Omit it to start from a clean environment.

```
python -m venv /home/jovyan/my_env --system-site-packages
```

#### Activate the new environment

```
source /home/jovyan/my_env/bin/activate
```

#### Install a new package

Install ipykernel together with your package so the environment can register its own notebook kernel. Always invoke pip as `python -m pip`, so packages install into the active environment.

```
python -m pip install ipykernel dvc # dvc is an arbitrary package in this example.
```

> **Note**: If you install a package while a notebook is already running on that environment’s kernel, restart the kernel before you can import and use the new package. A running kernel does not pick up packages added after it started.

#### Enable the environment for usage in a notebook’s kernel

```
python -m ipykernel install --user --name=my_env
```

then refresh the browser.

> **Note**: Register the kernel with `python -m ipykernel`, not `ipython kernel install`. The latter may register the Conda ipython instead of the environment’s Python: the package would be installed into `my_env`, while the notebook kernel would still start with `/opt/conda/bin/python`, so the environment is ignored and import raises a `ModuleNotFoundError`. Using `python -m ipykernel` binds the kernel to the environment’s interpreter and avoids this mismatch.

## Contributing
Contributions are welcome! Because this repository is made of Jupyter notebooks, we use [pre-commit](https://pre-commit.com/) hooks to keep diffs reviewable (stripping volatile notebook metadata while **keeping figures**), to lint code cells, and to scan for accidentally committed secrets.

Before opening a pull request:

1. Install and enable the hooks (one-time, per clone):
   ```
   pip install pre-commit
   pre-commit install
   ```
2. Run the hooks against everything and fix anything they flag:
   ```
   pre-commit run --all-files
   ```
   Some hooks (e.g. notebook metadata stripping) edit files in place — just re-stage the changes and commit again.

The same checks run automatically in CI on every pull request, so running them locally first avoids a failed build.

## Contact
If you have questions or need support with these examples contact the ➡️ [DestinE support](https://platform.destine.eu/support).
