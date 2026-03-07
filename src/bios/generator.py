"""Claude API integration for bio generation."""

import json

import anthropic


class BioGenerator:
    """Generates customer bios using Claude API."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

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
        """
        prompt = self._build_prompt(customer_data, tone, include_conversation_starters)

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

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
        """Parse Claude's response into structured output."""
        # Extract conversation starters if present
        starters = []
        if "Conversation Starters" in response:
            lines = response.split("Conversation Starters")[1].split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("-") or line.startswith("•"):
                    starters.append(line.lstrip("-•").strip())
                if len(starters) >= 3:
                    break

        return {
            "bio": response,
            "conversation_starters": starters,
        }
