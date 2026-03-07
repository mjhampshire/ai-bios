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

| Source | Table(s) | Data Points | Signal Strength |
|--------|----------|-------------|-----------------|
| **Customer Profile** | `TWCCUSTOMER` | VIP status, loyalty tier, member since, preferred store | Strong |
| **Orders** | `TWCALLORDERS`, `ORDERLINE`, `TWCVARIANT` | Categories, brands, colors, price points, frequency, AOV | Strong |
| **Wishlist** | `TWCWISHLIST`, `WISHLISTITEM` | Desired items, price sensitivity, customer interest level | Strong |
| **Preferences** | `TWCPREFERENCES` | Explicit likes/dislikes for colors, styles, brands, fabrics | Very Strong |
| **Customer Messages** | `TWCCUSTOMER_MESSAGE` | Messages sent by customer (`isReply = '1'`) | Strong |
| **Staff Notes** | `TWCNOTES` (to be added) | Staff observations, special requests, personal details | Very Strong |
| **Clickstream** | `TWCCLICKSTREAM` | Browse patterns, categories explored, brands viewed | Medium |
| **Gorgias (Future)** | External API | Sentiment, open tickets, support history | Medium |

---

## ClickHouse Schema & Queries

### Tables Used

```
TWCCUSTOMER          - Customer profile, loyalty, VIP status
TWCPREFERENCES       - Preferences JSON (likes/dislikes)
TWCALLORDERS         - Order headers
ORDERLINE            - Order line items
TWCVARIANT           - Product catalog (for enrichment)
TWCWISHLIST          - Wishlist headers
WISHLISTITEM         - Wishlist items
TWCCLICKSTREAM       - Browsing behavior
TWCCUSTOMER_MESSAGE  - Customer messages (isReply = '1')
TWCNOTES             - Staff notes (to be added)
```

### Aggregation Queries

All queries filter by `tenantId` and `customerRef`.

#### 1. Customer Profile

```sql
SELECT
    customerId,
    customerRef,
    firstName,
    lastName,
    vipStatus,
    loyaltyTier,
    memberSince,
    preferredStore,
    usualStore
FROM TWCCUSTOMER
WHERE tenantId = {tenant_id:String}
  AND customerRef = {customer_ref:String}
  AND deleted = '0'
LIMIT 1
```

#### 2. Preferences (Likes/Dislikes)

```sql
SELECT
    preferences,
    rangeName,
    updatedAt
FROM TWCPREFERENCES
WHERE tenantId = {tenant_id:String}
  AND customerId = {customer_id:String}
  AND deleted = '0'
ORDER BY isPrimary DESC, updatedAt DESC
LIMIT 1
```

The `preferences` field contains JSON with structure:
```json
{
  "categories": [{"id": "dresses", "value": "Dresses", "source": "staff", "dislike": false}],
  "colours": [{"id": "navy", "value": "Navy", "source": "customer"}],
  "dresses": [{"id": "size_10", "value": "10"}],
  ...
}
```

#### 3. Purchase History Summary

```sql
SELECT
    count(DISTINCT o.orderId) as total_orders,
    sum(o.amount) as lifetime_spend,
    avg(o.amount) as avg_order_value,
    max(o.orderDate) as last_purchase_date,
    min(o.orderDate) as first_purchase_date,
    dateDiff('day', max(o.orderDate), now()) as days_since_last_purchase
FROM TWCALLORDERS o
WHERE o.tenantId = {tenant_id:String}
  AND o.customerRef = {customer_ref:String}
```

#### 4. Top Categories, Brands, Colors (from orders)

```sql
SELECT
    v.category,
    v.brand,
    v.color,
    count(*) as purchase_count,
    sum(ol.orderLineValue) as total_spend
FROM ORDERLINE ol
JOIN TWCVARIANT v ON ol.variantRef = v.variantRef AND ol.tenantId = v.tenantId
WHERE ol.tenantId = {tenant_id:String}
  AND ol.customerRef = {customer_ref:String}
GROUP BY v.category, v.brand, v.color
ORDER BY purchase_count DESC
LIMIT 20
```

#### 5. Recent Purchases (last 6 months)

```sql
SELECT
    ol.orderLineDate,
    ol.variantName,
    ol.orderLineValue,
    v.brand,
    v.category,
    v.color
FROM ORDERLINE ol
JOIN TWCVARIANT v ON ol.variantRef = v.variantRef AND ol.tenantId = v.tenantId
WHERE ol.tenantId = {tenant_id:String}
  AND ol.customerRef = {customer_ref:String}
  AND ol.orderLineDate >= now() - INTERVAL 6 MONTH
ORDER BY ol.orderLineDate DESC
LIMIT 10
```

#### 6. Active Wishlist Items

```sql
SELECT
    wi.productName,
    wi.variantName,
    wi.price,
    wi.category,
    wi.brandId,
    wi.customerInterest,
    wi.createdAt
FROM TWCWISHLIST w
JOIN WISHLISTITEM wi ON w.wishlistId = wi.wishlistId AND w.tenantId = wi.tenantId
WHERE w.tenantId = {tenant_id:String}
  AND w.customerRef = {customer_ref:String}
  AND w.deleted = '0'
  AND wi.deleted = '0'
  AND wi.purchased = '0'
ORDER BY wi.createdAt DESC
LIMIT 10
```

#### 7. Recent Browsing (last 30 days)

```sql
SELECT
    productType,
    brand,
    collectionName,
    count(*) as view_count
FROM TWCCLICKSTREAM
WHERE tenantId = {tenant_id:String}
  AND customerRef = {customer_ref:String}
  AND timeStamp >= now() - INTERVAL 30 DAY
GROUP BY productType, brand, collectionName
ORDER BY view_count DESC
LIMIT 15
```

#### 8. Customer Messages (sent by customer)

```sql
SELECT
    message,
    subjectLine,
    createdAt,
    staffFirstName,
    storeName
FROM TWCCUSTOMER_MESSAGE
WHERE tenantId = {tenant_id:String}
  AND customerRef = {customer_ref:String}
  AND isReply = '1'
ORDER BY createdAt DESC
LIMIT 10
```

#### 9. Staff Notes (when table is added)

```sql
-- Placeholder for TWCNOTES table
SELECT
    note,
    createdAt,
    createdBy,
    staffName
FROM TWCNOTES
WHERE tenantId = {tenant_id:String}
  AND customerRef = {customer_ref:String}
ORDER BY createdAt DESC
LIMIT 20
```

### Query Execution Strategy

Run queries in parallel for performance:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Parallel Query Execution                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Customer     │  │ Preferences  │  │ Orders       │          │
│  │ Profile      │  │              │  │ Summary      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Top Cats/    │  │ Recent       │  │ Wishlist     │          │
│  │ Brands       │  │ Purchases    │  │ Items        │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Browsing     │  │ Customer     │  │ Staff        │          │
│  │ History      │  │ Messages     │  │ Notes        │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  Total: ~300-500ms (parallel)                                  │
└─────────────────────────────────────────────────────────────────┘
```

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
    "customer_ref": "cust_12345",
    "customer_since": "2021-03",
    "vip_status": "VIP",
    "loyalty_tier": "Gold",
    "preferred_store": "Sydney CBD",
    "usual_store": "Sydney CBD"
  },
  "purchase_summary": {
    "total_orders": 34,
    "lifetime_spend": 28500,
    "avg_order_value": 838,
    "first_purchase_date": "2021-03-15",
    "last_purchase_date": "2025-02-15",
    "days_since_last_purchase": 20
  },
  "top_purchased": {
    "categories": [
      {"name": "Dresses", "count": 18, "spend": 14200},
      {"name": "Tops", "count": 12, "spend": 6800}
    ],
    "brands": [
      {"name": "Zimmermann", "count": 15, "spend": 12500},
      {"name": "Scanlan Theodore", "count": 8, "spend": 5200}
    ],
    "colors": [
      {"name": "Navy", "count": 12},
      {"name": "Black", "count": 10}
    ]
  },
  "recent_purchases": [
    {"date": "2025-02-15", "item": "Scanlan Theodore Blazer", "brand": "Scanlan Theodore", "price": 695},
    {"date": "2025-01-20", "item": "Zimmermann Silk Dress", "brand": "Zimmermann", "price": 850}
  ],
  "preferences": {
    "likes": {
      "categories": ["Dresses", "Blazers"],
      "colors": ["Navy", "Black", "Cream"],
      "brands": ["Zimmermann", "Scanlan Theodore"],
      "fabrics": ["Silk", "Cashmere"]
    },
    "dislikes": {
      "colors": ["Red"],
      "fabrics": ["Wool"],
      "brands": ["Aje"]
    },
    "sizes": {
      "dresses": "10",
      "tops": "S"
    }
  },
  "wishlist": {
    "count": 5,
    "items": [
      {"name": "Zimmermann Linen Midi Dress", "price": 695, "interest": "high", "added": "2025-03-01"},
      {"name": "Camilla Silk Scarf", "price": 220, "interest": "medium", "added": "2025-02-28"}
    ]
  },
  "recent_browsing": {
    "categories": ["Dresses", "Resort Wear", "Accessories"],
    "brands": ["Zimmermann", "Camilla"],
    "collections": ["Summer 2025", "Resort"]
  },
  "customer_messages": [
    {"date": "2025-02-10", "message": "Hi, do you have the navy dress in size 10?", "store": "Sydney CBD"},
    {"date": "2025-01-05", "message": "Thanks for letting me know about the sale!"}
  ],
  "staff_notes": [
    {"date": "2025-01-20", "author": "Jane", "note": "Works in corporate law, needs smart workwear"},
    {"date": "2024-11-05", "author": "Mike", "note": "Allergic to wool - always suggest cashmere"},
    {"date": "2024-08-12", "author": "Jane", "note": "Has daughter Emma (12), occasionally shops for her"}
  ],
  "gorgias": {
    "status": "not_integrated",
    "sentiment": null,
    "open_tickets": null
  }
}
```

### Future: Gorgias Integration

When integrated, Gorgias data will include:
- **Sentiment score** - Overall customer sentiment from support interactions
- **Open tickets** - Active support issues to be aware of
- **Recent interactions** - Summary of support conversations

This helps staff understand if a customer has unresolved issues before engaging.

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

## Caching & Preservation Strategy

### Bio Preservation Rules

**AI will NEVER overwrite a bio automatically.** Regeneration only happens when explicitly requested by user.

| Scenario | What User Sees | Regenerate Option |
|----------|----------------|-------------------|
| No bio exists | "Generate AI Bio" button | Yes (first generation) |
| Bio exists, data unchanged | Cached bio with "AI Generated" badge | No |
| Bio exists, new data available | Cached bio + "New activity - Refresh?" | Yes, on click |
| Staff-edited bio | Cached bio with "Edited by X" badge | No (AI disabled) |
| Staff-edited bio, user wants AI | Must click "Reset to AI" with confirmation | Yes, after confirm |

### Staleness Tracking

| Event | Action |
|-------|--------|
| Bio generated | Cache with `generated_at` timestamp |
| New order placed | Mark bio as `is_stale: true` |
| Wishlist updated | Mark bio as `is_stale: true` |
| Staff note added | Mark bio as `is_stale: true` |
| Preferences updated | Mark bio as `is_stale: true` |
| Staff edits bio | Set `is_staff_edited: true`, AI disabled |

Stale bios remain visible with a non-intrusive prompt to refresh. The prompt shows what changed (e.g., "2 new orders since last update").

---

## Performance & Generation Strategy

### Latency Considerations

| Operation | Latency | Notes |
|-----------|---------|-------|
| Claude API call | 2-5 seconds | Depends on bio length, model load |
| Data aggregation (ClickHouse) | 200-500ms | Parallel queries |
| Cached bio retrieval | <100ms | DynamoDB read |

### Hybrid Approach (Recommended)

To avoid unexpected delays, use explicit user-triggered generation:

**Scenario A: No bio exists**
```
┌─────────────────────────────────────────────────────────────┐
│  No AI bio generated yet                                    │
│                                                             │
│  [✨ Generate AI Bio]                                       │
└─────────────────────────────────────────────────────────────┘
```

**Scenario B: Cached bio (fresh)**
```
┌─────────────────────────────────────────────────────────────┐
│  Sarah gravitates toward classic, minimalist pieces...     │
│  ...                                                        │
│                                          🤖 AI Generated   │
└─────────────────────────────────────────────────────────────┘
```

**Scenario C: Cached bio (stale - new data available)**
```
┌─────────────────────────────────────────────────────────────┐
│  Sarah gravitates toward classic, minimalist pieces...     │
│  ...                                                        │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ ℹ️ New activity since Mar 1   [🔄 Refresh Bio]        │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Scenario D: Staff-edited bio (AI disabled)**
```
┌─────────────────────────────────────────────────────────────┐
│  Sarah is a wonderful long-term client who works in law... │
│  ...                                                        │
│                              ✏️ Edited by Jane on Mar 5    │
└─────────────────────────────────────────────────────────────┘
```
No regenerate option shown - staff owns this bio.

### Generation Flow

```
User clicks "Generate AI Bio"
         │
         ▼
┌─────────────────────┐
│  Show loading state │
│  "Generating bio... │
│   This takes a few  │
│   seconds"          │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐     ┌─────────────────────┐
│  Aggregate customer │────▶│  Call Claude API    │
│  data (parallel)    │     │  with prompt        │
│  ~300ms             │     │  ~2-4s              │
└─────────────────────┘     └─────────┬───────────┘
                                      │
                                      ▼
                            ┌─────────────────────┐
                            │  Cache bio in       │
                            │  DynamoDB           │
                            └─────────┬───────────┘
                                      │
                                      ▼
                            ┌─────────────────────┐
                            │  Display bio with   │
                            │  "AI Generated"     │
                            │  badge              │
                            └─────────────────────┘
```

### Why Not Auto-Generate?

| Approach | Pros | Cons |
|----------|------|------|
| Auto on page load | Seamless UX once cached | 2-5s delay on first/stale view; unexpected |
| Click to generate | User expects delay; transparent | Extra click required |
| Background batch | Always fresh; no delay | Stale data; compute cost for inactive customers |

**Recommendation:** Click-to-generate is more transparent and avoids frustrating users with unexpected delays. The loading state sets expectations.

---

## Design Decisions

| Question | Decision |
|----------|----------|
| **LLM Provider** | Claude (Anthropic) |
| **Bio ownership** | Once staff edits, AI regeneration is disabled for that customer |
| **Staff notes** | Include all notes in generation |
| **Generation trigger** | On-demand with "Generate AI Bio" button (see Performance section) |
| **Tone customization** | Per-retailer configuration (professional vs friendly) |

---

## Implementation Details

### 1. Data Aggregation Service

Python service using `clickhouse-connect` to run queries in parallel:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
import clickhouse_connect
import json

class BioDataAggregator:
    """Aggregates customer data from ClickHouse for bio generation."""

    def __init__(self, clickhouse_config: dict):
        self.client = clickhouse_connect.get_client(
            host=clickhouse_config['host'],
            port=clickhouse_config['port'],
            username=clickhouse_config['username'],
            password=clickhouse_config['password'],
            database=clickhouse_config['database'],
        )
        self.executor = ThreadPoolExecutor(max_workers=10)

    async def aggregate(self, tenant_id: str, customer_ref: str) -> dict:
        """
        Aggregate all customer data in parallel.
        Returns structured dict ready for prompt injection.
        """
        loop = asyncio.get_event_loop()

        # Run all queries in parallel
        results = await asyncio.gather(
            loop.run_in_executor(self.executor, self._fetch_customer_profile, tenant_id, customer_ref),
            loop.run_in_executor(self.executor, self._fetch_preferences, tenant_id, customer_ref),
            loop.run_in_executor(self.executor, self._fetch_purchase_summary, tenant_id, customer_ref),
            loop.run_in_executor(self.executor, self._fetch_top_purchased, tenant_id, customer_ref),
            loop.run_in_executor(self.executor, self._fetch_recent_purchases, tenant_id, customer_ref),
            loop.run_in_executor(self.executor, self._fetch_wishlist, tenant_id, customer_ref),
            loop.run_in_executor(self.executor, self._fetch_browsing, tenant_id, customer_ref),
            loop.run_in_executor(self.executor, self._fetch_customer_messages, tenant_id, customer_ref),
            loop.run_in_executor(self.executor, self._fetch_staff_notes, tenant_id, customer_ref),
        )

        return {
            "customer": results[0],
            "preferences": results[1],
            "purchase_summary": results[2],
            "top_purchased": results[3],
            "recent_purchases": results[4],
            "wishlist": results[5],
            "recent_browsing": results[6],
            "customer_messages": results[7],
            "staff_notes": results[8],
        }

    def _fetch_customer_profile(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query("""
            SELECT
                firstName, lastName, vipStatus, loyaltyTier,
                memberSince, preferredStore, usualStore
            FROM TWCCUSTOMER
            WHERE tenantId = {tenant_id:String}
              AND customerRef = {customer_ref:String}
              AND deleted = '0'
            LIMIT 1
        """, parameters={"tenant_id": tenant_id, "customer_ref": customer_ref})

        if result.row_count == 0:
            return {}

        row = result.first_row
        return {
            "name": f"{row[0]} {row[1]}".strip(),
            "first_name": row[0],
            "vip_status": row[2],
            "loyalty_tier": row[3],
            "member_since": row[4].strftime("%Y-%m") if row[4] else None,
            "preferred_store": row[5],
            "usual_store": row[6],
        }

    def _fetch_preferences(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query("""
            SELECT preferences
            FROM TWCPREFERENCES
            WHERE tenantId = {tenant_id:String}
              AND customerRef = {customer_ref:String}
              AND deleted = '0'
            ORDER BY isPrimary DESC, updatedAt DESC
            LIMIT 1
        """, parameters={"tenant_id": tenant_id, "customer_ref": customer_ref})

        if result.row_count == 0:
            return {"likes": {}, "dislikes": {}, "sizes": {}}

        prefs_json = result.first_row[0]
        return self._parse_preferences_json(prefs_json)

    def _parse_preferences_json(self, prefs_json: str) -> dict:
        """Parse the preferences JSON into likes/dislikes/sizes."""
        try:
            data = json.loads(prefs_json) if prefs_json else {}
        except json.JSONDecodeError:
            return {"likes": {}, "dislikes": {}, "sizes": {}}

        likes = {"categories": [], "colors": [], "brands": [], "fabrics": []}
        dislikes = {"categories": [], "colors": [], "brands": [], "fabrics": []}
        sizes = {}

        # Categories
        for item in data.get("categories", []):
            target = dislikes if item.get("dislike") else likes
            target["categories"].append(item.get("value"))

        # Colors
        for item in data.get("colours", []):
            target = dislikes if item.get("dislike") else likes
            target["colors"].append(item.get("value"))

        # Sizes by category
        size_fields = ["dresses", "tops", "bottoms", "footwear"]
        for field in size_fields:
            items = data.get(field, [])
            if items:
                sizes[field] = items[0].get("value")

        return {"likes": likes, "dislikes": dislikes, "sizes": sizes}

    def _fetch_purchase_summary(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query("""
            SELECT
                count(DISTINCT orderId) as total_orders,
                sum(amount) as lifetime_spend,
                avg(amount) as avg_order_value,
                min(orderDate) as first_purchase,
                max(orderDate) as last_purchase,
                dateDiff('day', max(orderDate), now()) as days_since_last
            FROM TWCALLORDERS
            WHERE tenantId = {tenant_id:String}
              AND customerRef = {customer_ref:String}
        """, parameters={"tenant_id": tenant_id, "customer_ref": customer_ref})

        row = result.first_row
        return {
            "total_orders": row[0] or 0,
            "lifetime_spend": float(row[1] or 0),
            "avg_order_value": round(float(row[2] or 0)),
            "first_purchase_date": row[3].strftime("%Y-%m-%d") if row[3] else None,
            "last_purchase_date": row[4].strftime("%Y-%m-%d") if row[4] else None,
            "days_since_last_purchase": row[5] or 0,
        }

    def _fetch_top_purchased(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query("""
            SELECT
                v.category, v.brand, v.color,
                count(*) as cnt, sum(ol.orderLineValue) as spend
            FROM ORDERLINE ol
            JOIN TWCVARIANT v ON ol.variantRef = v.variantRef AND ol.tenantId = v.tenantId
            WHERE ol.tenantId = {tenant_id:String}
              AND ol.customerRef = {customer_ref:String}
            GROUP BY v.category, v.brand, v.color
            ORDER BY cnt DESC
            LIMIT 20
        """, parameters={"tenant_id": tenant_id, "customer_ref": customer_ref})

        categories, brands, colors = {}, {}, {}
        for row in result.result_rows:
            cat, brand, color, cnt, spend = row
            if cat:
                categories[cat] = categories.get(cat, 0) + cnt
            if brand:
                brands[brand] = brands.get(brand, 0) + cnt
            if color:
                colors[color] = colors.get(color, 0) + cnt

        return {
            "categories": sorted(categories.keys(), key=lambda x: categories[x], reverse=True)[:5],
            "brands": sorted(brands.keys(), key=lambda x: brands[x], reverse=True)[:5],
            "colors": sorted(colors.keys(), key=lambda x: colors[x], reverse=True)[:5],
        }

    def _fetch_recent_purchases(self, tenant_id: str, customer_ref: str) -> list:
        result = self.client.query("""
            SELECT ol.orderLineDate, ol.variantName, ol.orderLineValue, v.brand, v.category
            FROM ORDERLINE ol
            JOIN TWCVARIANT v ON ol.variantRef = v.variantRef AND ol.tenantId = v.tenantId
            WHERE ol.tenantId = {tenant_id:String}
              AND ol.customerRef = {customer_ref:String}
              AND ol.orderLineDate >= now() - INTERVAL 6 MONTH
            ORDER BY ol.orderLineDate DESC
            LIMIT 5
        """, parameters={"tenant_id": tenant_id, "customer_ref": customer_ref})

        return [
            {"date": row[0].strftime("%Y-%m-%d"), "item": row[1], "price": row[2], "brand": row[3]}
            for row in result.result_rows
        ]

    def _fetch_wishlist(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query("""
            SELECT wi.productName, wi.price, wi.customerInterest, wi.createdAt, wi.brandId
            FROM TWCWISHLIST w
            JOIN WISHLISTITEM wi ON w.wishlistId = wi.wishlistId AND w.tenantId = wi.tenantId
            WHERE w.tenantId = {tenant_id:String}
              AND w.customerRef = {customer_ref:String}
              AND w.deleted = '0' AND wi.deleted = '0' AND wi.purchased = '0'
            ORDER BY wi.createdAt DESC
            LIMIT 5
        """, parameters={"tenant_id": tenant_id, "customer_ref": customer_ref})

        items = [
            {"name": row[0], "price": row[1], "interest": row[2], "brand": row[4]}
            for row in result.result_rows
        ]
        return {"count": len(items), "items": items}

    def _fetch_browsing(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query("""
            SELECT productType, brand, count(*) as cnt
            FROM TWCCLICKSTREAM
            WHERE tenantId = {tenant_id:String}
              AND customerRef = {customer_ref:String}
              AND timeStamp >= now() - INTERVAL 30 DAY
            GROUP BY productType, brand
            ORDER BY cnt DESC
            LIMIT 10
        """, parameters={"tenant_id": tenant_id, "customer_ref": customer_ref})

        categories, brands = {}, {}
        for row in result.result_rows:
            if row[0]:
                categories[row[0]] = categories.get(row[0], 0) + row[2]
            if row[1]:
                brands[row[1]] = brands.get(row[1], 0) + row[2]

        return {
            "categories": sorted(categories.keys(), key=lambda x: categories[x], reverse=True)[:5],
            "brands": sorted(brands.keys(), key=lambda x: brands[x], reverse=True)[:5],
        }

    def _fetch_customer_messages(self, tenant_id: str, customer_ref: str) -> list:
        result = self.client.query("""
            SELECT message, createdAt, storeName
            FROM TWCCUSTOMER_MESSAGE
            WHERE tenantId = {tenant_id:String}
              AND customerRef = {customer_ref:String}
              AND isReply = '1'
            ORDER BY createdAt DESC
            LIMIT 5
        """, parameters={"tenant_id": tenant_id, "customer_ref": customer_ref})

        return [
            {"message": row[0], "date": row[1].strftime("%Y-%m-%d"), "store": row[2]}
            for row in result.result_rows
        ]

    def _fetch_staff_notes(self, tenant_id: str, customer_ref: str) -> list:
        # Placeholder - implement when TWCNOTES table is added
        return []
```

### 2. Claude API Integration

Using the `anthropic` Python SDK:

```python
import anthropic
from typing import Optional

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
            messages=[
                {"role": "user", "content": prompt}
            ]
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
```

### 3. Bio Service (Orchestration)

Combines aggregation and generation:

```python
from datetime import datetime
from typing import Optional
import hashlib

class BioService:
    """Orchestrates bio generation and caching."""

    def __init__(
        self,
        aggregator: BioDataAggregator,
        generator: BioGenerator,
        cache: BioCacheRepository,  # DynamoDB
        settings: RetailerSettingsRepository,
    ):
        self.aggregator = aggregator
        self.generator = generator
        self.cache = cache
        self.settings = settings

    async def get_bio(self, tenant_id: str, customer_ref: str) -> Optional[dict]:
        """Get cached bio if exists."""
        return await self.cache.get(tenant_id, customer_ref)

    async def generate_bio(self, tenant_id: str, customer_ref: str, user_id: str) -> dict:
        """
        Generate a new bio for a customer.

        1. Check if staff-edited bio exists (block regeneration)
        2. Aggregate customer data from ClickHouse
        3. Get retailer settings (tone, etc.)
        4. Call Claude to generate bio
        5. Cache result
        """
        # Check for staff-edited bio
        existing = await self.cache.get(tenant_id, customer_ref)
        if existing and existing.get("is_staff_edited"):
            raise ValueError("Cannot regenerate staff-edited bio. Use reset_to_ai first.")

        # Aggregate data
        customer_data = await self.aggregator.aggregate(tenant_id, customer_ref)

        if not customer_data.get("customer"):
            raise ValueError(f"Customer not found: {customer_ref}")

        # Get retailer settings
        retailer_settings = await self.settings.get_bio_settings(tenant_id)

        # Generate bio
        result = self.generator.generate(
            customer_data=customer_data,
            tone=retailer_settings.get("tone", "professional"),
            include_conversation_starters=retailer_settings.get("include_conversation_starters", True),
        )

        # Create snapshot hash for staleness detection
        snapshot_hash = self._create_snapshot_hash(customer_data)

        # Cache result
        bio_record = {
            "tenant_id": tenant_id,
            "customer_ref": customer_ref,
            "bio": result["bio"],
            "conversation_starters": result["conversation_starters"],
            "generated_at": datetime.utcnow().isoformat(),
            "generated_by": user_id,
            "snapshot_hash": snapshot_hash,
            "is_staff_edited": False,
            "is_stale": False,
        }

        await self.cache.save(bio_record)

        return bio_record

    async def update_bio(self, tenant_id: str, customer_ref: str, bio_text: str, user_id: str) -> dict:
        """Staff edits and saves bio. Disables AI regeneration."""
        bio_record = {
            "tenant_id": tenant_id,
            "customer_ref": customer_ref,
            "bio": bio_text,
            "conversation_starters": [],  # Staff can add manually if needed
            "edited_at": datetime.utcnow().isoformat(),
            "edited_by": user_id,
            "is_staff_edited": True,
            "is_stale": False,
        }

        await self.cache.save(bio_record)
        return bio_record

    async def reset_to_ai(self, tenant_id: str, customer_ref: str, user_id: str) -> dict:
        """Clear staff edits and regenerate AI bio."""
        await self.cache.delete(tenant_id, customer_ref)
        return await self.generate_bio(tenant_id, customer_ref, user_id)

    def _create_snapshot_hash(self, data: dict) -> str:
        """Create hash of key data points for staleness detection."""
        key_data = {
            "orders": data.get("purchase_summary", {}).get("total_orders"),
            "last_purchase": data.get("purchase_summary", {}).get("last_purchase_date"),
            "wishlist_count": data.get("wishlist", {}).get("count"),
            "notes_count": len(data.get("staff_notes", [])),
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
```

### 4. API Endpoints (FastAPI)

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/customers/{customer_ref}/bio")

class GenerateBioRequest(BaseModel):
    regenerate: bool = False

class UpdateBioRequest(BaseModel):
    bio: str

@router.get("")
async def get_bio(
    customer_ref: str,
    tenant_id: str = Depends(get_tenant_id),
    bio_service: BioService = Depends(get_bio_service),
):
    """Get current bio for customer."""
    bio = await bio_service.get_bio(tenant_id, customer_ref)
    if not bio:
        return {"exists": False, "bio": None}
    return {"exists": True, **bio}

@router.post("/generate")
async def generate_bio(
    customer_ref: str,
    request: GenerateBioRequest,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_current_user_id),
    bio_service: BioService = Depends(get_bio_service),
):
    """Generate AI bio for customer."""
    try:
        bio = await bio_service.generate_bio(tenant_id, customer_ref, user_id)
        return bio
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("")
async def update_bio(
    customer_ref: str,
    request: UpdateBioRequest,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_current_user_id),
    bio_service: BioService = Depends(get_bio_service),
):
    """Staff updates bio (disables AI regeneration)."""
    bio = await bio_service.update_bio(tenant_id, customer_ref, request.bio, user_id)
    return bio

@router.post("/reset")
async def reset_to_ai(
    customer_ref: str,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_current_user_id),
    bio_service: BioService = Depends(get_bio_service),
):
    """Clear staff edits and regenerate AI bio."""
    bio = await bio_service.reset_to_ai(tenant_id, customer_ref, user_id)
    return bio
```

### 5. Dependencies

```
# requirements.txt
anthropic>=0.18.0
clickhouse-connect>=0.7.0
fastapi>=0.109.0
pydantic>=2.0.0
boto3>=1.34.0  # For DynamoDB cache
```

### 6. Environment Variables

```bash
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# ClickHouse
CLICKHOUSE_HOST=your-clickhouse-host
CLICKHOUSE_PORT=8443
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=...
CLICKHOUSE_DATABASE=default

# DynamoDB (for bio cache)
AWS_REGION=ap-southeast-2
BIO_CACHE_TABLE=twc-customer-bios
```

---

## Retailer Configuration

Per-retailer settings for bio generation:

```json
{
  "tenant_id": "camillaandmarc-au",
  "bio_settings": {
    "tone": "professional",           // "professional" | "friendly" | "luxury"
    "include_spend_data": true,       // Show AOV, lifetime spend
    "include_conversation_starters": true,
    "max_notes_to_include": 10,       // Most recent N notes
    "language": "en-AU"
  }
}
```

### Tone Examples

**Professional:**
> "Ms. Chen has been a valued VIP client since 2021, demonstrating a consistent preference for classic silhouettes in neutral palettes. Her purchasing history reflects an appreciation for quality fabrications, particularly silk and cashmere from Zimmermann and Scanlan Theodore."

**Friendly:**
> "Sarah's been with us since 2021 and she's a dream to style! She loves classic, minimalist looks - think navy, black, and cream. Zimmermann and Scanlan Theodore are her go-tos, especially anything in silk or cashmere."

**Luxury:**
> "Sarah Chen, a distinguished VIP member since 2021, embodies refined elegance in her sartorial choices. Her discerning eye gravitates toward timeless silhouettes, favoring the understated sophistication of navy and cream, rendered in the finest silk and cashmere."

---

## Proposed Jira Stories

### Epic: AI-Generated Customer Bios

Enable AI-powered bio generation to help staff quickly understand customer preferences and history.

---

#### BIO-001: Create retailer bio settings configuration
**Type:** Task
**Priority:** High
**Story Points:** 2

**Description:**
Add bio generation settings to retailer configuration in DynamoDB.

**Acceptance Criteria:**
- [ ] Add `bio_settings` to retailer config schema
- [ ] Support fields: `tone`, `include_spend_data`, `include_conversation_starters`, `max_notes_to_include`, `language`
- [ ] Default values for retailers without explicit config
- [ ] Admin API to update settings

---

#### BIO-002: Build customer profile aggregation query
**Type:** Story
**Priority:** High
**Story Points:** 2

**Description:**
As the bio service, I need to fetch basic customer profile data (name, VIP status, loyalty tier, tenure).

**Acceptance Criteria:**
- [ ] Query `TWCCUSTOMER` table by tenantId + customerRef
- [ ] Return: name, vipStatus, loyaltyTier, memberSince, preferredStore
- [ ] Handle customer not found (return empty dict)
- [ ] Unit tests with mock data

---

#### BIO-003: Build preferences aggregation query
**Type:** Story
**Priority:** High
**Story Points:** 3

**Description:**
As the bio service, I need to parse customer preferences JSON into structured likes/dislikes/sizes.

**Acceptance Criteria:**
- [ ] Query `TWCPREFERENCES` table (primary preference first)
- [ ] Parse JSON: categories, colours, brands, fabrics
- [ ] Separate likes vs dislikes (based on `dislike` flag)
- [ ] Extract sizes by category (dresses, tops, bottoms, footwear)
- [ ] Handle malformed JSON gracefully
- [ ] Unit tests for JSON parsing edge cases

---

#### BIO-004: Build purchase history aggregation queries
**Type:** Story
**Priority:** High
**Story Points:** 3

**Description:**
As the bio service, I need purchase summary and top categories/brands from order history.

**Acceptance Criteria:**
- [ ] Query `TWCALLORDERS` for: total orders, lifetime spend, AOV, first/last purchase
- [ ] Query `ORDERLINE` + `TWCVARIANT` for top categories, brands, colors
- [ ] Query recent purchases (last 6 months)
- [ ] Handle customers with no orders
- [ ] Unit tests

---

#### BIO-005: Build wishlist aggregation query
**Type:** Story
**Priority:** High
**Story Points:** 2

**Description:**
As the bio service, I need to fetch active wishlist items.

**Acceptance Criteria:**
- [ ] Query `TWCWISHLIST` + `WISHLISTITEM` joined
- [ ] Filter: deleted='0', purchased='0'
- [ ] Return: product name, price, brand, customerInterest
- [ ] Limit to 10 most recent items
- [ ] Unit tests

---

#### BIO-006: Build clickstream aggregation query
**Type:** Story
**Priority:** Medium
**Story Points:** 2

**Description:**
As the bio service, I need recent browsing behavior (last 30 days).

**Acceptance Criteria:**
- [ ] Query `TWCCLICKSTREAM` grouped by productType, brand
- [ ] Return top 5 categories and brands by view count
- [ ] Filter to last 30 days
- [ ] Handle customers with no clickstream data
- [ ] Unit tests

---

#### BIO-007: Build customer messages aggregation query
**Type:** Story
**Priority:** Medium
**Story Points:** 2

**Description:**
As the bio service, I need customer-sent messages for context.

**Acceptance Criteria:**
- [ ] Query `TWCCUSTOMER_MESSAGE` where isReply='1'
- [ ] Return: message text, date, store
- [ ] Limit to 5 most recent
- [ ] Truncate long messages (>500 chars)
- [ ] Unit tests

---

#### BIO-008: Build staff notes aggregation query
**Type:** Story
**Priority:** Medium
**Story Points:** 2

**Description:**
As the bio service, I need staff notes about the customer.

**Acceptance Criteria:**
- [ ] Query `TWCNOTES` table (when available)
- [ ] Return: note text, date, author
- [ ] Limit to 20 most recent
- [ ] Placeholder implementation until table exists
- [ ] Unit tests

---

#### BIO-009: Build parallel aggregation orchestrator
**Type:** Story
**Priority:** High
**Story Points:** 3

**Description:**
As the bio service, I need to run all aggregation queries in parallel for performance.

**Acceptance Criteria:**
- [ ] Use asyncio + ThreadPoolExecutor for parallel execution
- [ ] All 8 queries run concurrently
- [ ] Total aggregation time <500ms (target)
- [ ] Combine results into single structured dict
- [ ] Error handling: partial failure returns partial data
- [ ] Logging for query timing
- [ ] Integration tests with ClickHouse

---

#### BIO-010: Design Claude prompt template
**Type:** Story
**Priority:** High
**Story Points:** 3

**Description:**
As a product owner, I want a well-crafted prompt that generates consistent, high-quality bios.

**Acceptance Criteria:**
- [ ] Prompt template with JSON data injection point
- [ ] Clear output format instructions (sections, lengths)
- [ ] Tone instructions for: professional, friendly, luxury
- [ ] Guardrails: "only use provided data", "do not invent details"
- [ ] Conversation starters extraction instructions
- [ ] Document prompt in design doc
- [ ] Test with sample data for each tone

---

#### BIO-011: Implement Claude API client
**Type:** Story
**Priority:** High
**Story Points:** 3

**Description:**
As the bio service, I need to call Claude API to generate bios.

**Acceptance Criteria:**
- [ ] Use `anthropic` Python SDK
- [ ] Configure model: claude-sonnet-4-20250514
- [ ] Set max_tokens: 1024
- [ ] Inject customer data JSON into prompt
- [ ] Parse response to extract conversation starters
- [ ] Handle API errors (rate limits, timeouts)
- [ ] Configurable timeout (default 30s)
- [ ] Unit tests with mocked API

---

#### BIO-012: Implement bio response parser
**Type:** Story
**Priority:** Medium
**Story Points:** 2

**Description:**
As the bio service, I need to parse Claude's response into structured output.

**Acceptance Criteria:**
- [ ] Extract full bio text
- [ ] Extract conversation starters as list
- [ ] Handle missing sections gracefully
- [ ] Validate response format
- [ ] Unit tests with various response formats

---

#### BIO-013: Implement bio cache repository (DynamoDB)
**Type:** Story
**Priority:** High
**Story Points:** 3

**Description:**
As the bio service, I need to cache generated bios in DynamoDB.

**Acceptance Criteria:**
- [ ] DynamoDB table: `twc-customer-bios`
- [ ] Schema: tenantId (PK), customerRef (SK), bio, generated_at, snapshot_hash, is_staff_edited
- [ ] CRUD operations: get, save, delete
- [ ] TTL support for auto-expiry (optional)
- [ ] Unit tests with mocked DynamoDB

---

#### BIO-014: Implement staleness detection
**Type:** Story
**Priority:** Medium
**Story Points:** 3

**Description:**
As the bio service, I need to detect when a bio is stale (underlying data changed).

**Acceptance Criteria:**
- [ ] Create snapshot hash from key data points (order count, last purchase, wishlist count)
- [ ] Store hash with cached bio
- [ ] Compare current data hash vs stored hash
- [ ] Return `is_stale: true` and `stale_reason` when different
- [ ] Skip staleness check for staff-edited bios
- [ ] Unit tests

---

#### BIO-015: Implement bio service orchestrator
**Type:** Story
**Priority:** High
**Story Points:** 5

**Description:**
As the API layer, I need a service that orchestrates aggregation, generation, and caching.

**Acceptance Criteria:**
- [ ] `get_bio()`: Return cached bio or None
- [ ] `generate_bio()`: Aggregate → Generate → Cache
- [ ] `update_bio()`: Staff edit, set is_staff_edited=True
- [ ] `reset_to_ai()`: Clear staff edit, regenerate
- [ ] Block regeneration for staff-edited bios (raise error)
- [ ] Get retailer settings for tone configuration
- [ ] Integration tests

---

#### BIO-016: Implement bio API endpoints
**Type:** Story
**Priority:** High
**Story Points:** 3

**Description:**
As a frontend developer, I need REST API endpoints for bio operations.

**Acceptance Criteria:**
- [ ] `GET /api/v1/customers/{customer_ref}/bio` - Get current bio
- [ ] `POST /api/v1/customers/{customer_ref}/bio/generate` - Generate AI bio
- [ ] `PUT /api/v1/customers/{customer_ref}/bio` - Staff edit bio
- [ ] `POST /api/v1/customers/{customer_ref}/bio/reset` - Reset to AI
- [ ] Proper error responses (400, 404, 500)
- [ ] Request validation with Pydantic
- [ ] OpenAPI documentation
- [ ] Integration tests

---

#### BIO-017: Build bio display component (frontend)
**Type:** Story
**Priority:** High
**Story Points:** 5

**Description:**
As a staff member viewing a customer profile, I want to see their bio with clear indication of its source and freshness.

**Acceptance Criteria:**
- [ ] Display bio in customer profile page
- [ ] Show "Generate AI Bio" button if no bio exists
- [ ] Show "AI Generated" badge with timestamp for AI bios
- [ ] Show "Edited by [name] on [date]" badge for staff-edited bios
- [ ] Show "New activity - Refresh?" banner for stale AI bios
- [ ] Loading state with "Generating bio... This takes a few seconds"
- [ ] Expandable/collapsible for long bios

---

#### BIO-018: Build bio edit modal (frontend)
**Type:** Story
**Priority:** Medium
**Story Points:** 3

**Description:**
As a staff member, I want to edit the bio in a modal with a rich text editor.

**Acceptance Criteria:**
- [ ] Edit button opens modal with current bio text
- [ ] Markdown or rich text editor
- [ ] Save/Cancel buttons
- [ ] Confirmation if overwriting AI-generated bio ("This will disable AI updates")
- [ ] Success/error feedback

---

#### BIO-019: Add conversation starters component
**Type:** Story
**Priority:** Medium
**Story Points:** 2

**Description:**
As a staff member, I want to see actionable conversation starters based on the customer's recent activity.

**Acceptance Criteria:**
- [ ] Display conversation starters below bio
- [ ] 2-4 suggestions based on: wishlist items, recent purchases, browse activity
- [ ] Clickable to navigate to relevant product/order
- [ ] Update when bio is regenerated

---

#### BIO-020: Implement bio generation audit logging
**Type:** Story
**Priority:** Low
**Story Points:** 2

**Description:**
As an admin, I want to track bio generation and edits for compliance and debugging.

**Acceptance Criteria:**
- [ ] Log: customer_id (hashed), tenant_id, action (generate/edit/reset), timestamp, user_id
- [ ] Don't log bio content or PII
- [ ] Store in audit log table
- [ ] Retention policy (90 days)

---

#### BIO-021: Add bio settings to retailer admin UI
**Type:** Story
**Priority:** Low
**Story Points:** 3

**Description:**
As a retailer admin, I want to configure bio generation settings for my brand.

**Acceptance Criteria:**
- [ ] Settings page in retailer admin
- [ ] Tone selector (professional/friendly/luxury) with preview
- [ ] Toggle: include spend data
- [ ] Toggle: include conversation starters
- [ ] Save confirmation

---

### Story Summary

| Phase | Stories | Points |
|-------|---------|--------|
| Configuration | BIO-001 | 2 |
| Data Aggregation | BIO-002 to BIO-009 | 19 |
| Claude Integration | BIO-010 to BIO-012 | 8 |
| Caching & Staleness | BIO-013, BIO-014 | 6 |
| Orchestration & API | BIO-015, BIO-016 | 8 |
| Frontend | BIO-017 to BIO-019 | 10 |
| Admin & Audit | BIO-020, BIO-021 | 5 |
| **Total** | **21 stories** | **~58 points** |

### Suggested Sprint Breakdown

**Sprint 1: Foundation & Aggregation**
- BIO-001: Retailer settings config
- BIO-002: Customer profile aggregation query
- BIO-003: Preferences aggregation query
- BIO-004: Purchase history aggregation queries
- BIO-005: Wishlist aggregation query
- BIO-006: Clickstream aggregation query

**Sprint 2: Aggregation & Claude**
- BIO-007: Customer messages aggregation query
- BIO-008: Staff notes aggregation query
- BIO-009: Parallel aggregation orchestrator
- BIO-010: Claude prompt template
- BIO-011: Claude API client
- BIO-012: Bio response parser

**Sprint 3: Caching, Orchestration & API**
- BIO-013: Bio cache repository (DynamoDB)
- BIO-014: Staleness detection
- BIO-015: Bio service orchestrator
- BIO-016: Bio API endpoints

**Sprint 4: Frontend & Polish**
- BIO-017: Bio display component
- BIO-018: Bio edit modal
- BIO-019: Conversation starters component
- BIO-020: Audit logging
- BIO-021: Bio settings admin UI
