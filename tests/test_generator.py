"""Tests for BioGenerator."""

import pytest

from src.bios.generator import BioGenerator


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

        assert result["bio"] == response
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

        assert result["bio"] == response
        assert result["conversation_starters"] == []

    def test_parse_response_bullet_variants(self):
        """Handles different bullet point formats."""
        generator = BioGenerator.__new__(BioGenerator)

        response = """
**Conversation Starters:**
• First starter
- Second starter
"""

        result = generator._parse_response(response)

        assert len(result["conversation_starters"]) == 2
        assert "First starter" in result["conversation_starters"][0]
        assert "Second starter" in result["conversation_starters"][1]
