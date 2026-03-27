"""
Metrics Module - SOW Requirements 4.7, 7.3

Provides metrics collection and tracking for integration runs.
Supports timing, counters, gauges, and histograms.

Usage:
    from common.metrics import MetricsCollector, Timer

    metrics = MetricsCollector()

    # Track counts
    metrics.increment('records_processed')
    metrics.increment('errors', tags={'type': 'validation'})

    # Track timing
    with Timer(metrics, 'api_call_duration'):
        response = requests.post(...)

    # Get summary
    summary = metrics.get_summary()
"""

import time
import threading
import statistics
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """Container for a single metric value with metadata."""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)


class Counter:
    """Thread-safe counter metric."""

    def __init__(self, name: str):
        self.name = name
        self._value = 0
        self._lock = threading.Lock()

    def increment(self, amount: int = 1) -> int:
        with self._lock:
            self._value += amount
            return self._value

    def decrement(self, amount: int = 1) -> int:
        with self._lock:
            self._value -= amount
            return self._value

    @property
    def value(self) -> int:
        return self._value

    def reset(self) -> None:
        with self._lock:
            self._value = 0


class Gauge:
    """Thread-safe gauge metric for values that go up and down."""

    def __init__(self, name: str):
        self.name = name
        self._value = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def increment(self, amount: float = 1.0) -> float:
        with self._lock:
            self._value += amount
            return self._value

    def decrement(self, amount: float = 1.0) -> float:
        with self._lock:
            self._value -= amount
            return self._value

    @property
    def value(self) -> float:
        return self._value


class Histogram:
    """Thread-safe histogram for tracking distributions."""

    def __init__(self, name: str, buckets: Optional[List[float]] = None):
        self.name = name
        self._values: List[float] = []
        self._lock = threading.Lock()
        self._buckets = buckets or [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

    def observe(self, value: float) -> None:
        with self._lock:
            self._values.append(value)

    @property
    def count(self) -> int:
        return len(self._values)

    @property
    def sum(self) -> float:
        return sum(self._values) if self._values else 0.0

    @property
    def mean(self) -> float:
        return statistics.mean(self._values) if self._values else 0.0

    @property
    def median(self) -> float:
        return statistics.median(self._values) if self._values else 0.0

    @property
    def min(self) -> float:
        return min(self._values) if self._values else 0.0

    @property
    def max(self) -> float:
        return max(self._values) if self._values else 0.0

    @property
    def stddev(self) -> float:
        if len(self._values) < 2:
            return 0.0
        return statistics.stdev(self._values)

    def percentile(self, p: float) -> float:
        """Calculate percentile (0-100)."""
        if not self._values:
            return 0.0
        sorted_values = sorted(self._values)
        idx = int(len(sorted_values) * p / 100)
        return sorted_values[min(idx, len(sorted_values) - 1)]

    def get_bucket_counts(self) -> Dict[str, int]:
        """Get counts per bucket."""
        counts = {f"le_{b}": 0 for b in self._buckets}
        counts["le_inf"] = len(self._values)

        for v in self._values:
            for b in self._buckets:
                if v <= b:
                    counts[f"le_{b}"] += 1
                    break

        return counts

    def get_stats(self) -> Dict[str, float]:
        """Get all statistics."""
        return {
            "count": self.count,
            "sum": self.sum,
            "mean": round(self.mean, 6),
            "median": round(self.median, 6),
            "min": round(self.min, 6),
            "max": round(self.max, 6),
            "stddev": round(self.stddev, 6),
            "p50": round(self.percentile(50), 6),
            "p90": round(self.percentile(90), 6),
            "p95": round(self.percentile(95), 6),
            "p99": round(self.percentile(99), 6),
        }

    def reset(self) -> None:
        with self._lock:
            self._values = []


class Timer:
    """Context manager for timing operations."""

    def __init__(
        self,
        collector: 'MetricsCollector',
        name: str,
        tags: Optional[Dict[str, str]] = None
    ):
        self.collector = collector
        self.name = name
        self.tags = tags or {}
        self._start_time: Optional[float] = None
        self._duration: Optional[float] = None

    def __enter__(self) -> 'Timer':
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._duration = time.perf_counter() - self._start_time
        self.collector.observe(self.name, self._duration, self.tags)
        if exc_type:
            self.collector.increment(f"{self.name}_errors", tags=self.tags)

    @property
    def duration(self) -> float:
        return self._duration or 0.0


class MetricsCollector:
    """
    Central metrics collection system.

    Collects counters, gauges, and histograms with optional tagging.
    """

    def __init__(self, prefix: str = ""):
        self._prefix = prefix
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._lock = threading.Lock()
        self._start_time = datetime.now()

    def _get_full_name(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Get full metric name with prefix and tags."""
        full_name = f"{self._prefix}{name}" if self._prefix else name
        if tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
            full_name = f"{full_name}{{{tag_str}}}"
        return full_name

    def increment(
        self,
        name: str,
        amount: int = 1,
        tags: Optional[Dict[str, str]] = None
    ) -> int:
        """Increment a counter."""
        full_name = self._get_full_name(name, tags)
        with self._lock:
            if full_name not in self._counters:
                self._counters[full_name] = Counter(full_name)
            return self._counters[full_name].increment(amount)

    def decrement(
        self,
        name: str,
        amount: int = 1,
        tags: Optional[Dict[str, str]] = None
    ) -> int:
        """Decrement a counter."""
        full_name = self._get_full_name(name, tags)
        with self._lock:
            if full_name not in self._counters:
                self._counters[full_name] = Counter(full_name)
            return self._counters[full_name].decrement(amount)

    def gauge_set(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge value."""
        full_name = self._get_full_name(name, tags)
        with self._lock:
            if full_name not in self._gauges:
                self._gauges[full_name] = Gauge(full_name)
            self._gauges[full_name].set(value)

    def observe(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record an observation in a histogram."""
        full_name = self._get_full_name(name, tags)
        with self._lock:
            if full_name not in self._histograms:
                self._histograms[full_name] = Histogram(full_name)
            self._histograms[full_name].observe(value)

    def timer(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None
    ) -> Timer:
        """Get a timer context manager."""
        return Timer(self, name, tags)

    @contextmanager
    def timed(self, name: str, tags: Optional[Dict[str, str]] = None):
        """Context manager for timing operations."""
        with self.timer(name, tags):
            yield

    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> int:
        """Get current counter value."""
        full_name = self._get_full_name(name, tags)
        counter = self._counters.get(full_name)
        return counter.value if counter else 0

    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        """Get current gauge value."""
        full_name = self._get_full_name(name, tags)
        gauge = self._gauges.get(full_name)
        return gauge.value if gauge else 0.0

    def get_histogram_stats(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """Get histogram statistics."""
        full_name = self._get_full_name(name, tags)
        histogram = self._histograms.get(full_name)
        return histogram.get_stats() if histogram else {}

    def get_summary(self) -> Dict[str, Any]:
        """Get complete metrics summary."""
        summary = {
            "collection_started": self._start_time.isoformat(),
            "collection_duration_seconds": (datetime.now() - self._start_time).total_seconds(),
            "counters": {},
            "gauges": {},
            "histograms": {},
        }

        for name, counter in self._counters.items():
            summary["counters"][name] = counter.value

        for name, gauge in self._gauges.items():
            summary["gauges"][name] = gauge.value

        for name, histogram in self._histograms.items():
            summary["histograms"][name] = histogram.get_stats()

        return summary

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            for counter in self._counters.values():
                counter.reset()
            for histogram in self._histograms.values():
                histogram.reset()
            self._start_time = datetime.now()


# Global metrics collector instance
_global_collector: Optional[MetricsCollector] = None


def get_metrics_collector(prefix: str = "") -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector(prefix)
    return _global_collector


def reset_metrics() -> None:
    """Reset the global metrics collector."""
    global _global_collector
    if _global_collector:
        _global_collector.reset()
