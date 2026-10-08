# Jupyter notebooks for ESA DTC-IS

The notebooks in this folder allow the user to interact with ESA's digital twin component for ice sheets ([DTC-IS](https://dtc-ice-sheets.org/)).

User's may also wish to interact with the digital twin via the [dashboard](https://dashboards.dtc-ice-sheets.org/)

## Getting started

These notebooks are designed to work with the default Insula kernel. The additional dependencies are installed in the first cell of the notebook into your instance of the default kernel.

For some of the notebooks you will need to generate an authentication token. These notebooks typically display a text input widget in which you can copy and paste your token. The easiest pathway to generating your authentication token is logging into the [dashboard](https://dashboards.dtc-ice-sheets.org/) and creating a token via your preffered 3rd party OAuth provider. You can then reach your token by navigating [here](https://query.dtc-ice-sheets.org/auth/get-token).

> **_NOTE:_**  Some cells in these notebooks trigger externally hosted workflows to derive the results and may take a while to complete. Please allow each cell to complete before moving on to the next one.

## The notebooks

Each notebook contains a comprehensive description. An short description is provided here for orientation purposes.

1. DTC-IS-SLR.ipynb - Explore how changes in terrestrial water mass, such as from ice-sheet melt, affect global and regional sea level.
