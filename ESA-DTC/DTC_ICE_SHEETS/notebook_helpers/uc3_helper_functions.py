"""Provide helper functions and widgets for the UC3 notebooks."""

from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path

import ipywidgets as widgets
import pandas as pd
import plotly.graph_objects as go
import pytz
import requests
import yaml
from dtc_query_client import (
    ApiClient,
    Configuration,
    CovariateAnalysisRequest,
    CovariateAnalysisType,
    GenericApi,
    StateAndFateApi,
    VariableItem,
)
from dtc_query_client.helpers import wait_for_job
from IPython.display import display
from plotly.colors import qualitative
from plotly.subplots import make_subplots
from traitlets import traitlets


def authenticate_with_token(token: str) -> ApiClient:
    """
    Create an authenticated API client.

    Parameters
    ----------
    token : str
        API token used to authenticate requests against the DTC Query API.

    Returns
    -------
    ApiClient
        Configured API client instance.
    """
    config = Configuration(host="https://query.dtc-ice-sheets.org", access_token=token)
    client = ApiClient(config)
    return client


class LoadedButton(widgets.Button):
    """A button that can hold a value as an attribute."""

    def __init__(self: LoadedButton, value: object = None, *args: object, **kwargs: object) -> None:
        """
        Initialize the button with an attached value trait.

        Parameters
        ----------
        value : any, optional
            Initial value stored on the button, by default None.
        *args
            Positional arguments forwarded to ``widgets.Button``.
        **kwargs
            Keyword arguments forwarded to ``widgets.Button``.
        """
        super(LoadedButton, self).__init__(*args, **kwargs)
        self.add_traits(value=traitlets.Any(value))


def update_client(b: LoadedButton) -> object:
    """
    Return the client stored on a loaded button.

    Parameters
    ----------
    b : LoadedButton
        Button carrying the client in its ``value`` attribute.

    Returns
    -------
    object
        Stored client value.
    """
    return b.value


def _load_dataset_yaml() -> dict:
    """Load dataset and variable mappings from YAML configuration.

    Returns
    -------
    dict
        Parsed mapping configuration loaded from `variable_mappings.yml`.
    """
    temp_path = Path(__file__).parent / "variable_mappings.yml"

    with temp_path.open("r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)
    return config_dict


def _parse_datasets(dataset_config: dict) -> list[str]:
    """Convert dataset identifiers to display labels.

    Parameters
    ----------
    dataset_config : dict
        Dataset mapping configuration keyed by dataset identifier.

    Returns
    -------
    list[str]
        Human-readable dataset labels.
    """
    return [_dataset_name_to_pretty_dataset_name(x) for x in dataset_config.keys()]


def _dataset_names_to_pretty_dataset_names() -> dict:
    """Build a mapping from dataset identifiers to display labels.

    Returns
    -------
    dict
        Mapping from dataset name to dataset label.
    """
    dataset_config = _load_dataset_yaml()
    return {dataset: dataset_config[dataset]["label"] for dataset in dataset_config}


def _pretty_dataset_names_to_dataset_names() -> dict:
    """Build a mapping from display labels to dataset identifiers.

    Returns
    -------
    dict
        Mapping from dataset label to dataset name.
    """
    dataset_config = _load_dataset_yaml()
    return {dataset_config[dataset]["label"]: dataset for dataset in dataset_config}


def _pretty_dataset_name_to_dataset_name(pretty_name: str) -> str:
    """Resolve a dataset display label to its dataset identifier.

    Parameters
    ----------
    pretty_name : str
        Human-readable dataset label.

    Returns
    -------
    str
        Dataset identifier if found, otherwise ``None``.

    Raises
    ------
    ValueError
        If the provided label does not match any dataset in the configuration.
    """
    mapping = _pretty_dataset_names_to_dataset_names()
    name = mapping.get(pretty_name, None)

    if name is None:
        raise ValueError(f"Dataset label '{pretty_name}' not found in configuration.")

    return name


def _dataset_name_to_pretty_dataset_name(dataset_name: str) -> str:
    """Resolve a dataset identifier to its display label.

    Parameters
    ----------
    dataset_name : str
        Dataset identifier used by the API.

    Returns
    -------
    str
        Human-readable dataset label if found, otherwise ``None``.

    Raises
    ------
    ValueError
        If the provided identifier does not match any dataset in the configuration.
    """
    mapping = _dataset_names_to_pretty_dataset_names()
    name = mapping.get(dataset_name, None)

    if name is None:
        raise ValueError(f"Dataset identifier '{dataset_name}' not found in configuration.")

    return name


def _var_names_to_pretty_var_names() -> dict:
    """Build a mapping from variable identifiers to display labels.

    Returns
    -------
    dict
        Mapping from variable name to variable label.
    """
    dataset_config = _load_dataset_yaml()
    var_mapping = {}
    for dataset in dataset_config:
        for variable in dataset_config[dataset]["variables"]:
            var_mapping[variable] = dataset_config[dataset]["variables"][variable]["label"]
    return var_mapping


def _var_name_to_pretty_var_name(var_name: str) -> str:
    """Resolve a variable identifier to its display label.

    Parameters
    ----------
    var_name : str
        Variable identifier used by the API.

    Returns
    -------
    str
        Human-readable variable label if found, otherwise ``None``.

    Raises
    ------
    ValueError
        If the provided identifier does not match any variable in the configuration.
    """
    mapping = _var_names_to_pretty_var_names()
    name = mapping.get(var_name, None)

    if name is None:
        raise ValueError(f"Variable identifier '{var_name}' not found in configuration.")

    return name


def _var_name_units(var_name: str, dataset: str) -> str:
    """Retrieve the units for a given variable identifier.

    Parameters
    ----------
    var_name : str
        Variable identifier used by the API.
    dataset : str
        Dataset identifier used by the API.

    Returns
    -------
    str
        Units string if found, otherwise ``None``.

    Raises
    ------
    ValueError
        If the provided variable identifier does not match any variable in the configuration.
    """
    dataset_config = _load_dataset_yaml()
    if dataset in dataset_config and var_name in dataset_config[dataset]["variables"]:
        return dataset_config[dataset]["variables"][var_name]["units"]

    raise ValueError(f"Variable identifier '{var_name}' not found in configuration.")


async def get_ice_shelves(client: ApiClient) -> list[str]:
    """
    Fetch available ice shelf names.

    Parameters
    ----------
    client : ApiClient
        Authenticated API client.

    Returns
    -------
    list[str]
        Available ice shelf names.
    """
    return await StateAndFateApi(client).list_ice_shelves()


async def get_dataset(client: ApiClient) -> list[object]:
    """
    Fetch available dataset overviews.

    Parameters
    ----------
    client : ApiClient
        Authenticated API client.

    Returns
    -------
    list[object]
        Dataset overview objects returned by the API.
    """
    return await GenericApi(client).dataset_overviews()


async def ice_shelf_selector(client: ApiClient) -> widgets.VBox:
    """
    Create an ice shelf selection widget.

    Parameters
    ----------
    client : ApiClient
        Authenticated API client.

    Returns
    -------
    widgets.VBox
        VBox containing the ice shelf selection dropdown.
    """
    ice_shelves = await get_ice_shelves(client=client)

    return widgets.VBox(
        [
            widgets.Label(value="Select Ice Shelf:"),
            widgets.Dropdown(
                options=ice_shelves,
                value="thwaites",
                disabled=False,
                layout=widgets.Layout(width="90%"),
            ),
        ],
        layout=widgets.Layout(width="30%", margin="0rem 2rem 0rem 0rem"),
    )


async def display_datasets_and_variables(client: ApiClient) -> tuple[widgets.VBox, widgets.VBox]:
    """
    Create dataset and variable selection widgets.

    Parameters
    ----------
    client : ApiClient
        Authenticated API client.

    Returns
    -------
    tuple[widgets.VBox, widgets.VBox]
        Dataset selection widget and variable selection widget.
    """

    def variable_update_on_button_clicked(button: widgets.Button) -> None:
        """Refresh variable options after dataset selection changes.

        Parameters
        ----------
        button : widgets.Button
            Button used to trigger variable list refresh.
        """
        variable_widget.children[1].options = _parse_variables(
            _load_dataset_yaml(), [_pretty_dataset_name_to_dataset_name(x) for x in dataset_widget.children[1].value]
        )

    def _parse_variables(dataset_config: dict, selected_datasets: list[str]) -> list[str]:
        """Collect variables available in selected datasets.

        Parameters
        ----------
        dataset_config : dict
            Dataset mapping configuration keyed by dataset identifier.
        selected_datasets : list[str]
            Dataset identifiers selected by the user.

        Returns
        -------
        list[str]
            Variable identifiers from all selected datasets.
        """
        variables = []
        for dataset in selected_datasets:
            dataset_variables = dataset_config[dataset]["variables"]
            variables.extend(dataset_variables)

        return variables

    dataset_widget = await dataset_selector(client=client)
    variable_widget = await variable_selector(client=client)

    variable_widget.children[2].on_click(variable_update_on_button_clicked)

    return dataset_widget, variable_widget


async def dataset_selector(client: ApiClient) -> widgets.SelectMultiple:
    """
    Create a dataset selection widget.

    Parameters
    ----------
    client : ApiClient
        Authenticated API client.

    Returns
    -------
    widgets.SelectMultiple
        Multi-select widget populated with dataset identifiers.
    """
    datasets = _load_dataset_yaml()

    dataset_list = _parse_datasets(datasets)

    dataset_label = widgets.Label(value="Select Datasets:", layout=widgets.Layout(width="30%"))
    dataset_selection = widgets.SelectMultiple(
        options=dataset_list,
        rows=10,
        disabled=False,
        layout=widgets.Layout(width="95%"),
    )

    return widgets.VBox(
        [
            dataset_label,
            dataset_selection,
        ],
        layout=widgets.Layout(width="90%", margin="0rem 2rem 0rem 0rem"),
    )


async def variable_selector(client: ApiClient) -> widgets.SelectMultiple:
    """
    Create a variable selection widget.

    Parameters
    ----------
    client : ApiClient
        Authenticated API client.

    Returns
    -------
    widgets.SelectMultiple
        Multi-select widget populated with variable identifiers.
    """
    variables = []

    variable_label = widgets.Label(value="Select Variables:", layout=widgets.Layout(width="90%"))
    variable_selection = widgets.SelectMultiple(
        options=variables,
        rows=10,
        disabled=False,
        layout=widgets.Layout(width="95%"),
    )
    variable_button = widgets.Button(
        description="Update variables",
        disabled=False,
        button_style="info",  # 'success', 'info', 'warning', 'danger' or ''
        tooltip="Click me",
    )

    return widgets.VBox(
        [
            variable_label,
            variable_selection,
            variable_button,
        ],
        layout=widgets.Layout(width="90%", margin="0rem 2rem 0rem 0rem"),
    )


def analysis_type_selector() -> widgets.ToggleButtons:
    """
    Create an analysis type toggle widget.

    Returns
    -------
    widgets.ToggleButtons
        Toggle buttons for the supported analysis modes.
    """
    return widgets.HBox(
        [
            widgets.Label(value="Select Analysis Type: "),
            widgets.ToggleButtons(
                options=["Correlation", "Cross-Correlation", "Granger Causality"],
                disabled=False,
                button_style="info",  # 'success', 'info', 'warning', 'danger' or ''
                layout=widgets.Layout(width="80%"),
            ),
        ],
        layout=widgets.Layout(margin="1rem 0rem 1rem 0rem"),
    )


def time_range_selector() -> widgets.HBox:
    """Create a time range selection widget group.

    Returns
    -------
    widgets.HBox
        Container with start and end datetime text inputs.
    """
    min_date = datetime(2010, 1, 1, tzinfo=pytz.UTC)
    max_date = datetime.now(pytz.UTC)
    max_date = datetime(max_date.year, max_date.month, max_date.day, tzinfo=pytz.UTC)

    start_time_label = widgets.Label(value="Pick a start datetime:")

    start_time_widget = widgets.Text(value="", placeholder="YYYY-MM-DD HH:MM:SS", disabled=False)

    end_time_label = widgets.Label(value="Pick an end datetime:")

    # end_time_widget = widgets.DatetimePicker(description="", disabled=False, min=min_date, max=max_date)
    end_time_widget = widgets.Text(value="", placeholder="YYYY-MM-DD HH:MM:SS", disabled=False)

    start_time_widget.value = min_date.strftime("%Y-%m-%d %H:%M:%S")
    end_time_widget.value = max_date.strftime("%Y-%m-%d %H:%M:%S")

    time_picker_container = [start_time_label, start_time_widget, end_time_label, end_time_widget]

    return widgets.Box(time_picker_container)


def widget_credentials_make() -> widgets.Box:
    """
    Create a credential entry widget group.

    Returns
    -------
    widgets.Box
        Container holding the token input, submit button, and output area.
    """

    def on_button_clicked(b: LoadedButton) -> None:
        """
        Authenticate the entered token and store the client on the button.

        Parameters
        ----------
        b : LoadedButton
            Button receiving the authenticated client in its ``value`` attribute.
        """
        with credentials_output:
            credentials_output.clear_output()
            if credentials_input.value.strip() == "":
                print("Please enter an API token before submitting.")  # noqa: T201
            else:
                print("API token submitted...")  # noqa: T201

                b.value = authenticate_with_token(credentials_input.value.strip())

    credentials_input = widgets.Textarea(
        value="",
        placeholder="Paste your API token here...",
        description="API token:",
        disabled=False,
        layout=widgets.Layout(width="50%", height="8rem"),
    )

    credentials_button = LoadedButton(
        description="submit API token",
        disabled=False,
        button_style="info",
        tooltip="",
        icon="",
    )

    credentials_output = widgets.Output()
    credentials_button.on_click(on_button_clicked)

    credentials_container = [credentials_input, credentials_button, credentials_output]
    display(widgets.Box(credentials_container))
    return widgets.Box(credentials_container)



def get_client(credentials_container: widgets.Box) -> ApiClient:
    """Extract an authenticated API client from the credentials widget.

    Parameters
    ----------
    credentials_container : widgets.Box
        Credential widget container returned by `widget_credentials_make`.

    Returns
    -------
    ApiClient
        Authenticated API client stored on the submit button.
    """
    return credentials_container.children[1].value


def get_ice_shelf(input_selector: widgets.VBox) -> str:
    """Read the selected ice shelf identifier from the input widget.

    Parameters
    ----------
    input_selector : widgets.VBox
        Input selector container built for covariate analysis.

    Returns
    -------
    str
        Selected ice shelf identifier.
    """
    return input_selector.children[0].children[0].children[1].value


def get_time_range(input_selector: widgets.VBox) -> tuple:
    """Read selected start and end datetimes from the input widget.

    Parameters
    ----------
    input_selector : widgets.VBox
        Input selector container built for covariate analysis.

    Returns
    -------
    tuple
        Start and end datetime strings in ``YYYY-MM-DD HH:MM:SS`` format.
    """
    start_time = input_selector.children[2].children[0].children[1].value
    end_time = input_selector.children[2].children[0].children[3].value
    return start_time, end_time


def get_analysis_type(input_selector: widgets.VBox) -> str:
    """Read the selected analysis type label from the input widget.

    Parameters
    ----------
    input_selector : widgets.VBox
        Input selector container built for covariate analysis.

    Returns
    -------
    str
        Selected analysis type label.
    """
    return input_selector.children[1].children[0].children[1].value


def get_input_datasets(input_selector: widgets.VBox) -> list[str]:
    """Read selected dataset labels from the input widget.

    Parameters
    ----------
    input_selector : widgets.VBox
        Input selector container built for covariate analysis.

    Returns
    -------
    list[str]
        Selected human-readable dataset labels.
    """
    return input_selector.children[0].children[1].children[1].value


def get_variables(input_selector: widgets.VBox) -> list[str]:
    """Build selected variables as API request objects.

    Parameters
    ----------
    input_selector : widgets.VBox
        Input selector container built for covariate analysis.

    Returns
    -------
    list[str]
        Selected variables represented as `VariableItem` objects.
    """
    dataset_config = _load_dataset_yaml()
    datasets = get_input_datasets(input_selector)
    variables = input_selector.children[0].children[2].children[1].value
    variable_mapping = []
    for dataset in datasets:
        dataset = _pretty_dataset_name_to_dataset_name(dataset)
        variable_checks = {}
        for variable in variables:
            if variable in dataset_config[dataset]["variables"] and variable not in variable_checks:
                name = (
                    f"{dataset_config[dataset]['label']}: "
                    f"{dataset_config[dataset]['variables'][variable]['label']} "
                    f"[{dataset_config[dataset]['variables'][variable]['units']}]"
                )
                variable_mapping.append(
                    VariableItem(
                        name=name, dataset=dataset, variable=variable, extent=dataset_config[dataset]["region"]
                    )
                )

                variable_checks[variable] = True

    return variable_mapping


async def build_covariate_analysis_input_selector(client: ApiClient) -> widgets.VBox:
    """
    Create a widget group for selecting covariate analysis inputs.

    Parameters
    ----------
    client : ApiClient
        Authenticated API client.

    Returns
    -------
    widgets.VBox
        Container holding the ice shelf selector, dataset selector, variable selector, and analysis type selector.
    """
    ice_shelf_widget = await ice_shelf_selector(client=client)
    dataset_widget, variable_widget = await display_datasets_and_variables(client=client)

    input_selector_row1 = widgets.HBox([ice_shelf_widget, dataset_widget, variable_widget])

    input_selector_row2 = widgets.HBox([analysis_type_selector()])

    input_selector_row3 = widgets.HBox([time_range_selector()])

    input_selector = widgets.VBox([input_selector_row1, input_selector_row2, input_selector_row3])

    display(input_selector)  # noqa: F821

    return input_selector


def _get_analysis_type(input_selector: widgets.VBox) -> CovariateAnalysisType:
    """Convert selected analysis label to API enum value.

    Parameters
    ----------
    input_selector : widgets.VBox
        Input selector container built for covariate analysis.

    Returns
    -------
    CovariateAnalysisType
        Analysis type enum required by the API.

    Raises
    ------
    ValueError
        If the selected analysis label is unsupported.
    """
    analysis_type_str = input_selector.children[1].children[0].children[1].value
    if analysis_type_str == "Correlation":
        return CovariateAnalysisType.CORR
    elif analysis_type_str == "Cross-Correlation":
        return CovariateAnalysisType.CROSS_CORR
    elif analysis_type_str == "Granger Causality":
        return CovariateAnalysisType.CAUSAL
    else:
        raise ValueError(f"Unsupported analysis type: {analysis_type_str}")


async def run_data_linkage_analysis(client: ApiClient, input_selector: widgets.VBox) -> dict:
    """Run covariate analysis and return plotting data.

    Parameters
    ----------
    client : ApiClient
        Authenticated API client.
    input_selector : widgets.VBox
        Input selector container built for covariate analysis.

    Returns
    -------
    dict
        Parsed JSON payload containing covariate analysis results.
    """
    variable_mapping = get_variables(input_selector)

    analysis_type = _get_analysis_type(input_selector)
    res = await StateAndFateApi(client).run_covariate_analysis(
        ice_shelf_id=get_ice_shelf(input_selector),
        covariate_analysis_request=CovariateAnalysisRequest(
            start_time=datetime.strptime(get_time_range(input_selector)[0], "%Y-%m-%d %H:%M:%S"),
            end_time=datetime.strptime(get_time_range(input_selector)[1], "%Y-%m-%d %H:%M:%S"),
            variables=variable_mapping,
            analysis_type=analysis_type,
        ),
    )

    res = await wait_for_job(client=client, job_id=res.job_id)

    output_url = res.outputs["use-case-3-covariate-analyser"]["output_json"]
    r = requests.get(output_url, timeout=10)
    r.raise_for_status()
    plot_data = r.json()

    return plot_data


async def extract_timeseries_data(client: ApiClient, input_selector: widgets.VBox) -> dict:
    """Extract per-variable time series from covariate analysis responses.

    Parameters
    ----------
    client : ApiClient
        Authenticated API client.
    input_selector : widgets.VBox
        Input selector container built for covariate analysis.

    Returns
    -------
    dict
        Mapping of measurement names to pandas time series.
    """
    variable_mapping = get_variables(input_selector)
    results_output = {}
    results = []
    for variable in variable_mapping:
        res = await StateAndFateApi(client).run_covariate_analysis(
            ice_shelf_id=get_ice_shelf(input_selector),
            covariate_analysis_request=CovariateAnalysisRequest(
                start_time=datetime.strptime(get_time_range(input_selector)[0], "%Y-%m-%d %H:%M:%S"),
                end_time=datetime.strptime(get_time_range(input_selector)[1], "%Y-%m-%d %H:%M:%S"),
                variables=[variable],
                analysis_type=CovariateAnalysisType("corr"),
            ),
        )

        res = await wait_for_job(client=client, job_id=res.job_id)

        output_url = res.outputs["use-case-3-covariate-analyser"]["output_json"]
        r = requests.get(output_url, timeout=10)
        r.raise_for_status()
        results.append(r.json())

    for i, result_var in enumerate(results):
        dataset = variable_mapping[i].dataset
        timestamps = result_var["variables"][list(result_var["variables"].keys())[0]]["timestamps"]
        values = result_var["variables"][list(result_var["variables"].keys())[0]]["values"]
        measurement_name = result_var["variables"][list(result_var["variables"].keys())[0]]["measurement_name"]
        results_output[measurement_name + f"_{i}"] = (
            pd.Series(
                values,
                index=pd.to_datetime(timestamps),
                name=measurement_name,
            ),
            dataset,
        )

    return results_output


def customwrap(s: str, width: int = 16, separator: str = "<br>") -> str:
    """Wrap text to specified width with custom line separator.

    Break long strings into multiple lines at word boundaries, using a
    specified separator for line breaks.

    Parameters
    ----------
    s : str
        String to wrap.
    width : int, optional
        Maximum line width in characters. Default is 16.
    separator : str, optional
        String to use for line breaks. Default is "<br>".

    Returns
    -------
    str
        Wrapped string with line breaks at word boundaries.
    """
    return separator.join(textwrap.wrap(s, width=width))


def plot_covariate_analysis(
    plot_data: dict, analysis_type: CovariateAnalysisType, plot_height: int = 1000, plot_width: int = 1000
) -> go.Figure:
    """Create a matrix plot visualizing covariate relationships.

    Generate a comprehensive scatter plot matrix showing pairwise relationships
    between variables, with marginal histograms and statistical annotations.

    Parameters
    ----------
    plot_data : dict
        Dictionary containing variable data, histograms, and covariate statistics.
    analysis_type : CovariateAnalysisType
        Type of analysis to determine which statistics to display.

    Returns
    -------
    go.Figure
        Plotly figure with scatter matrix, marginal distributions, and
        statistical annotations.
    """
    colors = qualitative.Plotly
    labels = list(plot_data["variables"].keys())
    datas = [plot_data["variables"][label] for label in labels]

    # The labels have form "dataset name: variable name [units]".
    # Separate the units to a separate list for later reattachment.
    split = list(zip(*[label.rsplit(" [", 1) for label in labels], strict=True))
    titles = split[0]
    units = ["[" + x for x in split[1]]

    # Remove the dataset name, unless it would cause duplicate labels.
    labels_without_prefix = [title.split(": ", 1)[1] for title in titles]
    titles = labels_without_prefix if len(set(labels_without_prefix)) == len(labels) else labels

    # Wrap titles to a fixed width, and then reattach units on a newline.
    titles = [customwrap(title, width=14) + "<br>" + unit for title, unit in zip(titles, units, strict=True)]

    fig = make_subplots(
        len(labels) + 1,
        len(labels) + 1,
        row_titles=titles,
        column_titles=titles,
        shared_xaxes=True,
        shared_yaxes=True,
        vertical_spacing=0.02,
        horizontal_spacing=0.02,
    )

    for idx, data in enumerate(datas):
        edge_starts = data["hist_edges"][:-1]
        edge_ends = data["hist_edges"][1:]
        widths = [b - a for a, b in zip(edge_starts, edge_ends, strict=True)]
        y = data["hist_values"]
        fig.add_trace(
            go.Bar(
                x=edge_starts,
                customdata=edge_ends,
                width=widths,
                y=y,
                offset=0,
                orientation="v",
                marker={"color": colors[1]},
                hovertemplate=f"<b>%{{x:.2f}} to %{{customdata:.2f}}: </b> %{{y}}<extra>{titles[idx]}</extra>",
            ),
            row=len(labels) + 1,
            col=idx + 1,
        )
        fig.add_trace(
            go.Bar(
                y=edge_starts,
                customdata=edge_ends,
                width=widths,
                x=y,
                offset=0,
                orientation="h",
                marker={"color": colors[1]},
                hovertemplate=f"<b>%{{y:.2f}} to %{{customdata:.2f}}: </b> %{{x}}<extra>{titles[idx]}</extra>",
            ),
            row=idx + 1,
            col=len(labels) + 1,
        )

    for a_idx, a_label in enumerate(labels):
        for b_idx, b_label in enumerate(labels):
            if a_idx == b_idx:
                continue
            a_data, b_data = (
                plot_data["variables"][a_label],
                plot_data["variables"][b_label],
            )
            fig.add_trace(
                go.Scatter(
                    x=a_data["values"],
                    y=b_data["values"],
                    mode="markers",
                    marker={"color": colors[0]},
                    hovertemplate=(
                        f"<b>{titles[a_idx]}:</b> %{{x:.2f}}<br><b>{titles[b_idx]}:</b> %{{y:.2f}}<extra></extra>"
                    ),
                ),
                row=b_idx + 1,
                col=a_idx + 1,
            )
            if analysis_type == CovariateAnalysisType.CAUSAL:
                stats = plot_data["covariate_stats"].get(
                    f"{a_label}/{b_label}",
                    {},
                )
            else:
                stats = plot_data["covariate_stats"].get(
                    f"{a_label}/{b_label}",
                    plot_data["covariate_stats"].get(
                        f"{b_label}/{a_label}",
                        {},
                    ),
                )
            axes_id = a_idx + b_idx * (len(labels) + 1) + 1
            axes_name = str(axes_id) if axes_id > 0 else ""
            fig.add_annotation(
                text="<br>".join(
                    [f"<b>{customwrap(k)}:</b> {round(v, 2) if isinstance(v, float) else v}" for k, v in stats.items()]
                ),
                xref=f"x{axes_name} domain",
                yref=f"y{axes_name} domain",
                x=0.01,
                y=0.99,
                showarrow=False,
                align="left",
                bgcolor="white",
                borderpad=5,
                opacity=0.9,
            )

    for i in range(len(labels) + 1):
        fig.add_trace(go.Scatter(), row=i + 1, col=i + 1)

    fig.update_layout(
        height=plot_height,
        width=plot_width,
        showlegend=False,
    )
    return fig


def plot_timeseries_data(timeseries_data: dict, pretty_labels: bool = True) -> go.Figure:
    """Create a time series plot for multiple variables.

    Generate a line plot showing the time series data for each variable,
    with appropriate labels and legends.

    Parameters
    ----------
    timeseries_data : dict
        Dictionary containing variable names and their corresponding time series values.

    Returns
    -------
    go.Figure
        Plotly figure with time series lines for each variable.
    """
    colors = qualitative.Plotly
    fig = go.Figure()

    for idx, (variable_name, values) in enumerate(timeseries_data.items()):
        units = _var_name_units("_".join(variable_name.split("_")[:-1]), dataset=values[1])
        values = values[0]
        fig.add_trace(
            go.Scatter(
                x=values.index,
                y=values,
                mode="lines+markers",
                name=_var_name_to_pretty_var_name("_".join(variable_name.split("_")[:-1])) + f" ({units})"
                if pretty_labels is not None
                else variable_name,
                line={"color": colors[idx % len(colors)]},
            )
        )

    fig.update_layout(
        xaxis_title="Time",
        yaxis_title="Data Values",
        height=600,
        width=800,
    )

    return fig
