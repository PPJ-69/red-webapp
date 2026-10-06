from dataclasses import dataclass
from enum import Enum
from threading import Lock


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    metric_type: MetricType


METRIC_DEFINITIONS = (
    MetricDefinition("stream_requests_total", MetricType.COUNTER),
    MetricDefinition("stream_bytes_forwarded_total", MetricType.COUNTER),
    MetricDefinition("stream_active_connections", MetricType.GAUGE),
    MetricDefinition("stream_first_byte_ms", MetricType.HISTOGRAM),
    MetricDefinition("stream_upstream_errors_total", MetricType.COUNTER),
    MetricDefinition("direct_vs_relay_ratio", MetricType.GAUGE),
)


@dataclass
class _MetricValue:
    value: float = 0
    observations: int = 0
    maximum: float | None = None


class MetricsRegistry:
    def __init__(
        self, definitions: tuple[MetricDefinition, ...] = METRIC_DEFINITIONS
    ) -> None:
        self._definitions = {definition.name: definition for definition in definitions}
        if len(self._definitions) != len(definitions):
            raise ValueError("Metric names must be unique.")
        self._values = {name: _MetricValue() for name in self._definitions}
        self._lock = Lock()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._definitions)

    def increment(self, name: str, amount: float = 1) -> float:
        definition = self._definition(name, MetricType.COUNTER)
        if amount < 0:
            raise ValueError("Counters cannot be incremented by a negative amount.")
        with self._lock:
            value = self._values[definition.name]
            value.value += amount
            return value.value

    def set_gauge(self, name: str, value: float) -> None:
        definition = self._definition(name, MetricType.GAUGE)
        with self._lock:
            self._values[definition.name].value = value

    def observe(self, name: str, value: float) -> None:
        definition = self._definition(name, MetricType.HISTOGRAM)
        with self._lock:
            metric = self._values[definition.name]
            metric.value += value
            metric.observations += 1
            metric.maximum = value if metric.maximum is None else max(metric.maximum, value)

    def snapshot(self) -> dict[str, dict[str, float | int | None | str]]:
        with self._lock:
            result: dict[str, dict[str, float | int | None | str]] = {}
            for name, definition in self._definitions.items():
                metric = self._values[name]
                result[name] = {
                    "type": definition.metric_type.value,
                    "value": metric.value,
                }
                if definition.metric_type is MetricType.HISTOGRAM:
                    result[name]["count"] = metric.observations
                    result[name]["maximum"] = metric.maximum
            return result

    def _definition(self, name: str, expected_type: MetricType) -> MetricDefinition:
        try:
            definition = self._definitions[name]
        except KeyError as exc:
            raise KeyError(f"Metric {name!r} is not registered.") from exc
        if definition.metric_type is not expected_type:
            raise TypeError(
                f"Metric {name!r} is a {definition.metric_type.value}, "
                f"not a {expected_type.value}."
            )
        return definition


metrics = MetricsRegistry()
