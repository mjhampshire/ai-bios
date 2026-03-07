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

#### BIO-002: Build customer data aggregation service
**Type:** Story
**Priority:** High
**Story Points:** 5

**Description:**
As the bio generation service, I need to aggregate customer data from multiple sources into a structured format for the LLM prompt.

**Acceptance Criteria:**
- [ ] Query ClickHouse for: orders, wishlist, clickstream, preferences
- [ ] Query DynamoDB for: staff notes, loyalty data
- [ ] Aggregate into JSON schema (see design doc)
- [ ] Parallel queries for performance (<500ms total)
- [ ] Handle missing data gracefully (sparse profiles)

---

#### BIO-003: Design and implement Claude prompt template
**Type:** Story
**Priority:** High
**Story Points:** 3

**Description:**
As a product owner, I want the AI to generate consistent, high-quality bios that match the retailer's tone preference.

**Acceptance Criteria:**
- [ ] Prompt template with structured data injection
- [ ] Support for 3 tones: professional, friendly, luxury
- [ ] Output follows bio structure (style profile, shopping patterns, key notes, recent activity, conversation starters)
- [ ] Guardrails to prevent hallucination (only use provided data)
- [ ] Max token limits to control cost/latency

---

#### BIO-004: Implement bio generation API endpoint
**Type:** Story
**Priority:** High
**Story Points:** 5

**Description:**
As a frontend developer, I need an API to generate AI bios for customers.

**Acceptance Criteria:**
- [ ] `POST /api/v1/customers/{customerId}/bio/generate` endpoint
- [ ] Calls data aggregation service
- [ ] Calls Claude API with prompt
- [ ] Returns generated bio with metadata (generated_at, confidence, conversation_starters)
- [ ] Error handling for API failures
- [ ] Request timeout handling (10s max)

---

#### BIO-005: Implement bio caching layer
**Type:** Story
**Priority:** High
**Story Points:** 3

**Description:**
As a system, I want to cache generated bios to avoid repeated API calls and reduce latency.

**Acceptance Criteria:**
- [ ] Store generated bios in DynamoDB
- [ ] Cache schema: bio text, generated_at, data_snapshot, is_staff_edited
- [ ] `GET /api/v1/customers/{customerId}/bio` returns cached bio
- [ ] Track staleness (data changed since generation)
- [ ] Return `is_stale: true` if new orders/wishlist/notes since generation

---

#### BIO-006: Implement bio staleness detection
**Type:** Story
**Priority:** Medium
**Story Points:** 3

**Description:**
As a staff member, I want to know when a bio is outdated so I can regenerate it.

**Acceptance Criteria:**
- [ ] Track last bio generation timestamp
- [ ] Compare against latest: order date, wishlist update, note added, preference change
- [ ] Return `stale_reason` in API response (e.g., "2 new orders since last update")
- [ ] Don't mark staff-edited bios as stale (AI disabled)

---

#### BIO-007: Implement staff bio editing
**Type:** Story
**Priority:** High
**Story Points:** 3

**Description:**
As a staff member, I want to edit and save the AI-generated bio to add my personal knowledge.

**Acceptance Criteria:**
- [ ] `PUT /api/v1/customers/{customerId}/bio` endpoint
- [ ] Save edited bio text
- [ ] Set `is_staff_edited: true`, `edited_by`, `edited_at`
- [ ] Once staff-edited, `generate` endpoint returns 400 with message
- [ ] Option to "Reset to AI" which clears staff edits (requires confirmation)

---

#### BIO-008: Build bio display component (frontend)
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

#### BIO-009: Build bio edit modal (frontend)
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

#### BIO-010: Add conversation starters component
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

#### BIO-011: Implement bio generation audit logging
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

#### BIO-012: Add bio settings to retailer admin UI
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
| Backend Core | BIO-001 to BIO-007 | 24 |
| Frontend | BIO-008 to BIO-010 | 10 |
| Admin & Audit | BIO-011, BIO-012 | 5 |
| **Total** | **12 stories** | **~39 points** |

### Suggested Sprint Breakdown

**Sprint 1: Foundation**
- BIO-001: Retailer settings config
- BIO-002: Data aggregation service
- BIO-003: Claude prompt template

**Sprint 2: Core API**
- BIO-004: Generation API endpoint
- BIO-005: Caching layer
- BIO-006: Staleness detection

**Sprint 3: Frontend**
- BIO-007: Staff bio editing (API)
- BIO-008: Bio display component
- BIO-009: Bio edit modal

**Sprint 4: Polish**
- BIO-010: Conversation starters
- BIO-011: Audit logging
- BIO-012: Admin UI
