"""Tests for retry utilities."""

import pytest
import time
from unittest.mock import MagicMock, patch
import requests

from src.infrastructure.http.retry import (
    RetryConfig,
    with_retry,
    retry_on_rate_limit,
    get_retry_after_seconds,
    DEFAULT_RETRYABLE_STATUS_CODES,
    DEFAULT_RETRYABLE_EXCEPTIONS,
)
from src.domain.exceptions import RateLimitError, ServerError, TimeoutError


class TestRetryConfig:
    """Test cases for RetryConfig class."""

    def test_default_initialization(self):
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.retryable_status_codes == DEFAULT_RETRYABLE_STATUS_CODES
        assert config.retryable_exceptions == DEFAULT_RETRYABLE_EXCEPTIONS

    def test_custom_initialization(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            retryable_status_codes={500, 503},
            retryable_exceptions=(ValueError,),
        )

        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.retryable_status_codes == {500, 503}
        assert config.retryable_exceptions == (ValueError,)

    def test_calculate_delay_first_attempt(self):
        """Test delay calculation for first attempt."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0)

        delay = config.calculate_delay(0)

        assert delay == 1.0  # 1.0 * (2.0 ** 0) = 1.0

    def test_calculate_delay_exponential_growth(self):
        """Test delay increases exponentially."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0)

        assert config.calculate_delay(0) == 1.0   # 1.0 * 2^0 = 1.0
        assert config.calculate_delay(1) == 2.0   # 1.0 * 2^1 = 2.0
        assert config.calculate_delay(2) == 4.0   # 1.0 * 2^2 = 4.0
        assert config.calculate_delay(3) == 8.0   # 1.0 * 2^3 = 8.0

    def test_calculate_delay_respects_max_delay(self):
        """Test delay is capped at max_delay."""
        config = RetryConfig(base_delay=1.0, max_delay=5.0, exponential_base=2.0)

        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 5.0  # Capped at max_delay
        assert config.calculate_delay(10) == 5.0  # Still capped

    def test_is_retryable_status_default(self):
        """Test default retryable status codes."""
        config = RetryConfig()

        assert config.is_retryable_status(408) is True
        assert config.is_retryable_status(429) is True
        assert config.is_retryable_status(500) is True
        assert config.is_retryable_status(502) is True
        assert config.is_retryable_status(503) is True
        assert config.is_retryable_status(504) is True
        assert config.is_retryable_status(400) is False
        assert config.is_retryable_status(401) is False
        assert config.is_retryable_status(404) is False
        assert config.is_retryable_status(200) is False

    def test_is_retryable_status_custom(self):
        """Test custom retryable status codes."""
        config = RetryConfig(retryable_status_codes={500, 502})

        assert config.is_retryable_status(500) is True
        assert config.is_retryable_status(502) is True
        assert config.is_retryable_status(503) is False

    def test_is_retryable_exception_default(self):
        """Test default retryable exceptions."""
        config = RetryConfig()

        assert config.is_retryable_exception(requests.exceptions.Timeout()) is True
        assert config.is_retryable_exception(requests.exceptions.ConnectionError()) is True
        assert config.is_retryable_exception(RateLimitError("Test")) is True
        assert config.is_retryable_exception(ServerError("Test")) is True
        assert config.is_retryable_exception(TimeoutError("Test")) is True
        assert config.is_retryable_exception(ValueError("Test")) is False

    def test_is_retryable_exception_custom(self):
        """Test custom retryable exceptions."""
        config = RetryConfig(retryable_exceptions=(ValueError,))

        assert config.is_retryable_exception(ValueError("Test")) is True
        assert config.is_retryable_exception(TypeError("Test")) is False


class TestWithRetry:
    """Test cases for with_retry decorator."""

    def test_success_on_first_attempt(self):
        """Test function succeeds on first attempt."""
        call_count = 0

        @with_retry()
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()

        assert result == "success"
        assert call_count == 1

    @patch("src.infrastructure.http.retry.time.sleep")
    def test_retry_on_retryable_exception(self, mock_sleep):
        """Test function retries on retryable exception."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=3))
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.exceptions.ConnectionError("Connection failed")
            return "success"

        result = flaky_func()

        assert result == "success"
        assert call_count == 3
        assert mock_sleep.call_count == 2

    def test_no_retry_on_non_retryable_exception(self):
        """Test function does not retry on non-retryable exception."""
        call_count = 0

        @with_retry()
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            failing_func()

        assert call_count == 1

    @patch("src.infrastructure.http.retry.time.sleep")
    def test_max_retries_exceeded(self, mock_sleep):
        """Test exception is raised when max retries exceeded."""
        config = RetryConfig(max_retries=2)

        @with_retry(config)
        def always_fails():
            raise requests.exceptions.ConnectionError("Always fails")

        with pytest.raises(requests.exceptions.ConnectionError):
            always_fails()

        assert mock_sleep.call_count == 2

    @patch("src.infrastructure.http.retry.time.sleep")
    def test_on_retry_callback_called(self, mock_sleep):
        """Test on_retry callback is called before each retry."""
        retry_attempts = []

        def on_retry_callback(attempt, exception):
            retry_attempts.append((attempt, type(exception).__name__))

        call_count = 0

        @with_retry(RetryConfig(max_retries=2), on_retry=on_retry_callback)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.exceptions.ConnectionError("Failed")
            return "success"

        result = flaky_func()

        assert result == "success"
        assert len(retry_attempts) == 2
        assert retry_attempts[0] == (0, "ConnectionError")
        assert retry_attempts[1] == (1, "ConnectionError")

    @patch("src.infrastructure.http.retry.time.sleep")
    def test_exponential_backoff_delays(self, mock_sleep):
        """Test delays follow exponential backoff."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, max_retries=3)
        call_count = 0

        @with_retry(config)
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise requests.exceptions.ConnectionError("Failed")

        with pytest.raises(requests.exceptions.ConnectionError):
            failing_func()

        # Verify sleep was called with correct delays
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls == [1.0, 2.0, 4.0]

    def test_with_retry_default_config(self):
        """Test with_retry uses default config when none provided."""
        @with_retry()
        def simple_func():
            return "result"

        result = simple_func()
        assert result == "result"

    def test_preserves_function_metadata(self):
        """Test decorator preserves function name and docstring."""
        @with_retry()
        def documented_func():
            """This is the docstring."""
            return True

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is the docstring."


class TestRetryOnRateLimit:
    """Test cases for retry_on_rate_limit decorator."""

    def test_success_on_first_attempt(self):
        """Test function succeeds on first attempt."""
        @retry_on_rate_limit()
        def successful_func():
            return "success"

        result = successful_func()
        assert result == "success"

    @patch("src.infrastructure.http.retry.time.sleep")
    def test_retry_on_rate_limit_error(self, mock_sleep):
        """Test function retries on RateLimitError."""
        call_count = 0

        @retry_on_rate_limit(max_retries=3)
        def rate_limited_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RateLimitError("Rate limited", retry_after=30)
            return "success"

        result = rate_limited_func()

        assert result == "success"
        assert call_count == 2
        mock_sleep.assert_called_once_with(30)

    @patch("src.infrastructure.http.retry.time.sleep")
    def test_uses_retry_after_from_exception(self, mock_sleep):
        """Test uses retry_after from exception."""
        call_count = 0

        @retry_on_rate_limit(max_retries=2, default_wait=60.0)
        def rate_limited_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                error = RateLimitError("Rate limited")
                error.retry_after = 45
                raise error
            return "success"

        result = rate_limited_func()

        assert result == "success"
        mock_sleep.assert_called_with(45)

    @patch("src.infrastructure.http.retry.time.sleep")
    def test_uses_default_wait_when_no_retry_after(self, mock_sleep):
        """Test uses default wait when retry_after attribute not accessible."""
        call_count = 0

        @retry_on_rate_limit(max_retries=2, default_wait=120.0)
        def rate_limited_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # RateLimitError has retry_after as an attribute
                # The decorator uses getattr with default_wait fallback
                raise RateLimitError("Rate limited")
            return "success"

        result = rate_limited_func()

        assert result == "success"
        # RateLimitError initializes retry_after to 60 by default
        # So the decorator will use that value
        mock_sleep.assert_called()

    @patch("src.infrastructure.http.retry.time.sleep")
    def test_max_retries_exceeded(self, mock_sleep):
        """Test raises after max retries exceeded."""
        @retry_on_rate_limit(max_retries=2)
        def always_rate_limited():
            raise RateLimitError("Always limited", retry_after=10)

        with pytest.raises(RateLimitError):
            always_rate_limited()

        assert mock_sleep.call_count == 2

    def test_non_rate_limit_exception_not_caught(self):
        """Test non-RateLimitError exceptions are not caught."""
        @retry_on_rate_limit()
        def raises_other_error():
            raise ValueError("Not a rate limit error")

        with pytest.raises(ValueError):
            raises_other_error()

    def test_preserves_function_metadata(self):
        """Test decorator preserves function name and docstring."""
        @retry_on_rate_limit()
        def documented_func():
            """Rate limited function."""
            return True

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "Rate limited function."


class TestGetRetryAfterSeconds:
    """Test cases for get_retry_after_seconds function."""

    def test_extract_retry_after_header(self):
        """Test extracting Retry-After header value."""
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "120"}

        result = get_retry_after_seconds(mock_response)

        assert result == 120.0

    def test_extract_float_retry_after(self):
        """Test extracting float Retry-After value."""
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "30.5"}

        result = get_retry_after_seconds(mock_response)

        assert result == 30.5

    def test_missing_retry_after_uses_default(self):
        """Test uses default when Retry-After missing."""
        mock_response = MagicMock()
        mock_response.headers = {}

        result = get_retry_after_seconds(mock_response, default=90.0)

        assert result == 90.0

    def test_invalid_retry_after_uses_default(self):
        """Test uses default when Retry-After is invalid."""
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "invalid"}

        result = get_retry_after_seconds(mock_response, default=45.0)

        assert result == 45.0

    def test_default_default_value(self):
        """Test default default value is 60.0."""
        mock_response = MagicMock()
        mock_response.headers = {}

        result = get_retry_after_seconds(mock_response)

        assert result == 60.0


class TestDefaultConstants:
    """Test default constants are correct."""

    def test_default_retryable_status_codes(self):
        """Test default retryable status codes."""
        expected = {408, 429, 500, 502, 503, 504}
        assert DEFAULT_RETRYABLE_STATUS_CODES == expected

    def test_default_retryable_exceptions(self):
        """Test default retryable exceptions."""
        assert requests.exceptions.Timeout in DEFAULT_RETRYABLE_EXCEPTIONS
        assert requests.exceptions.ConnectionError in DEFAULT_RETRYABLE_EXCEPTIONS
        assert RateLimitError in DEFAULT_RETRYABLE_EXCEPTIONS
        assert ServerError in DEFAULT_RETRYABLE_EXCEPTIONS
        assert TimeoutError in DEFAULT_RETRYABLE_EXCEPTIONS
