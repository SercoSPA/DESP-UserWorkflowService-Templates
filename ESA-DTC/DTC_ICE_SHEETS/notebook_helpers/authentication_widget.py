"""
authentication_widget.py.

Widget for entering a DTC Ice Sheets API token in a notebook.

Usage (in a notebook cell)::

    from notebook_helpers.authentication_widget import request_api_token

    token_widget = request_api_token()

The token is checked when the user presses "Submit". The cell itself does not wait for this, so the user is
asked to run the next cell once the token has been accepted.

If the ``DTC_API_TOKEN`` environment variable is set, its token is filled in and checked automatically. Use this
in VS Code, which does not support pasting into the input box.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import ipywidgets as widgets
import dtc_query_client
from dtc_query_client import ApiClient, ApiResponse, Configuration
from dtc_query_client.exceptions import ApiException
from IPython.display import display

from .cell_spinner import BusyIndicator

API_HOST = "https://query.dtc-ice-sheets.org"
TOKEN_URL = f"{API_HOST}/auth/get-token"
TOKEN_ENV_VAR = "DTC_API_TOKEN"

LABEL_HTML = (
    f'API token (<a href="{TOKEN_URL}" target="_blank" rel="noopener noreferrer" '
    'style="color:var(--jp-content-link-color,#1976d2);text-decoration:underline">login here</a>):'
)
PLACEHOLDER = "paste your API token here..."
SUBMIT_TEXT = "Submit"
EMPTY_TOKEN_MESSAGE = "Please paste an API token before submitting."
CHECKING_MESSAGE = "Checking API token"
VALID_TOKEN_MESSAGE = "API token is valid. Please continue by running the next cell."
INVALID_TOKEN_MESSAGE = "API token not authenticated, please try again"
CHECK_TIMEOUT_S = 5.0
TIMEOUT_MESSAGE = (
    f"The API did not respond within {CHECK_TIMEOUT_S:g} s, please try again"
)


async def check_api_token(client: ApiClient) -> ApiResponse:
    """
    Make a request to the DTC Query API with ``client`` and return the response.

    Parameters
    ----------
    client : ApiClient
        DTC Query API client configured with the API token to check.

    Returns
    -------
    ApiResponse
        The response, also for error status codes (e.g. 401 for an invalid token). Its ``raw_data`` holds the
        response body, which contains the error message.

    Raises
    ------
    Exception
        If the request failed without a response (e.g. a network error).
    """
    api_instance = dtc_query_client.SeaLevelResponseApi(api_client=client)
    try:
        return await api_instance.get_mass_balance_with_http_info(
            "greenland", _request_timeout=CHECK_TIMEOUT_S
        )
    except ApiException as e:
        if e.status is None:
            raise
        return ApiResponse(
            status_code=e.status,
            headers=None,
            data=None,
            raw_data=(e.body or e.reason or "").encode(),
        )


def response_message(response: ApiResponse) -> str:
    """
    Return the message of an API response, e.g. ``"Invalid authentication token."``.

    Parameters
    ----------
    response : ApiResponse
        The API response.

    Returns
    -------
    str
        The ``detail`` of a JSON error body, otherwise the body text, otherwise the status code.
    """
    text = response.raw_data.decode(errors="replace").strip()
    try:
        detail = json.loads(text).get("detail")
    except (ValueError, AttributeError):
        detail = None
    return str(detail or text or f"HTTP {response.status_code}")


class ApiTokenWidget(widgets.VBox):
    """
    Widget made of a label (with a login link), a token input box, a submit button and a status message.

    The status message is a :class:`BusyIndicator`, so it shows a spinner while the token is being checked.
    Once a valid token has been submitted, ``dtc_client`` holds an :class:`ApiClient` authenticated with it.
    """

    dtc_client: ApiClient | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.label = widgets.HTML(value=LABEL_HTML)
        self.token_input = widgets.Text(
            value="", placeholder=PLACEHOLDER, layout=widgets.Layout(width="400px")
        )
        self.submit_button = widgets.Button(
            description=SUBMIT_TEXT, button_style="success"
        )
        self.status = BusyIndicator()
        self.token: str | None = None
        self._check_task: asyncio.Future | None = None

        self.submit_button.on_click(self._on_submit)
        super().__init__(
            children=[
                widgets.HBox([self.label, self.token_input, self.submit_button]),
                self.status,
            ],
            **kwargs,
        )

    @property
    def is_authenticated(self) -> bool:
        """Return True once a valid token has been submitted."""
        return self.token is not None

    def _on_submit(self, _button: widgets.Button) -> None:
        self.submit()

    def submit(self) -> None:
        """Check the token in the input box, as if the "Submit" button had been pressed."""
        token = self.token_input.value.strip()
        if not token:
            self.status.stop(EMPTY_TOKEN_MESSAGE)
            return

        previous_client = self.dtc_client
        self.token = None
        self.dtc_client = ApiClient(Configuration(host=API_HOST, access_token=token))
        check = self._check_token(token, previous_client)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(check)
        else:
            # The API client is async, so the check runs as a task on the kernel's event loop.
            self._check_task = asyncio.ensure_future(check)

    async def _check_token(self, token: str, previous_client: ApiClient | None) -> None:
        if previous_client is not None:
            await previous_client.close()
        try:
            with self.status(
                CHECKING_MESSAGE, disable=[self.token_input, self.submit_button]
            ):
                response = await check_api_token(self.dtc_client)
        except asyncio.TimeoutError:
            await self._discard_client()
            self.status.stop(TIMEOUT_MESSAGE)
            return
        except Exception:
            # The status message already shows the error.
            await self._discard_client()
            return

        if 200 <= response.status_code < 300:
            os.environ[TOKEN_ENV_VAR] = token
            self.token = token
            self.status.stop(VALID_TOKEN_MESSAGE)
        else:
            await self._discard_client()
            self.status.stop(
                f"{INVALID_TOKEN_MESSAGE} (response from DTC server: {response.status_code}: {response_message(response)})"
            )

    async def _discard_client(self) -> None:
        client, self.dtc_client = self.dtc_client, None
        if client is not None:
            await client.close()


def request_api_token() -> ApiTokenWidget:
    """
    Display the API token widget.

    A valid submitted token is stored in the ``DTC_API_TOKEN`` environment variable for use by the API helpers.
    If that variable is already set, its token is filled in and checked straight away. This also works around
    VS Code, where pasting into the widget's input box is not possible.

    Returns
    -------
    ApiTokenWidget
        The displayed widget.
    """
    token_widget = ApiTokenWidget()
    display(token_widget)
    env_token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if env_token:
        token_widget.token_input.value = env_token
        token_widget.submit()
    return token_widget
