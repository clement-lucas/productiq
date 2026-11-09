"""OpenTelemetry → Application Insights (only when the connection string is set)."""
from __future__ import annotations

import contextlib
import logging
from typing import Any, Iterator

from .guardrails import redact_pii

log = logging.getLogger("productiq")
_tracer: Any = None


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_pii(str(record.msg))
        if record.args:
            record.args = tuple(redact_pii(str(a)) for a in record.args)
        return True


def configure(connection_string: str = "") -> None:
    global _tracer
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for h in logging.getLogger().handlers:
        h.addFilter(_RedactingFilter())
    if connection_string:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(connection_string=connection_string, logger_name="productiq")
        except ImportError:  # pragma: no cover
            log.warning("azure-monitor-opentelemetry not installed; telemetry disabled")
    try:
        from opentelemetry import trace

        _tracer = trace.get_tracer("productiq")
    except ImportError:
        _tracer = None


@contextlib.contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """Span if OpenTelemetry is available, otherwise a no-op. Attribute values are redacted."""
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(name) as s:
        for k, v in attributes.items():
            s.set_attribute(k, redact_pii(str(v)) if isinstance(v, str) else v)
        yield s
