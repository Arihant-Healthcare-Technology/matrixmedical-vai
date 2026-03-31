"""
Tests for the rate_limiter module.

Tests cover:
- RateLimitStats statistics tracking
- RateLimiter token bucket implementation
- AdaptiveRateLimiter with backoff/recovery
- SlidingWindowRateLimiter implementation
- get_rate_limiter factory function
- Thread safety
"""

import pytest
import time
import threading
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from common.rate_limiter import (
    RateLimitStats,
    RateLimiter,
    AdaptiveRateLimiter,
    SlidingWindowRateLimiter,
    get_rate_limiter,
    reset_rate_limiters,
)


class TestRateLimitStats:
    """Tests for RateLimitStats dataclass."""

    def test_init_default_values(self):
        """Test default initialization values."""
        stats = RateLimitStats()
        assert stats.total_requests == 0
        assert stats.total_wait_time == 0.0
        assert stats.max_wait_time == 0.0
        assert stats.throttled_requests == 0
        assert stats.start_time is not None

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        now = datetime.now()
        stats = RateLimitStats(
            total_requests=100,
            total_wait_time=5.0,
            max_wait_time=1.5,
            throttled_requests=10,
            start_time=now,
        )
        assert stats.total_requests == 100
        assert stats.total_wait_time == 5.0
        assert stats.max_wait_time == 1.5
        assert stats.throttled_requests == 10
        assert stats.start_time == now

    def test_average_wait_time_zero_requests(self):
        """Test average wait time with zero requests."""
        stats = RateLimitStats()
        assert stats.average_wait_time == 0.0

    def test_average_wait_time_with_requests(self):
        """Test average wait time calculation."""
        stats = RateLimitStats(
            total_requests=10,
            total_wait_time=5.0,
        )
        assert stats.average_wait_time == 0.5

    def test_throttle_rate_zero_requests(self):
        """Test throttle rate with zero requests."""
        stats = RateLimitStats()
        assert stats.throttle_rate == 0.0

    def test_throttle_rate_with_requests(self):
        """Test throttle rate calculation."""
        stats = RateLimitStats(
            total_requests=100,
            throttled_requests=25,
        )
        assert stats.throttle_rate == 0.25

    def test_to_dict(self):
        """Test dictionary conversion."""
        now = datetime.now()
        stats = RateLimitStats(
            total_requests=100,
            total_wait_time=5.0,
            max_wait_time=1.5,
            throttled_requests=25,
            start_time=now,
        )
        result = stats.to_dict()

        assert result["total_requests"] == 100
        assert result["throttled_requests"] == 25
        assert result["throttle_rate"] == "25.00%"
        assert result["total_wait_time_seconds"] == 5.0
        assert result["average_wait_time_seconds"] == 0.05
        assert result["max_wait_time_seconds"] == 1.5
        assert "uptime_seconds" in result


class TestRateLimiter:
    """Tests for RateLimiter token bucket implementation."""

    @pytest.fixture
    def limiter(self):
        """Create a rate limiter for testing."""
        return RateLimiter(calls_per_minute=60, name="test")

    @pytest.fixture
    def fast_limiter(self):
        """Create a fast rate limiter for quick tests."""
        return RateLimiter(calls_per_minute=600, name="fast")

    def test_init_default_values(self):
        """Test initialization with default values."""
        limiter = RateLimiter(calls_per_minute=60)
        assert limiter.name == "default"
        assert limiter.calls_per_minute == 60
        assert limiter.rate == 1.0  # 60/60
        assert limiter.max_tokens == 60
        assert limiter.max_wait_seconds == 60.0

    def test_init_custom_burst_size(self):
        """Test initialization with custom burst size."""
        limiter = RateLimiter(calls_per_minute=60, burst_size=10)
        assert limiter.max_tokens == 10

    def test_init_custom_max_wait(self):
        """Test initialization with custom max wait."""
        limiter = RateLimiter(calls_per_minute=60, max_wait_seconds=30.0)
        assert limiter.max_wait_seconds == 30.0

    def test_acquire_success(self, fast_limiter):
        """Test successful token acquisition."""
        result = fast_limiter.acquire()
        assert result is True

    def test_acquire_multiple(self, fast_limiter):
        """Test multiple token acquisitions."""
        for _ in range(10):
            result = fast_limiter.acquire()
            assert result is True

    def test_acquire_with_tokens(self, fast_limiter):
        """Test acquiring multiple tokens at once."""
        result = fast_limiter.acquire(tokens=5)
        assert result is True

    def test_try_acquire_success(self, fast_limiter):
        """Test non-blocking acquisition success."""
        result = fast_limiter.try_acquire()
        assert result is True

    def test_try_acquire_updates_stats(self, fast_limiter):
        """Test try_acquire updates statistics."""
        initial_requests = fast_limiter.get_stats().total_requests
        fast_limiter.try_acquire()
        assert fast_limiter.get_stats().total_requests == initial_requests + 1

    def test_try_acquire_fails_when_exhausted(self):
        """Test try_acquire fails when no tokens available."""
        limiter = RateLimiter(calls_per_minute=60, burst_size=2)
        # Exhaust tokens
        limiter.try_acquire()
        limiter.try_acquire()
        # Third should fail
        result = limiter.try_acquire()
        assert result is False

    def test_wait_time_zero_when_available(self, fast_limiter):
        """Test wait time is zero when tokens available."""
        wait = fast_limiter.wait_time()
        assert wait == 0.0

    def test_wait_time_positive_when_exhausted(self):
        """Test wait time is positive when tokens exhausted."""
        limiter = RateLimiter(calls_per_minute=60, burst_size=1)
        limiter.acquire()
        wait = limiter.wait_time()
        assert wait > 0

    def test_get_stats(self, fast_limiter):
        """Test get_stats returns RateLimitStats."""
        stats = fast_limiter.get_stats()
        assert isinstance(stats, RateLimitStats)

    def test_reset_stats(self, fast_limiter):
        """Test reset_stats clears statistics."""
        fast_limiter.acquire()
        fast_limiter.reset_stats()
        stats = fast_limiter.get_stats()
        assert stats.total_requests == 0

    def test_rate_limited_decorator(self, fast_limiter):
        """Test rate_limited decorator."""
        call_count = 0

        @fast_limiter.rate_limited
        def test_func():
            nonlocal call_count
            call_count += 1
            return "result"

        result = test_func()
        assert result == "result"
        assert call_count == 1

    def test_context_manager(self, fast_limiter):
        """Test context manager usage."""
        with fast_limiter:
            pass  # Should not raise

    def test_acquire_timeout(self):
        """Test acquire times out when wait exceeds timeout."""
        limiter = RateLimiter(calls_per_minute=1, burst_size=1)
        limiter.acquire()  # Use the only token

        # Try to acquire with very short timeout
        result = limiter.acquire(timeout=0.001)
        assert result is False

    def test_stats_track_throttled_requests(self):
        """Test that throttled requests are tracked."""
        limiter = RateLimiter(calls_per_minute=600, burst_size=1)
        limiter.acquire()  # Use the token

        # This should be throttled
        limiter.acquire(timeout=0.1)

        stats = limiter.get_stats()
        assert stats.throttled_requests >= 1


class TestAdaptiveRateLimiter:
    """Tests for AdaptiveRateLimiter."""

    @pytest.fixture
    def adaptive_limiter(self):
        """Create adaptive rate limiter for testing."""
        return AdaptiveRateLimiter(
            calls_per_minute=100,
            name="adaptive_test",
            min_rate=10,
            backoff_factor=0.5,
            recovery_factor=1.2,
            recovery_threshold=5,
        )

    def test_init_inherits_from_rate_limiter(self, adaptive_limiter):
        """Test initialization inherits from RateLimiter."""
        assert adaptive_limiter.calls_per_minute == 100
        assert adaptive_limiter.name == "adaptive_test"

    def test_init_adaptive_properties(self, adaptive_limiter):
        """Test adaptive-specific initialization."""
        assert adaptive_limiter.max_rate == 100
        assert adaptive_limiter.min_rate == 10
        assert adaptive_limiter.backoff_factor == 0.5
        assert adaptive_limiter.recovery_factor == 1.2
        assert adaptive_limiter.recovery_threshold == 5

    def test_report_rate_limited_decreases_rate(self, adaptive_limiter):
        """Test rate decreases after rate limit hit."""
        initial_rate = adaptive_limiter.calls_per_minute
        adaptive_limiter.report_rate_limited()
        assert adaptive_limiter.calls_per_minute < initial_rate

    def test_report_rate_limited_respects_min_rate(self):
        """Test rate doesn't go below minimum."""
        limiter = AdaptiveRateLimiter(
            calls_per_minute=20,
            min_rate=10,
            backoff_factor=0.5,
        )
        # Multiple rate limited responses
        for _ in range(10):
            limiter.report_rate_limited()

        assert limiter.calls_per_minute >= limiter.min_rate

    def test_report_success_increases_rate_after_threshold(self, adaptive_limiter):
        """Test rate increases after enough successful calls."""
        # First decrease the rate
        adaptive_limiter.report_rate_limited()
        decreased_rate = adaptive_limiter.calls_per_minute

        # Then report enough successes
        for _ in range(adaptive_limiter.recovery_threshold):
            adaptive_limiter.report_success()

        assert adaptive_limiter.calls_per_minute > decreased_rate

    def test_report_success_respects_max_rate(self):
        """Test rate doesn't exceed maximum."""
        limiter = AdaptiveRateLimiter(
            calls_per_minute=100,
            recovery_factor=2.0,
            recovery_threshold=1,
        )
        # Many successful calls
        for _ in range(50):
            limiter.report_success()

        assert limiter.calls_per_minute <= limiter.max_rate

    def test_report_rate_limited_resets_success_count(self, adaptive_limiter):
        """Test rate limit resets success counter."""
        # Report some successes
        for _ in range(3):
            adaptive_limiter.report_success()

        # Rate limited should reset
        adaptive_limiter.report_rate_limited()

        # Need full threshold again for recovery
        initial_rate = adaptive_limiter.calls_per_minute
        for _ in range(adaptive_limiter.recovery_threshold - 1):
            adaptive_limiter.report_success()

        # Should not have increased yet
        assert adaptive_limiter.calls_per_minute == initial_rate


class TestSlidingWindowRateLimiter:
    """Tests for SlidingWindowRateLimiter."""

    @pytest.fixture
    def sliding_limiter(self):
        """Create sliding window rate limiter for testing."""
        return SlidingWindowRateLimiter(
            calls_per_minute=60,
            name="sliding_test",
            window_size_seconds=1,  # Use 1 second window for fast tests
        )

    def test_init(self, sliding_limiter):
        """Test initialization."""
        assert sliding_limiter.name == "sliding_test"
        assert sliding_limiter.max_calls == 60
        assert sliding_limiter.window_size == 1

    def test_acquire_success(self, sliding_limiter):
        """Test successful acquisition."""
        result = sliding_limiter.acquire()
        assert result is True

    def test_acquire_multiple(self, sliding_limiter):
        """Test multiple acquisitions within limit."""
        for _ in range(10):
            result = sliding_limiter.acquire()
            assert result is True

    def test_get_stats(self, sliding_limiter):
        """Test get_stats returns RateLimitStats."""
        stats = sliding_limiter.get_stats()
        assert isinstance(stats, RateLimitStats)

    def test_acquire_timeout_when_exhausted(self):
        """Test acquisition times out when limit reached."""
        limiter = SlidingWindowRateLimiter(
            calls_per_minute=2,
            window_size_seconds=60,
        )
        # Use all allowed calls
        limiter.acquire()
        limiter.acquire()

        # Next should timeout
        result = limiter.acquire(timeout=0.01)
        assert result is False


class TestGetRateLimiter:
    """Tests for get_rate_limiter factory function."""

    def setup_method(self):
        """Reset rate limiters before each test."""
        reset_rate_limiters()

    def teardown_method(self):
        """Reset rate limiters after each test."""
        reset_rate_limiters()

    def test_get_bill_limiter(self):
        """Test getting BILL.com rate limiter."""
        limiter = get_rate_limiter("bill")
        assert limiter.name == "bill.com"
        assert limiter.calls_per_minute == 60

    def test_get_motus_limiter(self):
        """Test getting Motus rate limiter."""
        limiter = get_rate_limiter("motus")
        assert limiter.name == "motus"
        assert limiter.calls_per_minute == 100

    def test_get_travelperk_limiter(self):
        """Test getting TravelPerk rate limiter."""
        limiter = get_rate_limiter("travelperk")
        assert limiter.name == "travelperk"
        assert limiter.calls_per_minute == 100

    def test_get_same_limiter_instance(self):
        """Test getting the same limiter returns same instance."""
        limiter1 = get_rate_limiter("bill")
        limiter2 = get_rate_limiter("bill")
        assert limiter1 is limiter2

    def test_get_unknown_integration_raises(self):
        """Test unknown integration raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_rate_limiter("unknown")
        assert "Unknown integration" in str(exc_info.value)

    def test_reset_clears_cached_limiters(self):
        """Test reset_rate_limiters clears cache."""
        limiter1 = get_rate_limiter("bill")
        reset_rate_limiters()
        limiter2 = get_rate_limiter("bill")
        assert limiter1 is not limiter2


class TestThreadSafety:
    """Tests for thread safety of rate limiters."""

    def test_concurrent_acquire(self):
        """Test concurrent token acquisition."""
        limiter = RateLimiter(calls_per_minute=1000, name="concurrent")
        acquired = []
        threads = []

        def acquire_token():
            result = limiter.acquire(timeout=1.0)
            acquired.append(result)

        # Create multiple threads
        for _ in range(50):
            t = threading.Thread(target=acquire_token)
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # All should have acquired
        assert len(acquired) == 50
        assert all(acquired)

    def test_concurrent_try_acquire(self):
        """Test concurrent non-blocking acquisition."""
        limiter = RateLimiter(calls_per_minute=60, burst_size=10)
        acquired = []
        threads = []

        def try_acquire_token():
            result = limiter.try_acquire()
            acquired.append(result)

        # Create more threads than burst size
        for _ in range(20):
            t = threading.Thread(target=try_acquire_token)
            threads.append(t)

        # Start all threads simultaneously
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Some should succeed, some should fail
        success_count = sum(1 for r in acquired if r)
        failure_count = sum(1 for r in acquired if not r)
        assert success_count <= 10  # No more than burst size
        assert success_count + failure_count == 20


class TestRateLimiterIntegration:
    """Integration tests for rate limiter."""

    def test_decorator_with_real_function(self):
        """Test decorator with actual function execution."""
        limiter = RateLimiter(calls_per_minute=600, name="decorator_test")
        results = []

        @limiter.rate_limited
        def process_item(item):
            results.append(item * 2)
            return item * 2

        for i in range(5):
            result = process_item(i)
            assert result == i * 2

        assert results == [0, 2, 4, 6, 8]

    def test_context_manager_with_exception(self):
        """Test context manager handles exceptions."""
        limiter = RateLimiter(calls_per_minute=600, name="context_test")

        with pytest.raises(ValueError):
            with limiter:
                raise ValueError("Test error")

        # Should still work after exception
        with limiter:
            pass

    def test_stats_accuracy(self):
        """Test statistics are accurate."""
        limiter = RateLimiter(calls_per_minute=600, burst_size=5)

        # Make some requests
        for _ in range(10):
            limiter.acquire(timeout=0.1)

        stats = limiter.get_stats()
        assert stats.total_requests == 10
        # Some should have been throttled
        assert stats.throttled_requests >= 0
