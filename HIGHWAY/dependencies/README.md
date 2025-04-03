# HIGHWAY Insula. 
* [Insula](https://platform.destine.eu/services/service/insula-code/)

After generating your insula environment we suggest that you generate a dedicated 
HIGHWAY environment. 
## generate an environment
https://platform.destine.eu/services/documents-and-api/doc/?service_name=insula-lab

```
python -m venv /home/jovyan/platform-lab/highway_env
source /home/jovyan/platform-lab/highway_env/bin/activate
```

## Activate the environment 
```
pip install ipykernel
python -m venv /home/jovyan/platform-lab/highway_env
ipython kernel install --user --name=highway
```

## update requirements
```
pip install -r requirements.txt
```
