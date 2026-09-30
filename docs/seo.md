# OddHobb — Google AI + Pinterest Playbook

> Build for agents first. Game both platforms from day one.
> Source: owner brief, 2026-09-30. Implementation lives in this repo —
> see `seo-impl.md` for what is wired vs still to build.

---

## GOOGLE AI SEARCH (AI Overviews, AI Mode, Gemini)

### The 8 Product Feed Attributes

Google explicitly connects these 8 attributes to AI-driven results. Most merchants are missing them.

| # | Attribute | What It Does | OddHobb Example |
|---|-----------|--------------|-----------------|
| 1 | **Product Highlight** | Key selling benefits (not specs) | "Handmade, 3D printed, personalized, magnetic" |
| 2 | **Product Detail** | Structured specs (Section:Name:Value) | "Material: PLA+ \| Size: 80mm \| Color: Black" |
| 3 | **Variant Option** | Non-standard variant dimensions | "Theme: Dragon Egg, Owl, Moon" |
| 4 | **Item Group Title** | Shared title for variant family | "First-Player Token Collection" |
| 5 | **Related Products** | Accessories, cross-sells | "Often bought with: token tray, dice tower" |
| 6 | **Question & Answer** | FAQ pairs for conversational AI | Q: "What size are the tiles?" A: "Fits standard 19mm tiles" |
| 7 | **Document Link** | PDFs AI can crawl | Companion guides, build instructions |
| 8 | **Popularity Rank** | Tell Google what sells | Sales data |

### Q&A Pairs (The Goldmine)

**Up to 30 Q&A pairs per product.** Google uses these to answer shopper questions in AI Mode.

Write Q&A pairs that match how people actually ask AI:

| People Ask AI | Your Q&A Pair |
|---------------|---------------|
| "What do I need for cross-stitch?" | "What tools do I need for cross-stitch?" → needle minder, floss drops |
| "Best gift for a mahjong player" | "What gifts do mahjong players like?" → line reader, wind markers |
| "How to build a cyberdeck" | "What is a cyberdeck?" → DIY computer, Raspberry Pi |
| "What is a protection spell kit?" | "What's in a protection spell kit?" → candle, oil, herbs, sigil card |

**The goal:** When someone asks Google AI "what do I need for cross-stitch?", your products appear in the answer.

### Document Links (Underused Opportunity)

**Up to 5 PDF links per product.** Google crawls these and uses them to answer questions in AI Mode.

For each product:
1. Companion guide PDF (historical context, symbolism)
2. Build/assembly guide PDF
3. Care and maintenance PDF
4. FAQ PDF
5. Supplier transparency PDF

### Product Feed Structure

```csv
id,title,description,product_highlight,product_detail,variant_option,item_group_title,related_products,question_and_answer,document_link,price,availability
```

### Google Merchant Center Setup

| Step | Action |
|------|--------|
| 1 | Create Merchant Center account (free) |
| 2 | Verify website |
| 3 | Build product feed with 8 AI attributes |
| 4 | Submit feed via API or CSV |
| 5 | Enable AI performance insights |
| 6 | Monitor "Top terms" and "Popular attributes" |

---

## PINTEREST (Visual Search Engine)

### The 4 Ranking Signals

| Signal | Weight | How to Optimize |
|--------|--------|-----------------|
| **Domain quality** | High | Claim website, consistent branding |
| **Pin quality** | High | Vertical 2:3, clear focal point, high-res |
| **Topic relevance** | High | Keywords in title, description, board name |
| **Engagement** | Medium | Saves, clicks, close-ups |

### Pinterest SEO Formula

**Pin Title (100 chars max):** primary keyword first, benefit second.
**Pin Description (500 chars max):** 2–3 related keywords in natural language.
**Board Name:** keyword-rich.
**Board Description:** 2–3 sentences with keywords.

### Pin Design Rules

| Element | Spec |
|---------|------|
| Aspect ratio | 2:3 (vertical) |
| Resolution | 1000×1500 minimum |
| Text on pin | Keyword-rich, readable |
| Focal point | Product clearly visible |
| Background | Clean, not cluttered |
| Variations | 3–5 designs per product |

### The Pinterest Game

1. **Consistency beats volume.** Pin daily.
2. **Freshness boost.** Pins under 7 days old get ranking boost.
3. **Topic alignment.** Pin title/description must match the landing page.
4. **Keyword research.** Pinterest Interest Taxonomy (20M+ keywords).
5. **Multiple designs per product.** One product → 5 designs → 5 keyword angles.

### Pinterest Product Pins

Catalog feed attributes: title, description, price, availability, image_link, additional_image_link (3–5), product_type, brand=OddHobb.

### Pinterest Content Calendar

| Day | Pin Type |
|-----|----------|
| Monday | Product pin |
| Tuesday | Idea pin ("5 Gifts for …") |
| Wednesday | Product pin |
| Thursday | Lifestyle pin |
| Friday | Product pin |
| Saturday | Collection pin |
| Sunday | How-to pin |

**7 pins per day minimum.**

---

## The Agent Discovery Play

### Google AI Discovery
1. Structured product feed with 8 AI attributes
2. 30 Q&A pairs per product
3. 5 companion guide PDFs per product
4. Submit to Google Merchant Center
5. Enable AI performance insights
6. Monitor "Top terms" and optimize

### Pinterest Discovery
1. Claim website + install Pinterest tag
2. Build product catalog feed
3. 5 pin designs per product
4. Pin daily with keyword-rich titles/descriptions
5. Pinterest Trends for keyword research
6. Monitor pin performance, double down on winners

### The Combined Flywheel

Both channels consume the same structured data. Q&A + companion guides are what AI agents read. Pinterest rewards consistent keyword-rich pinning.

---

## Implementation Priority (owner's 3-week plan)

| Week | Focus |
|------|-------|
| 1 | Merchant catalog + feed with 8 AI attributes + Q&A pairs |
| 2 | Pinterest catalog + document links (PDF guides) |
| 3 | Knowledge graphs (JSON) + MCP agent discovery |

**Key insight:** Write Q&A pairs and companion guides that AI agents can read. That's how you get recommended in Google AI Overviews.
