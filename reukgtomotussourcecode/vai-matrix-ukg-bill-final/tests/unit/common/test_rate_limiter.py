"""
Unit tests for common/rate_limiter.py.
"""

import time
import threading
from unittest.mock import patch, MagicMock

import pytest

from common.rate_limiter import (
    RateLimiter,
    RateLimitStats,
    AdaptiveRateLimiter,
    SlidingWindowRateLimiter,
    get_rate_limiter,
    reset_rate_limiters,
)


class TestRateLimitStats:
    """Tests for RateLimitStats dataclass."""

    def test_default_initialization(self):
        """Test default stats initialization."""
        stats = RateLimitStats()
        assert stats.total_requests == 0
        assert stats.total_wait_time == 0.0
        assert stats.max_wait_time == 0.0
        assert stats.throttled_requests == 0
        assert stats.start_time is not None

    def test_average_wait_time_zero_requests(self):
        """Test average wait time with zero requests."""
        stats = RateLimitStats()
        assert stats.average_wait_time == 0.0

    def test_average_wait_time_calculation(self):
        """Test average wait time calculation."""
        stats = RateLimitStats(total_requests=10, total_wait_time=5.0)
        assert stats.average_wait_time == 0.5

    def test_throttle_rate_zero_requests(self):
        """Test throttle rate with zero requests."""
        stats = RateLimitStats()
        assert stats.throttle_rate == 0.0

    def test_throttle_rate_calculation(self):
        """Test throttle rate calculation."""
        stats = RateLimitStats(total_requests=100, throttled_requests=25)
        assert stats.throttle_rate == 0.25

    def test_to_dict(self):
        """Test stats to dictionary conversion."""
        stats = RateLimitStats(
            total_requests=100,
            total_wait_time=10.0,
            max_wait_time=2.5,
            throttled_requests=20,
        )
        result = stats.to_dict()

        assert result["total_requests"] == 100
        assert result["throttled_requests"] == 20
        assert "20.00%" in result["throttle_rate"]
        assert result["total_wait_time_seconds"] == 10.0
        assert result["average_wait_time_seconds"] == 0.1


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(calls_per_minute=60, name="test")
        assert limiter.name == "test"
        assert limiter.calls_per_minute == 60
        assert limiter.rate == 1.0  # 60/60
        assert limiter.max_tokens == 60

    def test_initialization_with_burst_size(self):
        """Test initialization with custom burst size."""
        limiter = RateLimiter(calls_per_minute=60, burst_size=10)
        assert limiter.max_tokens == 10

    def test_acquire_succeeds_when_tokens_available(self):
        """Test acquire succeeds with available tokens."""
        limiter = RateLimiter(calls_per_minute=60)
        assert limiter.acquire() is True

    def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens at once."""
        limiter = RateLimiter(calls_per_minute=60)
        assert limiter.acquire(tokens=5) is True

    def test_try_acquire_succeeds(self):
        """Test try_acquire returns True when tokens available."""
        limiter = RateLimiter(calls_per_minute=60)
        assert limiter.try_acquire() is True

    def test_try_acquire_fails_no_tokens(self):
        """Test try_acquire returns False when no tokens."""
        limiter = RateLimiter(calls_per_minute=60)
        # Drain tokens
        for _ in range(60):
            limiter.try_acquire()
        # Next should fail
        assert limiter.try_acquire() is False

    def test_wait_time_zero_when_available(self):
        """Test wait_time returns 0 when tokens available."""
        limiter = RateLimiter(calls_per_minute=60)
        assert limiter.wait_time() == 0.0

    def test_wait_time_positive_when_drained(self):
        """Test wait_time returns positive value when tokens drained."""
        limiter = RateLimiter(calls_per_minute=60)
        # Drain all tokens
        for _ in range(60):
            limiter.try_acquire()
        # Wait time should be positive
        assert limiter.wait_time() > 0

    def test_get_stats(self):
        """Test get_stats returns stats object."""
        limiter = RateLimiter(calls_per_minute=60)
        limiter.acquire()
        stats = limiter.get_stats()
        assert stats.total_requests == 1

    def test_reset_stats(self):
        """Test reset_stats clears statistics."""
        limiter = RateLimiter(calls_per_minute=60)
        limiter.acquire()
        assert limiter.get_stats().total_requests == 1
        limiter.reset_stats()
        assert limiter.get_stats().total_requests == 0

    def test_context_manager(self):
        """Test rate limiter as context manager."""
        limiter = RateLimiter(calls_per_minute=60)
        with limiter:
            pass
        assert limiter.get_stats().total_requests == 1

    def test_rate_limited_decorator(self):
        """Test rate_limited decorator."""
        limiter = RateLimiter(calls_per_minute=60)

        @limiter.rate_limited
        def test_func():
            return "result"

        result = test_func()
        assert result == "result"
        assert limiter.get_stats().total_requests == 1

    def test_acquire_timeout(self):
        """Test acquire times out when no tokens."""
        limiter = RateLimiter(calls_per_minute=60)
        # Drain tokens
        for _ in range(60):
            limiter.try_acquire()
        # Should fail with short timeout
        assert limiter.acquire(timeout=0.01) is False

    def test_thread_safety(self):
        """Test thread safety with concurrent access."""
        limiter = RateLimiter(calls_per_minute=1000, name="concurrent")
        results = []

        def acquire_token():
            success = limiter.try_acquire()
            results.append(success)

        threads = [threading.Thread(target=acquire_token) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have acquired some tokens
        assert sum(results) > 0
        assert limiter.get_stats().total_requests == sum(results)


class TestAdaptiveRateLimiter:
    """Tests for AdaptiveRateLimiter class."""

    def test_initialization(self):
        """Test adaptive rate limiter initialization."""
        limiter = AdaptiveRateLimiter(calls_per_minute=60)
        assert limiter.max_rate == 60
        assert limiter.min_rate == 10

    def test_report_rate_limited_decreases_rate(self):
        """Test that reporting rate limit decreases rate."""
        limiter = AdaptiveRateLimiter(
            calls_per_minute=60,
            backoff_factor=0.5,
        )
        initial_rate = limiter.calls_per_minute
        limiter.report_rate_limited()
        assert limiter.calls_per_minute < initial_rate

    def test_report_success_increases_rate_after_threshold(self):
        """Test that success reports increase rate after threshold."""
        limiter = AdaptiveRateLimiter(
            calls_per_minute=30,
            recovery_threshold=5,
            recovery_factor=1.5,
        )
        limiter.max_rate = 60

        # Report successes up to threshold
        for _ in range(5):
            limiter.report_success()

        # Rate should have increased
        assert limiter.calls_per_minute > 30

    def test_rate_does_not_exceed_max(self):
        """Test rate doesn't exceed max rate."""
        limiter = AdaptiveRateLimiter(
            calls_per_minute=50,
            recovery_threshold=1,
            recovery_factor=2.0,
        )
        limiter.max_rate = 60

        for _ in range(10):
            limiter.report_success()

        assert limiter.calls_per_minute <= 60

    def test_rate_does_not_go_below_min(self):
        """Test rate doesn't go below min rate."""
        limiter = AdaptiveRateLimiter(
            calls_per_minute=20,
            min_rate=10,
            backoff_factor=0.1,
        )

        for _ in range(10):
            limiter.report_rate_limited()

        assert limiter.calls_per_minute >= 10


class TestSlidingWindowRateLimiter:
    """Tests for SlidingWindowRateLimiter class."""

    def test_initialization(self):
        """Test sliding window limiter initialization."""
        limiter = SlidingWindowRateLimiter(calls_per_minute=60)
        assert limiter.max_calls == 60
        assert limiter.window_size == 60

    def test_acquire_succeeds_under_limit(self):
        """Test acquire succeeds when under limit."""
        limiter = SlidingWindowRateLimiter(calls_per_minute=60)
        assert limiter.acquire() is True

    def test_acquire_multiple_times(self):
        """Test acquiring multiple times."""
        limiter = SlidingWindowRateLimiter(calls_per_minute=10)
        for _ in range(10):
            assert limiter.acquire() is True

    def test_get_stats(self):
        """Test get_stats returns stats."""
        limiter = SlidingWindowRateLimiter(calls_per_minute=60)
        limiter.acquire()
        stats = limiter.get_stats()
        assert stats.total_requests == 1


class TestGetRateLimiter:
    """Tests for get_rate_limiter factory function."""

    def setup_method(self):
        """Reset rate limiters before each test."""
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

    def test_caches_limiter(self):
        """Test that limiter is cached."""
        limiter1 = get_rate_limiter("bill")
        limiter2 = get_rate_limiter("bill")
        assert limiter1 is limiter2

    def test_invalid_integration_raises(self):
        """Test invalid integration raises ValueError."""
        with pytest.raises(ValueError) as exc:
            get_rate_limiter("invalid")
        assert "Unknown integration" in str(exc.value)


class TestResetRateLimiters:
    """Tests for reset_rate_limiters function."""

    def test_resets_cached_limiters(self):
        """Test that reset clears cached limiters."""
        limiter1 = get_rate_limiter("bill")
        reset_rate_limiters()
        limiter2 = get_rate_limiter("bill")
        # Should be different instances after reset
        assert limiter1 is not limiter2
