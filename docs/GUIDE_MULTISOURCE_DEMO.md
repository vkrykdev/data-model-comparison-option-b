# Reference — Multi-Source "Raw vs Well-Modeled" demo

This is the **reference** for the build. The executable, confirm-after-each steps are in
**`PLAN.md`** — follow that to build. Use this doc when you need detail: the source tables, the
conformed schema, the relationships and measures (for the Phase 5b portal fallback), and the
rationale behind the AI-layer text.

Names: lakehouse **lh_supply_demo** · models **MultiSource_Raw** / **MultiSource_Modeled** ·
notebook **build_modeled_layer** · agents **SupplyAgent_Raw** / **SupplyAgent_Raw_Plus** /
**SupplyAgent_Modeled**. Location:
workspace *Microsoft Fabric Demo Stand* → folder *data-model-comparison* → subfolder *Option B*.

---

## 1. The 17 source tables and their quirks

| Source | Tables | Convention | Deliberate quirks (= demo traps) |
|---|---|---|---|
| **A. ERP/WMS** | `products`, `suppliers`, `locations`, `sales_order_lines` (128.5K), `inventory_daily` (182.5K) | snake_case | Clean baseline. Stockout rate raised **0.02% → 2.06%**, A/B-concentrated |
| **B. Service** | `ServiceWorkOrders` (6K), `ServicePartsUsage` (9K) | PascalCase | Products as `ITM-####`; `TechnicianID` deliberately dangles |
| **C. Helpdesk** | `hdTickets` (12K), `hdCategories` | camelCase | `productRef` free-text, ~8% misspelled, ~4% blank; "complaint" only via `categoryId=1` |
| **D. MegaMart** | `mm_orders` (25K), `mm_listings` (102), `mm_settlements` (25K) | mm_ prefix | Own `listingId`; ~10 stale listings; 2 dual-listing SKUs; **gross vs net** (14% fees) |
| **E. Lakeside** | `LS_SALES_EXPORT` (40K), `LS_PRODUCT_LIST` (60), `LS_STORES` (4), `LS_STOCK_COUNT` (12.7K) | UPPERCASE | **TEXT DD/MM/YYYY dates**; `LSP-####` codes; product as text name; **weekly** counts; 10 store-brand-only items |
| **F. Glue** | `sku_xref_master` (103) | analyst Excel | ~95% complete: 3 "TODO confirm w/ Dana" gaps, 1 retired-SKU, 2 dual-listing conflicts |

**Multi-hop answer:** `SKU-0014 Titan Rocker Switch 20A` and `SKU-0045 Titan Solenoid Valve 1in`
— A-class, ~2,000 helpdesk tickets each (complaint-heavy, many open), below safety stock at every
DC at window end, near-zero Lakeside counts.

## 2. What `build_modeled_layer` produces (the conformed star)

The notebook reads the analyst's `sku_xref_master`, drops the retired-SKU row, resolves the
dual-listing conflicts (primary listing wins), and turns it into governed mapping tables. Then it
fixes Lakeside's DD/MM/YYYY text dates, unifies sales (ERP + MegaMart **net** via settlements +
Lakeside, with a `source` column), merges inventory (ERP daily + Lakeside weekly, flagged by
`grain`), and resolves `ITM-` codes and free-text helpdesk names to SKUs — making unresolvable
rows explicit `UNMAPPED`/`UNRESOLVED` members instead of dropping them.

Conformed tables (Direct Lake), all keyed for a clean star:

- `c_dim_date` (date_key, date, fiscal columns, **is_post_acquisition**)
- `c_dim_product` (sku + product_name/category/subcategory/brand/abc_class/prices + itm/lsp/listing codes; **115 rows** = 100 SKUs + 13 LSX Lakeside-locals + UNMAPPED/UNRESOLVED)
- `c_dim_location` (DCs + Lakeside stores + marketplace), `c_dim_channel` (5)
- `c_fact_sales_unified` (source, date_key, sku, location_id, channel, qty, gross_amount, net_amount)
- `c_fact_inventory` (date_key, sku, location_id, on_hand_qty, safety_stock, is_stockout, grain, source)
- `c_fact_service`, `c_fact_service_parts`, `c_fact_helpdesk`

Cell 9 verifies counts: `c_dim_product`=115, `c_fact_sales_unified`=193,500, `c_fact_inventory`=195,220.

## 3. MultiSource_Raw model (v1)

The point of v1 is what you *don't* add. Tables: the **17 raw tables**, Direct Lake. Relationships:
only the within-ERP same-name joins auto-detect would plausibly find —
`sales_order_lines[sku]→products[sku]`, `inventory_daily[sku]→products[sku]`, and the two
`location_id` equivalents. **No** cross-source joins (xref, LS codes, ITM, listings are absent),
no date dimension, no measures, no descriptions, no Prep-for-AI. Not a strawman — every eval
question is technically answerable from these tables by a clever analyst; that's what makes the
wrong answers damning. The TMDL in `fabric/models/MultiSource_Raw.SemanticModel/` encodes exactly
this.

## 4. MultiSource_Modeled model (v2)

Tables: the **9 c_ tables**, Direct Lake. The TMDL in
`fabric/models/MultiSource_Modeled.SemanticModel/` carries everything below; this section is the
spec for the **Phase 5b portal fallback** if `fab import` won't take.

### Relationships (all single-direction, dim → fact, 1:*)
`c_dim_date[date_key]` → each of the five facts' `date_key`; `c_dim_product[sku]` → each of the
five facts' `sku`; `c_dim_location[location_id]` → `c_fact_sales_unified` and `c_fact_inventory`;
`c_dim_channel[channel]` → `c_fact_sales_unified`. (13 relationships; dims aren't interrelated, so
no ambiguity.)

### Measures (host on `c_fact_sales_unified`)
```dax
Revenue Gross = SUM ( c_fact_sales_unified[gross_amount] )
Revenue Net = SUM ( c_fact_sales_unified[net_amount] )
Units Sold = SUM ( c_fact_sales_unified[qty] )
ERP Revenue = CALCULATE ( [Revenue Net], c_fact_sales_unified[source] = "ERP" )
Marketplace Net Revenue = CALCULATE ( [Revenue Net], c_fact_sales_unified[source] = "MegaMart" )
Marketplace Gross Revenue = CALCULATE ( [Revenue Gross], c_fact_sales_unified[source] = "MegaMart" )
Lakeside Revenue = CALCULATE ( [Revenue Net], c_fact_sales_unified[source] = "Lakeside" )
Stockout Rate % =
    DIVIDE (
        CALCULATE ( SUM ( c_fact_inventory[is_stockout] ), c_fact_inventory[grain] = "daily" ),
        CALCULATE ( COUNTROWS ( c_fact_inventory ), c_fact_inventory[grain] = "daily" )
    )
Avg On-Hand Units =
    AVERAGEX ( VALUES ( c_dim_date[date_key] ), CALCULATE ( SUM ( c_fact_inventory[on_hand_qty] ) ) )
Sell-Through Ratio = DIVIDE ( [Units Sold], [Avg On-Hand Units] )
Tickets = COUNTROWS ( c_fact_helpdesk )
Open Complaints = CALCULATE ( [Tickets], c_fact_helpdesk[is_complaint] = TRUE, c_fact_helpdesk[is_open] = TRUE )
Tickets per 1K Units = DIVIDE ( [Tickets], [Units Sold] ) * 1000
Parts per 100 Units = DIVIDE ( SUM ( c_fact_service_parts[qty_used] ), [Units Sold] ) * 100
```
*(If a boolean column loaded as text, use `= "true"`. None of the measures use time-intelligence,
so marking `c_dim_date` as a date table is optional.)*

### Descriptions
Already in the TMDL (and they don't need XMLA — descriptions are part of the model definition).
If rebuilding in the portal, copy them from
`fabric/agent-config/MultiSource_Modeled_prep_for_ai.md`, which summarizes the table/column intent.

## 5. The AI layer (rationale)

The exact paste-text is in `fabric/agent-config/`. Why it's split the way it is:

- **Prep-for-AI (model-level)** holds all data semantics because the Data Agent's DAX generator
  reads only these: the data window and acquisition date, "total = all sources, net unless gross
  asked," stockout/risk definitions, complaint = `categoryId 1`, the ≥1,000-unit ratio convention
  with the ~12% unresolved caveat, sell-through as a ratio, DD/MM date reading, and "assume rather
  than ask."
- **Agent instructions (agent-level)** hold only style: no emojis, state period/sources/basis, one
  "Analysis:" line, answer-don't-ask, admit when something isn't derivable.
- **Synonyms** need XMLA write (unavailable here) — the conformed column names are the business
  terms and descriptions carry alternates. State this honestly; on a paid license synonyms are a
  ~30-minute add.

## 6. Scope boundary

The build stops when all three agents exist: **SupplyAgent_Raw** (bare, on MultiSource_Raw),
**SupplyAgent_Raw_Plus** (raw data on the lh_supply_demo SQL endpoint + heavy agent instructions —
the instructions-only experiment), and **SupplyAgent_Modeled** (on MultiSource_Modeled, with
Prep-for-AI + style instructions). Out of scope: any
report, verified answers, Teams/Copilot Studio, and **answering the 12 questions** — that walk-
through is the live demo, scored against `eval/MultiSourceAgent_Eval.xlsx` (gold answers,
2/1/0/−1 with a hallucination penalty, and token-per-correct-answer). Token/CU capture uses the
Capacity Metrics app (capacity admin on the F4) or Foundry/SDK.
