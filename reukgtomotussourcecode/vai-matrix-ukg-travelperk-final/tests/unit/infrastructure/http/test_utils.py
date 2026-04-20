"""Tests for HTTP shared utilities."""

import pytest
from unittest.mock import MagicMock

from src.infrastructure.http.utils import (
    parse_json_response,
    sanitize_url_for_logging,
    extract_retry_after,
)


class TestParseJsonResponse:
    """Test cases for parse_json_response function."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "value", "number": 123}

        result = parse_json_response(mock_response)

        assert result == {"key": "value", "number": 123}

    def test_parse_empty_json(self):
        """Test parsing empty JSON object."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}

        result = parse_json_response(mock_response)

        assert result == {}

    def test_parse_json_array(self):
        """Test parsing JSON array response."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]

        result = parse_json_response(mock_response)

        assert result == [{"id": 1}, {"id": 2}]

    def test_parse_invalid_json_returns_raw_text(self):
        """Test that invalid JSON returns raw text."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Not valid JSON content"

        result = parse_json_response(mock_response)

        assert result["raw_text"] == "Not valid JSON content"
        assert "parse_error" in result

    def test_parse_invalid_json_truncates_long_text(self):
        """Test that long error text is truncated to 500 chars."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "x" * 1000  # Long text

        result = parse_json_response(mock_response)

        assert len(result["raw_text"]) == 500
        assert result["raw_text"] == "x" * 500

    def test_parse_json_decode_error(self):
        """Test handling JSONDecodeError."""
        import json

        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_response.text = "HTML error page"

        result = parse_json_response(mock_response)

        assert result["raw_text"] == "HTML error page"
        assert "parse_error" in result


class TestSanitizeUrlForLogging:
    """Test cases for sanitize_url_for_logging function."""

    def test_url_without_query_params(self):
        """Test URL without query parameters."""
        url = "https://api.example.com/users/123"

        result = sanitize_url_for_logging(url)

        assert result == "https://api.example.com/users/123"

    def test_url_with_query_params(self):
        """Test URL with query parameters are removed."""
        url = "https://api.example.com/users?api_key=secret&id=123"

        result = sanitize_url_for_logging(url)

        assert result == "https://api.example.com/users"

    def test_url_with_multiple_question_marks(self):
        """Test URL with multiple question marks."""
        url = "https://api.example.com/search?q=what?&limit=10"

        result = sanitize_url_for_logging(url)

        assert result == "https://api.example.com/search"

    def test_empty_url(self):
        """Test empty URL string."""
        result = sanitize_url_for_logging("")

        assert result == ""

    def test_url_with_only_query_string(self):
        """Test URL that is only query string."""
        result = sanitize_url_for_logging("?key=value")

        assert result == ""

    def test_url_with_fragment(self):
        """Test URL with fragment is preserved."""
        url = "https://api.example.com/docs#section"

        result = sanitize_url_for_logging(url)

        # Fragment should be preserved since we only split on ?
        assert result == "https://api.example.com/docs#section"


class TestExtractRetryAfter:
    """Test cases for extract_retry_after function."""

    def test_extract_retry_after_header_present(self):
        """Test extracting Retry-After when header is present."""
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "120"}

        result = extract_retry_after(mock_response)

        assert result == 120

    def test_extract_retry_after_header_missing(self):
        """Test default value when Retry-After header is missing."""
        mock_response = MagicMock()
        mock_response.headers = {}

        result = extract_retry_after(mock_response)

        assert result == 60  # Default value

    def test_extract_retry_after_custom_default(self):
        """Test custom default value."""
        mock_response = MagicMock()
        mock_response.headers = {}

        result = extract_retry_after(mock_response, default=30)

        assert result == 30

    def test_extract_retry_after_invalid_value(self):
        """Test fallback when Retry-After is not a valid integer."""
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "not-a-number"}

        result = extract_retry_after(mock_response)

        assert result == 60  # Default value

    def test_extract_retry_after_zero_value(self):
        """Test zero Retry-After value."""
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "0"}

        result = extract_retry_after(mock_response)

        assert result == 0

    def test_extract_retry_after_large_value(self):
        """Test large Retry-After value."""
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "3600"}

        result = extract_retry_after(mock_response)

        assert result == 3600

    def test_extract_retry_after_with_title_case_header(self):
        """Test header with standard title case."""
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "45"}

        result = extract_retry_after(mock_response)

        assert result == 45

    def test_extract_retry_after_float_value(self):
        """Test float Retry-After value falls back to default."""
        mock_response = MagicMock()
        mock_response.headers = {"Retry-After": "30.5"}

        result = extract_retry_after(mock_response)

        assert result == 60  # Falls back to default since int() would fail
