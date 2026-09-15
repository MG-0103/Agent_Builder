"""Lightweight tracer for user ADK code.

Drop this in the user's runtime, wrap their callback kwargs with the
helpers here, and export the resulting spans as JSON. Post the JSON to
``/traces`` to overlay onto the static graph.

Not an OTel adapter — deliberately minimal, no threading, no network.
Real OTel spans can be adapted separately via ``observed_from_spans``
after mapping their kind and parent fields.
"""

from __future__ import annotations

import contextvars
import time
import uuid
from typing import Any, Callable

from .trace import Span, Trace


_current_span: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "adk_parser_current_span", default=None
)


class Tracer:
    """Collects spans in memory during a run.

    Usage sketch::

        tracer = Tracer()
        agent = LlmAgent(
            ...,
            before_agent_callback=tracer.wrap_agent_callback("agent_name"),
            before_tool_callback=tracer.wrap_tool_callback("agent_name"),
        )
        # run the agent
        json_payload = tracer.export()
        # POST json_payload to /traces
    """

    def __init__(self) -> None:
        self._spans: list[Span] = []

    # -- Internal ---------------------------------------------------------

    def _open(self, kind: str, name: str, attrs: dict[str, Any] | None = None) -> str:
        span_id = uuid.uuid4().hex[:12]
        parent = _current_span.get()
        self._spans.append(
            Span(
                id=span_id,
                kind=kind,  # type: ignore[arg-type]
                name=name,
                parent_id=parent,
                started_at=time.time(),
                attrs=attrs or {},
            )
        )
        return span_id

    def _close(self, span_id: str) -> None:
        for span in self._spans:
            if span.id == span_id:
                span.ended_at = time.time()
                return

    # -- Public wrappers --------------------------------------------------

    def wrap_agent_callback(
        self,
        agent_name: str,
        inner: Callable[..., Any] | None = None,
    ) -> Callable[..., Any]:
        """Return a callback that records an agent-span around ``inner``."""

        def _cb(*args: Any, **kwargs: Any) -> Any:
            span_id = self._open("agent", agent_name)
            token = _current_span.set(span_id)
            try:
                if inner is not None:
                    return inner(*args, **kwargs)
                return None
            finally:
                self._close(span_id)
                _current_span.reset(token)

        return _cb

    def wrap_tool_callback(
        self,
        agent_name: str,
        inner: Callable[..., Any] | None = None,
    ) -> Callable[..., Any]:
        """Return a before_tool_callback that emits a tool_call span whose
        parent is the currently-open agent span. ``agent_name`` is currently
        unused — ADK passes the invoking agent as an arg — but retained so
        users can annotate at wrap time."""

        def _cb(*args: Any, **kwargs: Any) -> Any:
            tool_name = kwargs.get("tool_name") or (args[1] if len(args) > 1 else "<unknown-tool>")
            span_id = self._open("tool_call", str(tool_name), attrs={"agent": agent_name})
            try:
                if inner is not None:
                    return inner(*args, **kwargs)
                return None
            finally:
                self._close(span_id)

        return _cb

    def wrap_named_callback(
        self,
        callback_name: str,
        inner: Callable[..., Any] | None = None,
    ) -> Callable[..., Any]:
        """Record a `callback` span so hook edges show up as observed."""

        def _cb(*args: Any, **kwargs: Any) -> Any:
            span_id = self._open("callback", callback_name)
            try:
                if inner is not None:
                    return inner(*args, **kwargs)
                return None
            finally:
                self._close(span_id)

        return _cb

    # -- Export -----------------------------------------------------------

    def trace(self) -> Trace:
        return Trace(spans=list(self._spans))

    def export(self) -> dict[str, Any]:
        return self.trace().model_dump()
