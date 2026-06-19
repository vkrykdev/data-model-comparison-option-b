# The story behind the demo

Picture a mid-sized industrial-supplies distributor — the kind of business that keeps factories,
contractors, and maintenance crews stocked with the unglamorous-but-essential stuff: rocker
switches, solenoid valves, hydraulic hoses, terminal blocks, stretch wrap. For years it ran on a
clean, well-behaved ERP. Sales, inventory, products, suppliers — all in one tidy system, all
speaking the same language of SKUs and snake_case columns. Life was orderly.

Then the business did what growing businesses do: it spread out.

First, it built a **service department** — technicians opening work orders and consuming spare
parts in the field. Useful, but it lived in its own little system that referred to everything by
`ITM-` codes instead of SKUs. Then came a **helpdesk SaaS** for customer support, where agents
typed product names by hand into tickets — so "Titan Rocker Switch" might show up spelled three
different ways, or left blank entirely. Then the company started selling on the **MegaMart
marketplace**, which had its own listing IDs, its own order feed, and — crucially — took a ~14%
cut, so the money that landed in the bank never matched the gross sales number on the screen.

And then, the big one: on **February 1st, 2026**, it acquired **Lakeside Supply Co.**, a scrappy
regional outfit running on legacy Access and Excel. Lakeside counted stock once a week instead of
daily, wrote its dates the British way (DD/MM/YYYY) as plain text, used its own `LSP-` product
codes, and stocked a bunch of store-brand items the parent company had never carried.

So now leadership has five different systems all describing pieces of one business — and **no
single source of truth.** Someone in finance keeps a `sku_xref_master` spreadsheet that maps the
codes across systems, but it's about 95% complete: a few products were never mapped, one's
retired, a couple have conflicting entries.

Here's the tension that drives everything: **the executives want combined answers now** — total
company sales including Lakeside and the marketplace, which products generate the most complaints,
how the acquired stores are performing — but the integration project that would actually unify the
data is months away. They can't wait.

That's the whole point of the demo. The *same* messy, multi-source reality gets handed to AI
agents, and we watch what happens. Pile heavy instructions onto an agent pointed straight at the
legacy tables and it gets further — but it still stumbles: it slips between gross and net, struggles
to join free-text product names, misreads "03/02/2026" as March 2nd instead of February 3rd, and
approximates where sources won't cleanly connect. A properly modeled, AI-described version of that
*same data* answers cleanly and honestly. The company's mess isn't a bug in the story — **it's the
realistic starting condition every real company is in**, and the demo proves that modeling — not
instructions alone — is what turns that mess into trustworthy answers.

## The five data sources

What each system is, what it brings, and the quirk that makes it interesting.

### 1. ERP / WMS — the clean backbone
The company's core system of record, and the only one that's genuinely tidy. Consistent SKUs,
`snake_case` columns, daily data.
- **`products`** — the SKU master: name, category/subcategory, brand, ABC class, costs, list price, supplier.
- **`suppliers`** — vendor details, lead times, reliability scores.
- **`locations`** — distribution centers and regions.
- **`sales_order_lines`** — the main sales fact (Online / Retail / Wholesale channels), quantities and prices.
- **`inventory_daily`** — daily stock snapshots per SKU/location, including the `is_stockout` flag.
- **Quirk:** none, really — this is the well-behaved baseline everything else is measured against. The
  planted twist is that the stockout rate was nudged up to ~2% and concentrated in a couple of A/B-class products.

### 2. Service department — the `ITM-` code island
A separate maintenance/repair system. Technicians log work and the parts they consume.
- **`ServiceWorkOrders`** — jobs opened/closed, labor hours, status.
- **`ServicePartsUsage`** — parts consumed per work order.
- **Quirk:** it doesn't know about SKUs at all — every part is an `ITM-` code. To connect a service part
  to a product you must go through the `sku_xref_master` bridge (`itm_code → sku`). Miss that, and
  service activity floats free of the catalog.

### 3. Helpdesk SaaS — the free-text problem
A customer-support tool, `camelCase` columns, where humans type things in.
- **`hdTickets`** — support tickets: created/closed timestamps, priority, status, and a `productRef`.
- **`hdCategories`** — the category lookup (category 1 = "product complaint").
- **Quirk:** `productRef` is **free text**, not a code — roughly 8% are misspelled and 4% are blank.
  There's no clean key to join on; you match the typed name against `products.product_name` and accept
  that ~12% simply won't resolve. This is where naïve agents hallucinate a join.

### 4. MegaMart marketplace — gross vs. net
An external online marketplace the company sells through, with its own identifiers and economics.
- **`mm_listings`** — the seller's listings (own listing IDs, ~10 stale ones, 2 SKUs dual-listed).
- **`mm_orders`** — orders placed, with a **gross** amount.
- **`mm_settlements`** — what MegaMart actually paid out after commission and fulfillment fees (~14% taken).
- **Quirk:** the headline `grossAmount` overstates real revenue by ~16%. The number that matters is
  `payoutAmount` (net), which only appears once you join orders to settlements. Listings map to SKUs
  only via `mm_listing_id` in the xref — unmapped listings are revenue that can't be tied to a product.

### 5. Lakeside Supply Co. — the legacy acquisition
The regional company acquired on **Feb 1, 2026**, still on legacy Access/Excel. `UPPER_SNAKE` columns,
its own everything.
- **`LS_PRODUCT_LIST`** — Lakeside's catalog, keyed by `LSP-` codes (includes store-brand-only items).
- **`LS_SALES_EXPORT`** — its sales, joined to products only by free-text `PROD_DESC`.
- **`LS_STOCK_COUNT`** — **weekly** stock counts (not daily like ERP).
- **`LS_STORES`** — its retail store list.
- **Quirks, several:** dates are **text in DD/MM/YYYY** (so `03/02/2026` is 3 February, not March 2 —
  the classic misparse trap); inventory is weekly, so it can't be summed alongside ERP's daily grain
  (compare ratios instead); and its `LSP-` codes need the xref (`lsp_code → sku`) to align.

### The glue (not a source, but essential)
**`sku_xref_master`** — a hand-maintained crosswalk mapping each canonical SKU to its `itm_code`,
`lsp_code`, and `mm_listing_id`. It's ~95% complete on purpose: 3 unmapped gaps, 1 retired SKU, 2
conflicting rows. It's the only safe bridge between the five islands — and its imperfections are
exactly what a governed approach surfaces honestly instead of guessing around.
