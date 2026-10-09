# Digital Twin Component for Ice Sheets (DTC-IS) Jupyter Notebook demonstrators

This folder contains notebook demonstrators for the [Digital Twin Component for Ice Sheets (DTC-IS)](https://dtc-ice-sheets.org/), an ESA-funded, EO-driven digital twin project.

The notebooks access the system's functionality through the (DTC-IS Query API)[https://query.dtc-ice-sheets.org/docs], using its (Python client)[https://pypi.org/project/dtc-query-client/].

For a more interactive way of exploring the system, please visit the twin's [dashboard](https://dashboards.dtc-ice-sheets.org/).

If you have any questions or encounter any issues while using the notebooks, please get in touch with the DTC-IS team at support@dtc-ice-sheets.org.

## Getting started

The notebooks are designed to run using the default Insula kernel. Any additional dependencies (e.g. the DTC-IS API Python client) are installed into your instance of the default kernel by the first cell of each notebook.

> **_NOTE:_**  The packages will be installed on your currently selected kernel. We recommend that you create a virtual environment to keep your development environment isolated. Details of how to do this are provided in the top level readme of this repository.

Each notebook requires a DTC-IS API token for authentication, and will prompt you to enter yours. You can obtain your token by navigating [here](https://query.dtc-ice-sheets.org/auth/get-token).

> **_NOTE:_**  Some cells in these notebooks trigger externally hosted workflows to derive the results and may take a while to complete. Please allow each cell to complete before moving on to the next one. Workflow results are cached, so subsequent runs of each step should complete faster.

## The notebooks

Each notebook contains a comprehensive description of its purpose and methodology. A short overview is provided below for orientation purposes.

1. DTC-IS-SLR.ipynb - Explore how changes in terrestrial water mass, such as those resulting from ice-sheet melt, affect global and regional sea level.
