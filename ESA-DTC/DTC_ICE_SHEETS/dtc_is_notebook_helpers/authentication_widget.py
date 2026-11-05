"""
authentication_widget.py.

Widget for entering a DTC Ice Sheets API token in a notebook.

Usage (in a notebook cell)::

    from notebook_helpers.authentication_widget import request_api_token

    token_widget = request_api_token()
    await token_widget.wait_until_authenticated()

The token is checked when the user presses "Submit". Awaiting authentication keeps the cell running until
a token is accepted, without blocking widget interactions.

Each call to ``request_api_token`` clears the ``DTC_API_TOKEN`` environment variable and starts fresh.
To provide a token up front, use ``request_api_token(token=your_token)``; it is checked automatically.
Without an explicit token, the widget starts empty and unauthenticated.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import dtc_query_client
import ipywidgets as widgets
from dtc_query_client import ApiClient, ApiResponse, Configuration
from dtc_query_client.exceptions import ApiException
from ipykernel import version_info as kernel_version
from IPython import get_ipython
from IPython.display import display
from jupyter_ui_poll import ui_events

from .cell_spinner import BusyIndicator, suppress_cell_spinner

API_HOST = "https://query.dtc-ice-sheets.org"
TOKEN_URL = f"{API_HOST}/auth/get-token"
DTC_API_TOKEN_ENV_NAME = "DTC_API_TOKEN"  # noqa: S105 - this is the environment variable name, not the token itself.

LABEL_HTML = (
    f'<span style="color:var(--jp-ui-font-color1,CanvasText)">API token '
    f'(<a href="{TOKEN_URL}" target="_blank" rel="noopener noreferrer" '
    'style="color:var(--jp-content-link-color,#1976d2);text-decoration:underline">login here</a>):'
    "</span>"
)
CHECK_TIMEOUT_S = 5.0
TOKEN_INPUT_PLACEHOLDER = "paste your API token here..."  # noqa: S105 - placeholder text, not a credential.
AUTHENTICATED_PLACEHOLDER = "token submitted, to submit another token please rerun the cell first."


class _CredentialInput(widgets.Password):
    """Password input that omits its value from full widget-state snapshots."""

    def get_state(self, key: str | None = None, drop_defaults: bool = False) -> dict[str, Any]:
        state = super().get_state(key=key, drop_defaults=drop_defaults)
        if key is None:
            state.pop("value", None)
        return state


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
        return await api_instance.get_mass_balance_with_http_info("greenland", _request_timeout=CHECK_TIMEOUT_S)
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

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401  # VBox accepts arbitrary trait options.
        self.label = widgets.HTML(value=LABEL_HTML)
        self.token_input = _CredentialInput(
            value="", placeholder=TOKEN_INPUT_PLACEHOLDER, layout=widgets.Layout(width="400px")
        )
        self.submit_button = widgets.Button(description="Submit", button_style="success")
        self.status = BusyIndicator()
        self.token: str | None = None
        self._check_task: asyncio.Future | None = None
        self._authenticated = asyncio.Event()

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

    def get_client(self) -> ApiClient:
        """Return the API client, or Raise an error if it doesn't exist."""
        if self.dtc_client is None:
            raise RuntimeError("API client is not authenticated.")
        return self.dtc_client

    async def wait_until_authenticated(self) -> None:
        """Wait for a valid token, allowing widget interactions and retries while waiting."""
        if self._authenticated.is_set():
            return
        with suppress_cell_spinner():
            shell = get_ipython()
            if shell is None or getattr(shell, "kernel", None) is None or kernel_version >= (7, 4):
                await self._authenticated.wait()
                return

            # Older kernels queue widget messages behind the currently executing cell.
            async with ui_events() as poll:
                while not self._authenticated.is_set():
                    await poll(10)
                    await asyncio.sleep(0.05)

    def _on_submit(self, _button: widgets.Button) -> None:
        self.submit()

    def submit(self, token: str | None = None) -> None:
        """Check the token in the input box, as if the "Submit" button had been pressed."""
        # Debounce - if a token check is already in progress, do not start another one.
        if self._check_task is not None and not self._check_task.done():
            return
        token = (self.token_input.value if token is None else token).strip()
        self.token_input.value = ""
        if not token:
            self.status.stop("Please paste an API token before submitting.")
            return

        previous_client = self.dtc_client
        self.token = None
        self._authenticated.clear()
        os.environ.pop(DTC_API_TOKEN_ENV_NAME, None)
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
            with self.status("Checking API token", disable=[self.token_input, self.submit_button]):
                response = await check_api_token(self.dtc_client)
        except asyncio.TimeoutError:
            await self._discard_client()
            self.status.stop(f"The API did not respond within {CHECK_TIMEOUT_S:g} s, please try again")
            return
        except Exception:
            # The status message already shows the error.
            await self._discard_client()
            return

        if 200 <= response.status_code < 300:
            os.environ[DTC_API_TOKEN_ENV_NAME] = token
            self.token = token
            self.token_input.placeholder = AUTHENTICATED_PLACEHOLDER
            self.status.stop("✅ API token is valid. Please continue by running the next cell.")
            self._authenticated.set()
        else:
            await self._discard_client()
            self.status.stop(
                "❌ API token not authenticated, please try again "
                f"(response from DTC server: {response.status_code}: {response_message(response)})"
            )

    async def _discard_client(self) -> None:
        client, self.dtc_client = self.dtc_client, None
        if client is not None:
            await client.close()


def request_api_token(token: str | None = None) -> ApiTokenWidget:
    """
    Clear the saved environment token and display a fresh API token widget.

    A valid submitted token is stored in the ``DTC_API_TOKEN`` environment variable for use by the API helpers.
    Each call clears that variable. An explicitly supplied token is filled in and checked automatically;
    otherwise the input starts empty, requiring a new submission.
    Previously returned API clients are not revoked.

    Parameters
    ----------
    token : str | None, optional
        Token to check immediately. If omitted or blank, display an empty widget.

    Returns
    -------
    ApiTokenWidget
        The displayed widget.
    """
    os.environ.pop(DTC_API_TOKEN_ENV_NAME, None)
    token_widget = ApiTokenWidget()
    display(token_widget)
    if token and token.strip():
        token_widget.submit(token.strip())
    return token_widget
