# AI-Generated Customer Bios - Design Document

**Status:** Draft
**Last Updated:** March 2025

---

## Overview

Generate AI-powered customer bio summaries to help retail staff quickly understand a customer's preferences, history, and relationship with the brand. These draft bios give staff a starting point when engaging with customers, especially those they haven't personally served before.

### Problem Statement

Today, customer bios are manually written by staff based on their personal knowledge and relationship with customers. This creates gaps:
- New staff lack context on existing customers
- Customers who shop across multiple stores/staff have fragmented knowledge
- Bio quality varies significantly
- Rich data (orders, wishlist, clickstream) isn't leveraged

### Solution

Use AI to generate a draft bio by synthesizing:
- **Purchase history** - What they buy, spend patterns, frequency
- **Wishlist data** - What they're interested in but haven't purchased
- **Clickstream** - Browsing behavior, categories explored
- **In-store notes** - Past staff interactions and observations
- **Preferences** - Stated likes/dislikes (colors, styles, brands, sizes)
- **Loyalty data** - Tier, points, tenure

---

## Data Sources

| Source | Data Points | Signal Strength |
|--------|-------------|-----------------|
| **Orders** | Categories, brands, colors, price points, frequency, recency, AOV, total spend | Strong |
| **Wishlist** | Desired items, price sensitivity, aspiration vs. purchase gap | Strong |
| **Preferences** | Explicit likes/dislikes for colors, styles, brands, fabrics | Very Strong |
| **In-store Notes** | Staff observations, special requests, personal details | Very Strong |
| **Clickstream** | Browse patterns, time spent, categories explored | Medium |
| **Loyalty** | Tier, tenure, engagement level | Medium |

---

## Bio Structure

### Proposed Format

```
[Customer Name] has been a [loyalty tier] customer since [year].

**Style Profile:**
[2-3 sentences on their style preferences, favorite categories, colors, brands]

**Shopping Patterns:**
[1-2 sentences on how they shop - frequency, AOV, online vs in-store]

**Key Notes:**
- [Bullet points from staff notes - important personal details]
- [Special requests or considerations]

**Recent Activity:**
[What they've been browsing/buying lately]

**Conversation Starters:**
- [Suggestion based on recent wishlist or browse activity]
- [Follow-up on recent purchase]
```

### Example Output

```
Sarah Chen has been a VIP customer since 2021.

**Style Profile:**
Sarah gravitates toward classic, minimalist pieces with a preference for
neutral tones - particularly navy, black, and cream. She favors Zimmermann
and Scanlan Theodore for special occasions, and appreciates quality silk
and cashmere fabrics. Her typical dress size is 10.

**Shopping Patterns:**
Sarah shops primarily in-store, visiting approximately once per month with
an average spend of $850. She often purchases during new season launches.

**Key Notes:**
- Works in corporate law, needs smart workwear
- Prefers appointments on Saturday mornings
- Allergic to wool - suggest cashmere or silk alternatives
- Has a daughter (Emma, 12) - occasionally shops for her too

**Recent Activity:**
Browsing summer dresses and resort wear. Added 3 items to wishlist last week
including the Zimmermann Linen Midi Dress in Navy ($695).

**Conversation Starters:**
- The Zimmermann dress she wishlisted just came back in her size
- Follow up on the Scanlan Theodore blazer purchased last month
- New cashmere collection just arrived - perfect for her preferences
```

---

## Technical Approach

### Option A: Direct LLM Generation

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Data Sources   │────▶│  Prompt Builder │────▶│    LLM API      │
│  (ClickHouse,   │     │  (Aggregate &   │     │  (Claude/GPT)   │
│   DynamoDB)     │     │   Format Data)  │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │   Draft Bio     │
                                               │   (Markdown)    │
                                               └─────────────────┘
```

**Pros:**
- Flexible, natural language output
- Can handle nuance and context
- Easy to adjust tone/style via prompt

**Cons:**
- Latency (~2-5 seconds)
- Cost per generation
- Potential for hallucination

### Option B: Hybrid (Structured + LLM Polish)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Data Sources   │────▶│  Aggregation    │────▶│  Template       │
│                 │     │  Service        │     │  Engine         │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Structured     │
                                               │  Summary        │
                                               └────────┬────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  LLM Polish     │
                                               │  (Optional)     │
                                               └────────┬────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │   Draft Bio     │
                                               └─────────────────┘
```

**Pros:**
- Faster (can show structured data immediately)
- More predictable output
- Lower cost (LLM optional)
- No hallucination risk for data

**Cons:**
- Less natural prose
- More rigid format

### Recommendation: Option A with Guardrails

Use direct LLM generation with:
1. **Structured data in prompt** - Pass aggregated facts, not raw data
2. **Output validation** - Verify key facts match source data
3. **Caching** - Cache generated bios, regenerate on significant changes
4. **Human review** - Staff can edit/approve before publishing

---

## Data Aggregation

Before calling the LLM, aggregate raw data into a structured summary:

```json
{
  "customer": {
    "name": "Sarah Chen",
    "customer_since": "2021-03",
    "loyalty_tier": "VIP",
    "lifetime_spend": 28500,
    "total_orders": 34
  },
  "preferences": {
    "likes": {
      "categories": ["Dresses", "Blazers", "Knitwear"],
      "colors": ["Navy", "Black", "Cream"],
      "brands": ["Zimmermann", "Scanlan Theodore"],
      "fabrics": ["Silk", "Cashmere"],
      "styles": ["Classic", "Minimalist"]
    },
    "dislikes": {
      "colors": ["Red", "Orange"],
      "fabrics": ["Wool"],
      "brands": ["Aje"]
    },
    "sizes": {
      "dress": "10",
      "top": "S"
    }
  },
  "shopping_behavior": {
    "avg_order_value": 850,
    "purchase_frequency_days": 30,
    "preferred_channel": "in_store",
    "last_purchase_date": "2025-02-15",
    "recent_categories": ["Dresses", "Accessories"]
  },
  "recent_activity": {
    "wishlist_items": [
      {"name": "Zimmermann Linen Midi Dress", "price": 695, "added": "2025-03-01"}
    ],
    "recent_views": ["Summer Dresses", "Resort Wear", "Linen Collection"],
    "cart_abandonment": []
  },
  "staff_notes": [
    {"date": "2025-01-20", "author": "Jane", "note": "Works in corporate law, needs smart workwear"},
    {"date": "2024-11-05", "author": "Mike", "note": "Allergic to wool - always suggest cashmere"},
    {"date": "2024-08-12", "author": "Jane", "note": "Has daughter Emma (12), occasionally shops for her"}
  ],
  "special_dates": {
    "birthday": "1985-06-15"
  }
}
```

---

## API Design

### Generate Bio

```http
POST /api/v1/customers/{customerId}/bio/generate
```

**Request:**
```json
{
  "style": "detailed",      // "detailed" | "brief" | "bullet_points"
  "include_notes": true,    // Include staff notes in generation
  "regenerate": false       // Force regeneration even if cached
}
```

**Response:**
```json
{
  "bio": "Sarah Chen has been a VIP customer since 2021...",
  "generated_at": "2025-03-07T10:30:00Z",
  "data_snapshot": {
    "orders_count": 34,
    "last_order": "2025-02-15",
    "wishlist_count": 5
  },
  "conversation_starters": [
    "The Zimmermann dress she wishlisted just came back in her size",
    "Follow up on the Scanlan Theodore blazer purchased last month"
  ],
  "confidence": 0.85,
  "is_cached": false
}
```

### Get Current Bio

```http
GET /api/v1/customers/{customerId}/bio
```

Returns the current bio (AI-generated draft or staff-edited version).

### Update Bio

```http
PUT /api/v1/customers/{customerId}/bio
```

Staff can edit and save the bio. Edited bios are marked as `staff_edited: true`.

---

## UI/UX Considerations

### Customer Profile Page

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Sarah Chen                                           ⭐ VIP Customer   │
│  sarah.chen@email.com | +61 412 345 678                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Bio                                            [✨ Regenerate] [Edit]  │
│  ───────────────────────────────────────────────────────────────────── │
│                                                                         │
│  Sarah Chen has been a VIP customer since 2021.                        │
│                                                                         │
│  **Style Profile:**                                                     │
│  Sarah gravitates toward classic, minimalist pieces with a preference  │
│  for neutral tones - particularly navy, black, and cream...            │
│                                                                         │
│  [See full bio ▼]                                                      │
│                                                                         │
│  💡 Conversation Starters:                                              │
│  • The Zimmermann dress she wishlisted just came back in her size      │
│  • New cashmere collection just arrived                                 │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  [Orders]  [Wishlist]  [Notes]  [Activity]                             │
│  ...                                                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Generation States

1. **No bio exists** - Show "Generate Bio" button
2. **Generating** - Show loading spinner with "Generating bio..."
3. **Draft ready** - Show bio with "AI Generated" badge
4. **Staff edited** - Show bio with "Edited by [name]" badge
5. **Outdated** - Show "New data available - Regenerate?" prompt

---

## Privacy & Compliance

- **Data minimization** - Only include relevant data in prompts
- **No PII in logs** - Don't log customer names or contact details
- **Audit trail** - Track who generated/edited bios and when
- **Opt-out** - Customers can opt out of AI-generated content
- **Staff notes sensitivity** - Flag sensitive notes, exclude from AI generation

---

## Caching Strategy

| Event | Action |
|-------|--------|
| Bio generated | Cache with 7-day TTL |
| New order placed | Mark bio as "outdated" |
| Wishlist updated | Mark bio as "outdated" |
| Staff note added | Mark bio as "outdated" |
| Preferences updated | Mark bio as "outdated" |
| Staff edits bio | Cache indefinitely (staff-owned) |

Outdated bios show a prompt to regenerate but remain visible.

---

## Questions to Resolve

1. **LLM Provider** - Claude (Anthropic) vs GPT (OpenAI) vs self-hosted?
2. **Bio ownership** - Once staff edits, should AI regeneration be disabled?
3. **Multiple bios** - One bio per customer, or per store/staff member?
4. **Real-time vs batch** - Generate on-demand or pre-generate overnight?
5. **Staff notes privacy** - Which notes should be included in AI generation?
6. **Tone customization** - Should retailers be able to customize bio tone/style?

---

## Next Steps

1. Finalize data aggregation schema
2. Design prompt templates
3. Build aggregation service (ClickHouse queries)
4. Implement generation API
5. Build UI components
6. Test with sample customer data
7. Staff feedback and iteration
