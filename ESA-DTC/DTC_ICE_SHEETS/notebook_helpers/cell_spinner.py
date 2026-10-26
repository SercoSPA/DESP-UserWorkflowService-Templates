"""
cell_spinner.py.

"Still running" animations for Jupyter notebooks.

This module is self-contained (it only needs IPython, plus ipywidgets for ``BusyIndicator``) and can be
copied as-is into other notebook projects. The animation is pure HTML/CSS, so no frontend extension or
JavaScript is required.

Two complementary tools are provided:

1. **Cell spinner** - once enabled, every cell that runs for longer than a short delay shows an animated
   spinner at the bottom of its output. The spinner follows new output (prints, plots, widgets) so it stays
   at the bottom, and is removed as soon as the cell completes::

       %load_ext notebook_helpers.cell_spinner
       # or: from notebook_helpers.cell_spinner import enable_cell_spinner; enable_cell_spinner()

   The text next to the spinner can be changed while the cell runs::

       from notebook_helpers.cell_spinner import set_message
       set_message("Downloading data...")

2. **BusyIndicator** - a widget for work that runs in widget callbacks (e.g. ``Button.on_click``), which
   happens *after* the cell itself has completed and is therefore not covered by the cell spinner::

       from notebook_helpers.cell_spinner import BusyIndicator

       status = BusyIndicator()

       @status.track("Processing...", disable=[button])
       def on_click(b):
           ...
           status.update("Almost done...")

       button.on_click(on_click)
       display(button, status)
"""

from __future__ import annotations

import contextvars
import functools
import html
import sys
import threading
from collections.abc import Callable, Generator, Iterable
from contextlib import contextmanager
from typing import Any

from IPython import get_ipython
from IPython.display import display

try:
    import ipywidgets as _widgets
except ImportError:  # pragma: no cover - ipywidgets is optional for the cell spinner
    _widgets = None

DEFAULT_MESSAGE = "Running…"
# Cells finishing faster than this never show a spinner (avoids flicker and empty outputs).
SHOW_DELAY_S = 0.1
# Quiet period after new output before the spinner is moved back to the bottom.
MOVE_DEBOUNCE_S = 0.25

_CSS = (
    "<style>"
    ".nb-spinner{display:flex;align-items:center;gap:.6em;padding:4px 0;"
    "font-size:var(--jp-ui-font-size1,13px);color:var(--jp-ui-font-color2,#616161)}"
    ".nb-spinner__ring{width:14px;height:14px;flex:none;box-sizing:border-box;border-radius:50%;"
    "border:2px solid var(--jp-border-color2,#e0e0e0);border-top-color:var(--jp-brand-color1,#1976d2);"
    "animation:nb-spinner-rotate .8s linear infinite}"
    "@keyframes nb-spinner-rotate{to{transform:rotate(360deg)}}"
    "</style>"
)


def spinner_html(message: str = DEFAULT_MESSAGE) -> str:
    """
    Return the HTML for an animated spinner followed by a message.

    Parameters
    ----------
    message : str
        Text shown next to the spinner.

    Returns
    -------
    str
        Self-contained HTML snippet.
    """
    return (
        f'{_CSS}<div class="nb-spinner"><div class="nb-spinner__ring"></div><span>{html.escape(message)}</span></div>'
    )


def _output_widget_capturing() -> bool:
    """Return True if an ipywidgets ``Output`` context manager is currently capturing output."""
    if "ipywidgets" not in sys.modules:
        return False
    try:
        from ipywidgets.widgets.widget import _instances as instances
    except ImportError:  # ipywidgets < 8
        instances = getattr(sys.modules["ipywidgets"].Widget, "widgets", {})
    output_cls = sys.modules["ipywidgets"].Output
    return any(isinstance(w, output_cls) and w.msg_id for w in list(instances.values()))


class _CellSpinner:
    """Keep a spinner at the bottom of the output of the currently running cell."""

    def __init__(self, shell: Any, message: str = DEFAULT_MESSAGE) -> None:
        self.shell = shell
        self.default_message = message
        self.message = message
        self._lock = threading.RLock()
        self._local = threading.local()
        self._running = False
        self._handle = None
        self._clear_pending = False
        self._timer: threading.Timer | None = None
        self._display_pub = None
        self._patched: list[tuple[Any, str]] = []
        self._stream_patches: list[tuple[Any, Callable, Any]] = []

    # -- installation -------------------------------------------------------------------------------
    def install(self) -> None:
        """Register IPython event callbacks and output hooks."""
        self._display_pub = self.shell.display_pub
        self._patch(self._display_pub, "publish", self._wrap_publish)
        self._patch(self._display_pub, "clear_output", self._wrap_clear_output)
        self.shell.events.register("pre_run_cell", self._pre_run_cell)
        self.shell.events.register("post_run_cell", self._post_run_cell)

    def uninstall(self) -> None:
        """Remove IPython event callbacks and output hooks."""
        self._post_run_cell(None)
        self.shell.events.unregister("pre_run_cell", self._pre_run_cell)
        self.shell.events.unregister("post_run_cell", self._post_run_cell)
        for obj, name in self._patched:
            try:
                delattr(obj, name)
            except AttributeError:
                pass
        self._patched.clear()

    def _patch(self, obj: Any, name: str, wrapper_factory: Callable) -> None:
        setattr(obj, name, wrapper_factory(getattr(obj, name)))
        self._patched.append((obj, name))

    def _patch_streams(self) -> None:
        # IPython >= 9 wraps and restores ``stream.write`` around every cell, so streams are hooked per cell.
        self._stream_patches = []
        for stream in (sys.stdout, sys.stderr):
            previous = stream.__dict__.get("write") if hasattr(stream, "__dict__") else None
            try:
                stream.write = self._wrap_write(stream.write)
            except (AttributeError, TypeError):
                continue
            self._stream_patches.append((stream, stream.write, previous))

    def _unpatch_streams(self) -> None:
        for stream, wrapper, previous in self._stream_patches:
            if stream.__dict__.get("write") is not wrapper:
                continue
            if previous is None:
                del stream.write
            else:
                stream.write = previous
        self._stream_patches = []

    # -- output hooks -------------------------------------------------------------------------------
    @property
    def _is_own_output(self) -> bool:
        return getattr(self._local, "active", False)

    def _wrap_publish(self, original: Callable) -> Callable:
        def publish(data: dict, metadata: dict | None = None, *args: Any, **kwargs: Any) -> Any:
            result = original(data, metadata, *args, **kwargs)
            is_update = kwargs.get("update", args[1] if len(args) > 1 else False)
            if not is_update and not self._is_own_output:
                self._on_output()
            return result

        return publish

    def _wrap_clear_output(self, original: Callable) -> Callable:
        def clear_output(wait: bool = False) -> Any:
            result = original(wait)
            if not self._is_own_output and not _output_widget_capturing():
                with self._lock:
                    if self._running:
                        if wait:
                            # The spinner disappears together with the old output once new output arrives.
                            self._clear_pending = True
                        else:
                            self._handle = None
                            self._schedule_move(MOVE_DEBOUNCE_S)
            return result

        return clear_output

    def _wrap_write(self, original: Callable) -> Callable:
        def write(string: str) -> Any:
            result = original(string)
            if string and not self._is_own_output:
                self._on_output()
            return result

        return write

    def _on_output(self) -> None:
        if not self._running or _output_widget_capturing():
            return
        with self._lock:
            if not self._running:
                return
            if self._clear_pending:
                self._clear_pending = False
                self._handle = None
            # Before the initial delay has passed, keep the pending (longer) timer.
            if self._handle is not None or self._timer is None:
                self._schedule_move(MOVE_DEBOUNCE_S)

    # -- spinner management -------------------------------------------------------------------------
    def _schedule_move(self, delay: float) -> None:
        if self._timer is not None:
            self._timer.cancel()
        # Copying the context keeps the kernel's parent header, so the spinner lands in the right cell.
        context = contextvars.copy_context()
        self._timer = threading.Timer(delay, context.run, args=(self._move,))
        self._timer.daemon = True
        self._timer.start()

    def _move(self) -> None:
        with self._lock:
            self._timer = None
            if not self._running or self._clear_pending or self.shell.display_pub is not self._display_pub:
                return
            if _output_widget_capturing():
                self._schedule_move(MOVE_DEBOUNCE_S)
                return
            self._local.active = True
            try:
                # Flush pending text first so that it ends up above the spinner.
                for stream in (sys.stdout, sys.stderr):
                    stream.flush()
                self._hide()
                self._handle = display(self._bundle(), raw=True, display_id=True)
            finally:
                self._local.active = False

    def _bundle(self) -> dict[str, str]:
        return {"text/html": spinner_html(self.message), "text/plain": self.message}

    def _hide(self) -> None:
        if self._handle is not None:
            self._handle.update({"text/html": "", "text/plain": ""}, raw=True)
            self._handle = None

    def set_message(self, message: str | None) -> None:
        with self._lock:
            self.message = self.default_message if message is None else message
            if self._handle is not None and self._running:
                self._local.active = True
                try:
                    self._handle.update(self._bundle(), raw=True)
                finally:
                    self._local.active = False

    # -- IPython events -----------------------------------------------------------------------------
    def _pre_run_cell(self, info: Any) -> None:
        with self._lock:
            self._running = True
            self._handle = None
            self._clear_pending = False
            self.message = self.default_message
            self._patch_streams()
            self._schedule_move(SHOW_DELAY_S)

    def _post_run_cell(self, result: Any) -> None:
        with self._lock:
            self._running = False
            self._unpatch_streams()
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._local.active = True
            try:
                self._hide()
            finally:
                self._local.active = False


_spinner: _CellSpinner | None = None


def enable_cell_spinner(message: str = DEFAULT_MESSAGE) -> None:
    """
    Show an animated spinner at the bottom of every running cell from now on.

    Parameters
    ----------
    message : str
        Default text shown next to the spinner.
    """
    global _spinner
    shell = get_ipython()
    if shell is None or getattr(shell, "kernel", None) is None:
        print("cell_spinner: not running in a Jupyter kernel, spinner not enabled.")
        return
    if _spinner is not None:
        _spinner.default_message = message
        return
    _spinner = _CellSpinner(shell, message)
    _spinner.install()


def disable_cell_spinner() -> None:
    """Stop showing the cell spinner."""
    global _spinner
    if _spinner is not None:
        _spinner.uninstall()
        _spinner = None


def set_message(message: str | None = None) -> None:
    """
    Change the text next to the spinner of the currently running cell.

    Parameters
    ----------
    message : str or None
        New text. ``None`` restores the default message. Has no effect if the spinner is not enabled.
    """
    if _spinner is not None:
        _spinner.set_message(message)


def load_ipython_extension(shell: Any) -> None:
    """Enable the cell spinner via ``%load_ext``."""
    enable_cell_spinner()


def unload_ipython_extension(shell: Any) -> None:
    """Disable the cell spinner via ``%unload_ext``."""
    disable_cell_spinner()


class BusyIndicator(_widgets.HTML if _widgets is not None else object):
    """
    Widget showing a spinner while work triggered by a widget callback is running.

    Display it next to the controls that trigger the work, then wrap the callback with :meth:`track`
    (or use the instance as a context manager). Outside of busy periods it can show a plain message,
    e.g. a validation error.
    """

    def __init__(self, **kwargs: Any) -> None:
        if _widgets is None:
            raise ImportError("BusyIndicator requires ipywidgets.")
        super().__init__(**kwargs)
        self.busy = False

    def start(self, message: str = "Working…") -> None:
        """Show the spinner with ``message``."""
        self.busy = True
        self.value = spinner_html(message)

    def update(self, message: str) -> None:
        """Change the message, keeping the spinner if busy."""
        if self.busy:
            self.start(message)
        else:
            self.stop(message)

    def stop(self, message: str = "") -> None:
        """Hide the spinner, optionally leaving ``message`` in its place."""
        self.busy = False
        self.value = f'<div class="nb-spinner-message">{html.escape(message)}</div>' if message else ""

    @contextmanager
    def __call__(self, message: str = "Working…", disable: Iterable[Any] = ()) -> Generator[BusyIndicator, None, None]:
        """
        Show the spinner and disable ``disable`` widgets for the duration of the ``with`` block.

        If the block calls :meth:`stop` itself (e.g. to show an error), that message is kept.
        Exceptions are shown in the indicator and re-raised.
        """
        disable = list(disable)
        for widget in disable:
            widget.disabled = True
        self.start(message)
        try:
            yield self
        except Exception as e:
            self.stop(f"Error: {e}")
            raise
        else:
            if self.busy:
                self.stop()
        finally:
            for widget in disable:
                widget.disabled = False

    def track(self, message: str = "Working…", disable: Iterable[Any] = ()) -> Callable[[Callable], Callable]:
        """Wrap a (callback) function so that the indicator is busy while it runs."""

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                with self(message, disable):
                    return func(*args, **kwargs)

            return wrapper

        return decorator
