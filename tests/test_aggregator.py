"""Tests for BioDataAggregator."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from src.bios.aggregator import BioDataAggregator


class TestMessageTruncation:
    """Tests for message truncation."""

    def test_truncate_short_message(self):
        """Short messages are not truncated."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)
        result = aggregator._truncate_message("Short message")

        assert result == "Short message"

    def test_truncate_exact_limit(self):
        """Message at exact limit is not truncated."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)
        message = "x" * 500
        result = aggregator._truncate_message(message)

        assert result == message
        assert len(result) == 500

    def test_truncate_long_message(self):
        """Long messages are truncated with ellipsis."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)
        message = "x" * 600
        result = aggregator._truncate_message(message)

        assert len(result) == 500
        assert result.endswith("...")

    def test_truncate_custom_limit(self):
        """Respects custom max_length."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)
        message = "This is a test message"
        result = aggregator._truncate_message(message, max_length=10)

        assert result == "This is..."
        assert len(result) == 10

    def test_truncate_none_message(self):
        """Handles None message."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)
        result = aggregator._truncate_message(None)

        assert result is None

    def test_truncate_empty_message(self):
        """Handles empty message."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)
        result = aggregator._truncate_message("")

        assert result == ""


class TestSafeFetch:
    """Tests for safe fetch with error handling."""

    def test_safe_fetch_success(self):
        """Returns result on success."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)

        def mock_fetch(tenant_id, customer_ref):
            return {"name": "Test Customer"}

        key, result = aggregator._safe_fetch(
            "customer", mock_fetch, {}, "tenant-1", "CUST001"
        )

        assert key == "customer"
        assert result == {"name": "Test Customer"}

    def test_safe_fetch_failure_returns_default(self):
        """Returns default value on failure."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)

        def mock_fetch(tenant_id, customer_ref):
            raise Exception("Database connection failed")

        default = {"name": "Unknown"}
        key, result = aggregator._safe_fetch(
            "customer", mock_fetch, default, "tenant-1", "CUST001"
        )

        assert key == "customer"
        assert result == default

    def test_safe_fetch_logs_warning_on_failure(self):
        """Logs warning when fetch fails."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)

        def mock_fetch(tenant_id, customer_ref):
            raise Exception("Query timeout")

        with patch("src.bios.aggregator.logger") as mock_logger:
            aggregator._safe_fetch(
                "wishlist", mock_fetch, [], "tenant-1", "CUST001"
            )

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "wishlist" in call_args
            assert "tenant-1" in call_args


class TestPreferencesParser:
    """Tests for preferences JSON parsing."""

    def test_parse_empty_preferences(self):
        """Empty JSON returns empty likes/dislikes."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)
        result = aggregator._parse_preferences_json("{}")

        assert result == {"likes": {}, "dislikes": {}, "sizes": {}}

    def test_parse_invalid_json(self):
        """Invalid JSON returns empty result."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)
        result = aggregator._parse_preferences_json("not valid json")

        assert result == {"likes": {}, "dislikes": {}, "sizes": {}}

    def test_parse_likes(self):
        """Parses likes correctly."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)
        prefs_json = """{
            "categories": [{"id": "dresses", "value": "Dresses", "dislike": false}],
            "colours": [{"id": "navy", "value": "Navy"}]
        }"""

        result = aggregator._parse_preferences_json(prefs_json)

        assert "Dresses" in result["likes"]["categories"]
        assert "Navy" in result["likes"]["colors"]

    def test_parse_dislikes(self):
        """Parses dislikes correctly."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)
        prefs_json = """{
            "categories": [{"id": "shorts", "value": "Shorts", "dislike": true}],
            "colours": [{"id": "red", "value": "Red", "dislike": true}]
        }"""

        result = aggregator._parse_preferences_json(prefs_json)

        assert "Shorts" in result["dislikes"]["categories"]
        assert "Red" in result["dislikes"]["colors"]

    def test_parse_sizes(self):
        """Parses sizes correctly."""
        aggregator = BioDataAggregator.__new__(BioDataAggregator)
        prefs_json = """{
            "dresses": [{"id": "size_10", "value": "10"}],
            "tops": [{"id": "size_s", "value": "S"}]
        }"""

        result = aggregator._parse_preferences_json(prefs_json)

        assert result["sizes"]["dresses"] == "10"
        assert result["sizes"]["tops"] == "S"
