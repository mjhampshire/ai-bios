"""Claude API integration for bio generation."""

import json
import logging
from typing import Optional

import anthropic
from httpx import TimeoutException

logger = logging.getLogger(__name__)


class BioGenerationError(Exception):
    """Base exception for bio generation failures."""
    pass


class BioAPIError(BioGenerationError):
    """Claude API call failed."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class BioParseError(BioGenerationError):
    """Failed to parse Claude's response."""
    pass


class BioGenerator:
    """Generates customer bios using Claude API."""

    DEFAULT_TIMEOUT = 30.0  # seconds
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    DEFAULT_MAX_TOKENS = 1024

    def __init__(
        self,
        api_key: str,
        timeout: float = DEFAULT_TIMEOUT,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self.client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout,
        )
        self.timeout = timeout
        self.model = model
        self.max_tokens = max_tokens

    def generate(
        self,
        customer_data: dict,
        tone: str = "professional",  # professional, friendly, luxury
        include_conversation_starters: bool = True,
    ) -> dict:
        """
        Generate a bio from aggregated customer data.

        Returns:
            {
                "bio": "...",
                "conversation_starters": ["...", "..."],
            }

        Raises:
            BioAPIError: If Claude API call fails (rate limit, auth, network)
            BioParseError: If response cannot be parsed
        """
        prompt = self._build_prompt(customer_data, tone, include_conversation_starters)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.RateLimitError as e:
            retry_after = getattr(e, "retry_after", None)
            logger.warning(f"Rate limited by Claude API, retry_after={retry_after}")
            raise BioAPIError(
                "Rate limited by Claude API. Please try again later.",
                retry_after=retry_after,
            ) from e
        except anthropic.AuthenticationError as e:
            logger.error("Claude API authentication failed")
            raise BioAPIError("Invalid API key or authentication failed.") from e
        except anthropic.APIConnectionError as e:
            logger.error(f"Claude API connection error: {e}")
            raise BioAPIError("Failed to connect to Claude API.") from e
        except TimeoutException as e:
            logger.error(f"Claude API timeout after {self.timeout}s")
            raise BioAPIError(f"Request timed out after {self.timeout} seconds.") from e
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            raise BioAPIError(f"Claude API error: {e}") from e

        if not message.content:
            raise BioParseError("Empty response from Claude API")

        response_text = message.content[0].text
        return self._parse_response(response_text)

    def _build_prompt(
        self,
        data: dict,
        tone: str,
        include_starters: bool,
    ) -> str:
        tone_instructions = {
            "professional": "Use a professional, business-appropriate tone. Refer to the customer formally.",
            "friendly": "Use a warm, friendly tone. Be personable and casual.",
            "luxury": "Use an elegant, refined tone befitting a luxury retail experience.",
        }

        prompt = f"""You are a retail clienteling assistant. Generate a customer bio based on the data provided.

**Tone:** {tone_instructions.get(tone, tone_instructions["professional"])}

**Customer Data:**
```json
{json.dumps(data, indent=2, default=str)}
```

**Output Format:**
Write a bio with the following sections:

1. **Opening** (1 sentence): Customer name, tenure, and loyalty status.

2. **Style Profile** (2-3 sentences): Their style preferences, favorite categories, colors, brands. Include sizes if known. Mention any dislikes to avoid.

3. **Shopping Patterns** (1-2 sentences): How often they shop, average spend, preferred channel/store.

4. **Key Notes** (bullet points): Important personal details from staff notes. Only include if notes exist.

5. **Recent Activity** (1-2 sentences): What they've been browsing, wishlisted, or recently purchased.

"""
        if include_starters:
            prompt += """6. **Conversation Starters** (2-3 bullet points): Specific, actionable suggestions for engaging this customer based on their recent activity, wishlist, or purchase history.

"""

        prompt += """**Rules:**
- Only use information provided in the data. Do not invent details.
- If data is missing for a section, skip that section.
- Keep it concise - the entire bio should be readable in 30 seconds.
- For conversation starters, be specific (mention actual products or dates).
"""

        return prompt

    def _parse_response(self, response: str) -> dict:
        """
        Parse Claude's response into structured output.

        Validates:
        - Response is not empty
        - Response has minimum content length
        - Bio text is extractable

        Raises:
            BioParseError: If response is invalid or cannot be parsed
        """
        if not response:
            raise BioParseError("Empty response from Claude")

        response = response.strip()

        # Minimum length check - bio should have some content
        if len(response) < 50:
            raise BioParseError(f"Response too short ({len(response)} chars), expected bio content")

        # Extract conversation starters if present
        starters = self._extract_conversation_starters(response)

        return {
            "bio": response,
            "conversation_starters": starters,
        }

    def _extract_conversation_starters(self, response: str) -> list[str]:
        """Extract conversation starters from response text."""
        starters = []

        if "Conversation Starters" not in response:
            return starters

        # Get text after "Conversation Starters" header
        parts = response.split("Conversation Starters")
        if len(parts) < 2:
            return starters

        starter_section = parts[1]

        # Parse bullet points
        for line in starter_section.split("\n"):
            line = line.strip()

            # Stop if we hit another section header
            if line.startswith("**") and line.endswith("**"):
                break

            # Extract bullet items
            if line.startswith(("-", "•", "*")) and not line.startswith("**"):
                starter = line.lstrip("-•*").strip()
                if starter and len(starter) > 5:  # Ignore empty or very short items
                    starters.append(starter)

            if len(starters) >= 3:
                break

        return starters
