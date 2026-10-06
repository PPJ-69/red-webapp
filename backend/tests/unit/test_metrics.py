import unittest

from backend.app.observability.metrics import (
    METRIC_DEFINITIONS,
    MetricDefinition,
    MetricType,
    MetricsRegistry,
)


class MetricsRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metrics = MetricsRegistry()

    def test_predeclares_plan_metrics(self) -> None:
        self.assertEqual(
            set(self.metrics.names),
            {definition.name for definition in METRIC_DEFINITIONS},
        )

    def test_counter_gauge_and_histogram_operations(self) -> None:
        self.assertEqual(self.metrics.increment("stream_requests_total"), 1)
        self.metrics.increment("stream_bytes_forwarded_total", 256)
        self.metrics.set_gauge("stream_active_connections", 2)
        self.metrics.observe("stream_first_byte_ms", 12.5)
        self.metrics.observe("stream_first_byte_ms", 20)

        snapshot = self.metrics.snapshot()

        self.assertEqual(snapshot["stream_requests_total"]["value"], 1)
        self.assertEqual(snapshot["stream_bytes_forwarded_total"]["value"], 256)
        self.assertEqual(snapshot["stream_active_connections"]["value"], 2)
        self.assertEqual(snapshot["stream_first_byte_ms"]["value"], 32.5)
        self.assertEqual(snapshot["stream_first_byte_ms"]["count"], 2)
        self.assertEqual(snapshot["stream_first_byte_ms"]["maximum"], 20)

    def test_rejects_unregistered_metrics_and_wrong_operations(self) -> None:
        with self.assertRaisesRegex(KeyError, "not registered"):
            self.metrics.increment("unknown_metric")
        with self.assertRaisesRegex(TypeError, "not a gauge"):
            self.metrics.set_gauge("stream_requests_total", 1)
        with self.assertRaisesRegex(ValueError, "negative"):
            self.metrics.increment("stream_requests_total", -1)

    def test_rejects_duplicate_metric_definitions(self) -> None:
        definitions = (
            MetricDefinition("same_metric", MetricType.COUNTER),
            MetricDefinition("same_metric", MetricType.GAUGE),
        )

        with self.assertRaisesRegex(ValueError, "unique"):
            MetricsRegistry(definitions)


if __name__ == "__main__":
    unittest.main()
