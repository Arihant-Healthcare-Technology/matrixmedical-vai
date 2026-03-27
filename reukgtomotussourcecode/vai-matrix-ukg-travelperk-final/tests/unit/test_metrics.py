"""
Unit tests for metrics module.
Tests for SOW Requirements 4.7, 7.3 - Metrics collection.
"""
import sys
import time
import threading
import pytest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.metrics import (
    MetricValue,
    Counter,
    Gauge,
    Histogram,
    Timer,
    MetricsCollector,
    get_metrics_collector,
    reset_metrics,
)


class TestMetricValue:
    """Tests for MetricValue dataclass."""

    def test_create_metric_value(self):
        """Test creating a MetricValue."""
        value = MetricValue(name="test_metric", value=42.0)
        assert value.name == "test_metric"
        assert value.value == 42.0
        assert value.timestamp is not None
        assert value.tags == {}

    def test_create_with_tags(self):
        """Test creating MetricValue with tags."""
        tags = {"env": "prod", "region": "us-east-1"}
        value = MetricValue(name="test", value=10.0, tags=tags)
        assert value.tags == tags


class TestCounter:
    """Tests for Counter class."""

    def test_init(self):
        """Test counter initialization."""
        counter = Counter("test_counter")
        assert counter.name == "test_counter"
        assert counter.value == 0

    def test_increment(self):
        """Test counter increment."""
        counter = Counter("test")
        result = counter.increment()
        assert result == 1
        assert counter.value == 1

    def test_increment_by_amount(self):
        """Test counter increment by specific amount."""
        counter = Counter("test")
        result = counter.increment(5)
        assert result == 5
        assert counter.value == 5

    def test_decrement(self):
        """Test counter decrement."""
        counter = Counter("test")
        counter.increment(10)
        result = counter.decrement()
        assert result == 9

    def test_decrement_by_amount(self):
        """Test counter decrement by specific amount."""
        counter = Counter("test")
        counter.increment(10)
        result = counter.decrement(3)
        assert result == 7

    def test_reset(self):
        """Test counter reset."""
        counter = Counter("test")
        counter.increment(100)
        counter.reset()
        assert counter.value == 0

    def test_thread_safety(self):
        """Test counter is thread-safe."""
        counter = Counter("test")
        threads = []

        def increment_many():
            for _ in range(1000):
                counter.increment()

        for _ in range(10):
            t = threading.Thread(target=increment_many)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert counter.value == 10000


class TestGauge:
    """Tests for Gauge class."""

    def test_init(self):
        """Test gauge initialization."""
        gauge = Gauge("test_gauge")
        assert gauge.name == "test_gauge"
        assert gauge.value == 0.0

    def test_set(self):
        """Test gauge set."""
        gauge = Gauge("test")
        gauge.set(42.5)
        assert gauge.value == 42.5

    def test_increment(self):
        """Test gauge increment."""
        gauge = Gauge("test")
        gauge.set(10.0)
        result = gauge.increment(5.5)
        assert result == 15.5

    def test_decrement(self):
        """Test gauge decrement."""
        gauge = Gauge("test")
        gauge.set(20.0)
        result = gauge.decrement(7.5)
        assert result == 12.5

    def test_thread_safety(self):
        """Test gauge is thread-safe."""
        gauge = Gauge("test")
        threads = []

        def set_value(val):
            for _ in range(100):
                gauge.set(val)
                time.sleep(0.001)

        for i in range(5):
            t = threading.Thread(target=set_value, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should end with a valid value (one of 0-4)
        assert 0 <= gauge.value <= 4


class TestHistogram:
    """Tests for Histogram class."""

    def test_init(self):
        """Test histogram initialization."""
        hist = Histogram("test_histogram")
        assert hist.name == "test_histogram"
        assert hist.count == 0
        assert hist.sum == 0.0

    def test_observe(self):
        """Test histogram observe."""
        hist = Histogram("test")
        hist.observe(1.5)
        hist.observe(2.5)
        hist.observe(3.0)
        assert hist.count == 3
        assert hist.sum == 7.0

    def test_mean(self):
        """Test histogram mean calculation."""
        hist = Histogram("test")
        hist.observe(1.0)
        hist.observe(2.0)
        hist.observe(3.0)
        assert hist.mean == 2.0

    def test_mean_empty(self):
        """Test histogram mean with no observations."""
        hist = Histogram("test")
        assert hist.mean == 0.0

    def test_median(self):
        """Test histogram median calculation."""
        hist = Histogram("test")
        for v in [1, 2, 3, 4, 5]:
            hist.observe(v)
        assert hist.median == 3

    def test_min_max(self):
        """Test histogram min/max."""
        hist = Histogram("test")
        for v in [5, 1, 10, 3, 7]:
            hist.observe(v)
        assert hist.min == 1
        assert hist.max == 10

    def test_stddev(self):
        """Test histogram standard deviation."""
        hist = Histogram("test")
        for v in [2, 4, 4, 4, 5, 5, 7, 9]:
            hist.observe(v)
        # Standard deviation should be around 2.0
        assert 1.9 < hist.stddev < 2.2

    def test_stddev_single_value(self):
        """Test stddev with single value returns 0."""
        hist = Histogram("test")
        hist.observe(5.0)
        assert hist.stddev == 0.0

    def test_percentile(self):
        """Test histogram percentile calculation."""
        hist = Histogram("test")
        for v in range(1, 101):  # 1 to 100
            hist.observe(v)
        # Percentile uses index-based calculation, values should be close
        assert 49 <= hist.percentile(50) <= 51
        assert 89 <= hist.percentile(90) <= 91
        assert 98 <= hist.percentile(99) <= 100

    def test_percentile_empty(self):
        """Test percentile with no observations."""
        hist = Histogram("test")
        assert hist.percentile(50) == 0.0

    def test_get_bucket_counts(self):
        """Test histogram bucket counts."""
        hist = Histogram("test", buckets=[0.1, 0.5, 1.0, 2.0])
        hist.observe(0.05)  # <= 0.1
        hist.observe(0.3)   # <= 0.5
        hist.observe(0.8)   # <= 1.0
        hist.observe(1.5)   # <= 2.0
        hist.observe(5.0)   # > 2.0

        counts = hist.get_bucket_counts()
        assert counts["le_0.1"] >= 1
        assert counts["le_inf"] == 5

    def test_get_stats(self):
        """Test histogram get_stats."""
        hist = Histogram("test")
        for v in [1, 2, 3, 4, 5]:
            hist.observe(v)

        stats = hist.get_stats()

        assert stats["count"] == 5
        assert stats["sum"] == 15
        assert stats["mean"] == 3.0
        assert stats["median"] == 3.0
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert "p50" in stats
        assert "p90" in stats
        assert "p95" in stats
        assert "p99" in stats

    def test_reset(self):
        """Test histogram reset."""
        hist = Histogram("test")
        for v in [1, 2, 3]:
            hist.observe(v)
        hist.reset()
        assert hist.count == 0
        assert hist.sum == 0.0


class TestTimer:
    """Tests for Timer context manager."""

    def test_timer_records_duration(self):
        """Test timer records duration."""
        collector = MetricsCollector()
        with Timer(collector, "test_timing") as timer:
            time.sleep(0.01)

        assert timer.duration >= 0.01
        assert timer.duration < 0.1  # Shouldn't take too long

    def test_timer_observes_histogram(self):
        """Test timer records to histogram."""
        collector = MetricsCollector()
        with Timer(collector, "test_timing"):
            time.sleep(0.01)

        stats = collector.get_histogram_stats("test_timing")
        assert stats["count"] == 1
        assert stats["sum"] >= 0.01

    def test_timer_records_errors(self):
        """Test timer records errors on exception."""
        collector = MetricsCollector()

        with pytest.raises(ValueError):
            with Timer(collector, "failing_op"):
                raise ValueError("Test error")

        error_count = collector.get_counter("failing_op_errors")
        assert error_count == 1


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_init(self):
        """Test collector initialization."""
        collector = MetricsCollector()
        assert collector._prefix == ""

    def test_init_with_prefix(self):
        """Test collector with prefix."""
        collector = MetricsCollector(prefix="myapp_")
        collector.increment("counter")
        assert collector.get_counter("counter") == 1

    def test_increment(self):
        """Test increment creates and updates counter."""
        collector = MetricsCollector()
        collector.increment("requests")
        collector.increment("requests")
        assert collector.get_counter("requests") == 2

    def test_increment_with_tags(self):
        """Test increment with tags."""
        collector = MetricsCollector()
        collector.increment("requests", tags={"method": "GET"})
        collector.increment("requests", tags={"method": "POST"})

        assert collector.get_counter("requests", tags={"method": "GET"}) == 1
        assert collector.get_counter("requests", tags={"method": "POST"}) == 1

    def test_decrement(self):
        """Test decrement."""
        collector = MetricsCollector()
        collector.increment("counter", 10)
        collector.decrement("counter", 3)
        assert collector.get_counter("counter") == 7

    def test_gauge_set(self):
        """Test gauge_set."""
        collector = MetricsCollector()
        collector.gauge_set("temperature", 72.5)
        assert collector.get_gauge("temperature") == 72.5

    def test_gauge_set_with_tags(self):
        """Test gauge_set with tags."""
        collector = MetricsCollector()
        collector.gauge_set("cpu", 50.0, tags={"host": "server1"})
        collector.gauge_set("cpu", 75.0, tags={"host": "server2"})

        assert collector.get_gauge("cpu", tags={"host": "server1"}) == 50.0
        assert collector.get_gauge("cpu", tags={"host": "server2"}) == 75.0

    def test_observe(self):
        """Test observe records to histogram."""
        collector = MetricsCollector()
        collector.observe("latency", 0.1)
        collector.observe("latency", 0.2)
        collector.observe("latency", 0.15)

        stats = collector.get_histogram_stats("latency")
        assert stats["count"] == 3

    def test_timer_method(self):
        """Test timer() returns Timer instance."""
        collector = MetricsCollector()
        timer = collector.timer("operation")
        assert isinstance(timer, Timer)

    def test_timed_context_manager(self):
        """Test timed() context manager."""
        collector = MetricsCollector()
        with collector.timed("operation"):
            time.sleep(0.01)

        stats = collector.get_histogram_stats("operation")
        assert stats["count"] == 1

    def test_get_summary(self):
        """Test get_summary returns all metrics."""
        collector = MetricsCollector()
        collector.increment("requests")
        collector.gauge_set("active_connections", 10)
        collector.observe("latency", 0.1)

        summary = collector.get_summary()

        assert "collection_started" in summary
        assert "collection_duration_seconds" in summary
        assert "counters" in summary
        assert "gauges" in summary
        assert "histograms" in summary
        assert summary["counters"]["requests"] == 1
        assert summary["gauges"]["active_connections"] == 10

    def test_reset(self):
        """Test reset clears all metrics."""
        collector = MetricsCollector()
        collector.increment("counter", 100)
        collector.observe("latency", 0.5)

        collector.reset()

        assert collector.get_counter("counter") == 0
        stats = collector.get_histogram_stats("latency")
        assert stats.get("count", 0) == 0

    def test_full_name_with_prefix_and_tags(self):
        """Test full name generation with prefix and tags."""
        collector = MetricsCollector(prefix="app_")
        collector.increment("requests", tags={"method": "GET", "status": "200"})

        summary = collector.get_summary()
        # Should have key with prefix and tags
        assert any("app_requests" in key for key in summary["counters"])


class TestGlobalMetrics:
    """Tests for global metrics functions."""

    def test_get_metrics_collector_creates_singleton(self):
        """Test get_metrics_collector creates singleton."""
        # Reset global state
        import common.metrics
        common.metrics._global_collector = None

        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        assert collector1 is collector2

    def test_reset_metrics(self):
        """Test reset_metrics resets global collector."""
        import common.metrics
        common.metrics._global_collector = None

        collector = get_metrics_collector()
        collector.increment("test_counter", 100)

        reset_metrics()

        assert collector.get_counter("test_counter") == 0
