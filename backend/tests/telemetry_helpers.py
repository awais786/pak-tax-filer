"""The spans a telemetry test collected (feature 008, tasks T017, T018)."""

from collections.abc import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class CollectingExporter(InMemorySpanExporter):
    """Keeps spans only while a test collects them, so the rest of the run's aren't kept."""

    collecting = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Keep the spans while collecting; otherwise drop them."""
        if not self.collecting:
            return SpanExportResult.SUCCESS
        return super().export(spans)


class Spans:
    """The spans finished so far in this test."""

    def __init__(self, exporter: InMemorySpanExporter) -> None:
        self._exporter = exporter

    def all(self) -> list[ReadableSpan]:
        """Every finished span."""
        return list(self._exporter.get_finished_spans())

    def ai(self, feature: str | None = None) -> list[ReadableSpan]:
        """The AI-use spans (those with an `app.feature`), optionally for one feature."""
        return [
            span
            for span in self.all()
            if span.attributes
            and "app.feature" in span.attributes
            and span.attributes.get("gen_ai.operation.name") != "execute_tool"
            and (feature is None or span.attributes["app.feature"] == feature)
        ]
