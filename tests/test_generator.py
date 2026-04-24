"""Tests for BioGenerator."""

import pytest
from unittest.mock import Mock, patch, MagicMock

import anthropic

from src.bios.generator import (
    BioGenerator,
    BioGenerationError,
    BioAPIError,
    BioParseError,
)


class TestBioGeneratorInit:
    """Tests for BioGenerator initialization."""

    def test_init_with_defaults(self):
        """Creates generator with default settings."""
        with patch.object(anthropic.Anthropic, "__init__", return_value=None):
            generator = BioGenerator(api_key="test-key")

            assert generator.timeout == 30.0
            assert generator.model == "claude-sonnet-4-20250514"
            assert generator.max_tokens == 1024

    def test_init_with_custom_settings(self):
        """Creates generator with custom settings."""
        with patch.object(anthropic.Anthropic, "__init__", return_value=None):
            generator = BioGenerator(
                api_key="test-key",
                timeout=60.0,
                model="claude-3-opus-20240229",
                max_tokens=2048,
            )

            assert generator.timeout == 60.0
            assert generator.model == "claude-3-opus-20240229"
            assert generator.max_tokens == 2048


class TestResponseParser:
    """Tests for parsing Claude's response."""

    def test_parse_response_with_starters(self):
        """Extracts conversation starters from response."""
        generator = BioGenerator.__new__(BioGenerator)

        response = """
Sarah Chen has been a VIP customer since 2021.

**Style Profile:**
She loves classic pieces in navy and black.

**Conversation Starters:**
- Ask about the Zimmermann dress she wishlisted
- Follow up on her recent blazer purchase
- Mention the new cashmere collection
"""

        result = generator._parse_response(response)

        assert result["bio"] == response.strip()
        assert len(result["conversation_starters"]) == 3
        assert "Zimmermann dress" in result["conversation_starters"][0]

    def test_parse_response_without_starters(self):
        """Handles response without conversation starters section."""
        generator = BioGenerator.__new__(BioGenerator)

        response = """
Sarah Chen has been a VIP customer since 2021.

**Style Profile:**
She loves classic pieces in navy and black.
"""

        result = generator._parse_response(response)

        assert result["bio"] == response.strip()
        assert result["conversation_starters"] == []

    def test_parse_response_bullet_variants(self):
        """Handles different bullet point formats."""
        generator = BioGenerator.__new__(BioGenerator)

        response = """
This is a valid bio with enough content to pass validation checks.

**Conversation Starters:**
• First starter item here
- Second starter item here
"""

        result = generator._parse_response(response)

        assert len(result["conversation_starters"]) == 2
        assert "First starter" in result["conversation_starters"][0]
        assert "Second starter" in result["conversation_starters"][1]


class TestResponseValidation:
    """Tests for response validation."""

    def test_empty_response_raises_error(self):
        """Raises BioParseError for empty response."""
        generator = BioGenerator.__new__(BioGenerator)

        with pytest.raises(BioParseError, match="Empty response"):
            generator._parse_response("")

    def test_none_response_raises_error(self):
        """Raises BioParseError for None response."""
        generator = BioGenerator.__new__(BioGenerator)

        with pytest.raises(BioParseError, match="Empty response"):
            generator._parse_response(None)

    def test_too_short_response_raises_error(self):
        """Raises BioParseError for response that's too short."""
        generator = BioGenerator.__new__(BioGenerator)

        with pytest.raises(BioParseError, match="too short"):
            generator._parse_response("Hi")

    def test_whitespace_only_response_raises_error(self):
        """Raises BioParseError for whitespace-only response."""
        generator = BioGenerator.__new__(BioGenerator)

        with pytest.raises(BioParseError, match="too short"):
            generator._parse_response("   \n\n   ")


class TestAPIErrorHandling:
    """Tests for API error handling."""

    def test_rate_limit_error(self):
        """Wraps RateLimitError in BioAPIError with retry_after."""
        generator = BioGenerator.__new__(BioGenerator)
        generator.model = "claude-sonnet-4-20250514"
        generator.max_tokens = 1024

        mock_client = Mock()
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            message="Rate limited",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limited"}},
        )
        generator.client = mock_client

        with pytest.raises(BioAPIError, match="Rate limited"):
            generator.generate({"customer": {"name": "Test"}})

    def test_auth_error(self):
        """Wraps AuthenticationError in BioAPIError."""
        generator = BioGenerator.__new__(BioGenerator)
        generator.model = "claude-sonnet-4-20250514"
        generator.max_tokens = 1024

        mock_client = Mock()
        mock_client.messages.create.side_effect = anthropic.AuthenticationError(
            message="Invalid API key",
            response=Mock(status_code=401),
            body={"error": {"message": "Invalid API key"}},
        )
        generator.client = mock_client

        with pytest.raises(BioAPIError, match="authentication"):
            generator.generate({"customer": {"name": "Test"}})

    def test_connection_error(self):
        """Wraps APIConnectionError in BioAPIError."""
        generator = BioGenerator.__new__(BioGenerator)
        generator.model = "claude-sonnet-4-20250514"
        generator.max_tokens = 1024

        mock_client = Mock()
        mock_client.messages.create.side_effect = anthropic.APIConnectionError(
            message="Connection failed"
        )
        generator.client = mock_client

        with pytest.raises(BioAPIError, match="connect"):
            generator.generate({"customer": {"name": "Test"}})

    def test_empty_content_raises_parse_error(self):
        """Raises BioParseError when API returns empty content."""
        generator = BioGenerator.__new__(BioGenerator)
        generator.model = "claude-sonnet-4-20250514"
        generator.max_tokens = 1024

        mock_message = Mock()
        mock_message.content = []  # Empty content

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_message
        generator.client = mock_client

        with pytest.raises(BioParseError, match="Empty response"):
            generator.generate({"customer": {"name": "Test"}})


class TestConversationStarterExtraction:
    """Tests for conversation starter extraction edge cases."""

    def test_stops_at_next_section(self):
        """Stops extracting starters when hitting next section."""
        generator = BioGenerator.__new__(BioGenerator)

        response = """
This is a valid bio with enough content to pass validation checks.

**Conversation Starters:**
- First starter item
- Second starter item

**Next Section:**
This is not a starter.
"""

        result = generator._parse_response(response)
        assert len(result["conversation_starters"]) == 2

    def test_ignores_empty_bullets(self):
        """Ignores empty or very short bullet items."""
        generator = BioGenerator.__new__(BioGenerator)

        response = """
This is a valid bio with enough content to pass validation checks.

**Conversation Starters:**
-
- Hi
- This is a real conversation starter about products
"""

        result = generator._parse_response(response)
        assert len(result["conversation_starters"]) == 1
        assert "real conversation starter" in result["conversation_starters"][0]

    def test_limits_to_three_starters(self):
        """Only extracts first 3 conversation starters."""
        generator = BioGenerator.__new__(BioGenerator)

        response = """
This is a valid bio with enough content to pass validation checks.

**Conversation Starters:**
- First starter item here
- Second starter item here
- Third starter item here
- Fourth starter should be ignored
- Fifth starter should be ignored
"""

        result = generator._parse_response(response)
        assert len(result["conversation_starters"]) == 3
