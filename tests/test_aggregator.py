"""Tests for BioDataAggregator."""

import pytest

from src.bios.aggregator import BioDataAggregator


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
