# How the data is grouped (the modeled layer, in plain English)

When the messy legacy tables get modeled, everything gets reorganized into two simple kinds of
tables: **things you describe by** (dimensions) and **things you measure** (facts). All the facts
point back to the same shared dimensions, so numbers from five different systems finally line up.
That shape is called a **star**.

Here's the plain-English grouping — the 9 `c_*` tables the notebook builds:

## Dimensions — the "who / what / where / when" (shared lookup lists)

- **Product** (`c_dim_product`) — every item, one row per SKU. Lakeside's `LSP-` items, service
  `ITM-` parts, and marketplace listings all get folded into this one list via the cross-reference.
- **Location** (`c_dim_location`) — all the places: distribution centers, Lakeside stores, and the
  marketplace, in one list.
- **Date** (`c_dim_date`) — one row per day, with month/quarter/year and a flag for "after the
  acquisition."
- **Channel** (`c_dim_channel`) — Online, Retail, Wholesale, Marketplace, Lakeside.

## Facts — the "how much happened" (the numbers, by day / product / location)

- **Sales** (`c_fact_sales_unified`) — every sale from all three selling systems (ERP + marketplace
  + Lakeside) stacked into one table, with gross *and* net amounts.
- **Inventory** (`c_fact_inventory`) — stock levels and stockouts, ERP daily + Lakeside weekly,
  marked by grain so they're not mixed up.
- **Service** (`c_fact_service`) — work orders.
- **Service parts** (`c_fact_service_parts`) — parts used.
- **Helpdesk** (`c_fact_helpdesk`) — support tickets, with complaint / open flags.

## The trick that makes grouping possible

Every record gets translated to **one common product code** and **one common date format** *before*
it's grouped. So a marketplace order, a Lakeside sale, and an ERP sale for the *same physical
product* now share the same SKU — and can finally be added together.

So instead of 17 tables in 5 different "languages," you get a small, consistent set where **facts
connect to dimensions through shared keys**. That's the grouping, and it's what lets one question
pull a correct answer from all sources at once.
