# SupplyAgent_Legacy — instruction-loaded legacy agent (SEMANTIC-MODEL / DAX variant)

**Use this variant when the agent's data source is the `MultiSource_Legacy` semantic model**
(generates **DAX**), not the `lh_supply_demo` SQL endpoint. For the SQL-endpoint wiring use
`SupplyAgent_Legacy_instructions.md` instead — its T-SQL recipe does not apply here.

## Why this variant is deliberately limited (read before pasting)

`MultiSource_Legacy` has only **four relationships, all inside ERP**:
- `sales_order_lines[sku] -> products[sku]`
- `inventory_daily[sku] -> products[sku]`
- `sales_order_lines[location_id] -> locations[location_id]`
- `inventory_daily[location_id] -> locations[location_id]`

There is **no relationship** from `products`/`sku_xref_master` to the service (ITM-code),
helpdesk (free-text), marketplace, or Lakeside tables. DAX can only traverse defined
relationships, so **cross-source conformance is impossible on this model**. Two consequences:

1. Only ERP-internal questions, plus single-table aggregations on the unrelated source tables,
   are answerable. Anything that must *join* a non-ERP source to the product master cannot be
   answered here — the agent must say so rather than invent a join.
2. A Power BI **semantic-model data source has NO example-queries field and NO data-source-
   instructions field** in the Data Agent config (per Microsoft docs, those are supported only
   for lakehouse / warehouse / KQL / graph sources). The ONLY paste surface you get is the
   agent-level **Data agent instructions** field. The few-shot DAX examples below therefore have
   nowhere to live in the agent config; the only injection point for example DAX on a semantic
   model is **Prep for AI -> Verified Answers** on the `MultiSource_Legacy` model itself (Power BI
   side) — which means turning on Prep for AI for the legacy model. That defeats the "legacy" control
   and may be license-limited, so treat PART 2 as OPTIONAL and experiment-compromising. The clean
   way to use example queries is the SQL-endpoint wiring (Path A), which supports them directly.

This is a weaker agent by construction. That is itself a fair demo point: legacy data with no
conformance layer can answer the easy ERP questions and must decline the cross-source ones.

---

## PART 1 — paste into the agent's "Data agent instructions" field (the only available paste surface)

```
You answer over MultiSource_Legacy, a semantic model of LEGACY, un-conformed tables from five source
systems. Only the ERP tables (sales_order_lines, inventory_daily, products, locations) are
related to each other. The service, helpdesk, marketplace, and Lakeside tables stand alone with
NO relationship to the product master.

ANSWERING POLICY
- Never invent values or fabricate a join. If a question needs data from a source that has no
  relationship to products (service/ITM, helpdesk free-text, marketplace listings, Lakeside
  products), you CANNOT conform it in this model. Say so plainly in one line and stop - do not
  approximate a cross-source join. Suggested wording: "Not derivable here: <source> has no
  relationship to the product master in this model, so it can't be joined. The modeled agent
  resolves this."
- For questions that ARE answerable (see below), don't ask clarifying questions about period,
  scope, net/gross, or date format - state the assumption in one line and answer.
- For "which / most / top / worst products" questions, return a ranked Top 5 with the comparison
  value beside each item.
- SANITY-CHECK ratios: a multi-month sell-through should land ~0.5x-5x; a value in the tens or
  hundreds means the on-hand denominator collapsed - recompute.
- Always state: period used, sources included, NET vs GROSS basis, and (when the question has a
  date) the DD/MM interpretation. Lakeside dates are TEXT DD/MM/YYYY; 03/02/2026 = 3 February.
- Compact table or short bullets, no emojis, no decorative headers, under ~150 words. End with
  one "Analysis:" line.

WHAT THIS MODEL CAN ANSWER (ERP-related scope)
- Revenue / units by channel, product, category, location (ERP).
- Stockout rate and stockout risk (ERP inventory_daily vs safety_stock).
- ERP sell-through and category-average / overstock comparisons among ERP products.
- Single-table totals on standalone sources: total marketplace gross/net, total Lakeside sales,
  Lakeside sales on a date or period. These are network totals, NOT joined to products.
- Lakeside-stores-vs-DCs sell-through (a NETWORK-LEVEL comparison, not per product). Compute
  each side as its own independent ratio and present both - do NOT report a single blended
  figure and do NOT declare DCs "not computable":
  * DCs (ERP, related tables): units = SUM(sales_order_lines[qty_sold]) since 2026-02-01;
    on-hand = average across daily snapshot dates of SUM(inventory_daily[on_hand_qty]) since
    2026-02-01. DCs are locations[location_type] = "Distribution Center".
  * Lakeside stores (standalone LS tables, aggregated alone - no join to products needed):
    units = SUM(LS_SALES_EXPORT[QTY]) where the parsed DD/MM/YYYY date >= 2026-02-01;
    on-hand = average across weekly count dates of SUM(LS_STOCK_COUNT[QTY_ON_HAND]) over the
    same window. Use PATTERN D (sum on-hand WITHIN each snapshot date, THEN average those
    per-date totals - never average row-level on-hand, which collapses the denominator and
    produces an absurd ratio in the hundreds/thousands).
  Window: "since the acquisition" = 2026-02-01 onward (NOT 2023). State the DD/MM date basis.
  Gold magnitudes: Lakeside ~2.85x vs DCs ~1.70x - both land in the 1x-3x range; a result in
  the tens/hundreds (or a "not computable") means the on-hand denominator was mis-aggregated -
  recompute before answering.

WHAT THIS MODEL CANNOT ANSWER (decline honestly - no relationship exists)
- Tickets per 1,000 units, parts attach rate, after-sale issues by category (helpdesk/service
  to product).
- "A-class products with open complaints" and any product-level marketplace attribution /
  unmapped-revenue share (marketplace listing to product).
- Lakeside results broken down BY PRODUCT or merged per-SKU with ERP.
```

## PART 2 — reusable DAX PATTERNS (general; not tied to any question)

> These are **building blocks, not answers** — placeholders in `<...>` are filled per question so
> the agent can handle ANY query, not a fixed list. They are NOT example query/answer pairs and
> are NOT meant to be matched verbatim.
>
> Placement note: a semantic-model data source has **no example-queries or data-source-
> instructions field**, so these patterns cannot be pasted into the agent config. Fold the few
> that help into PART 1 (agent instructions) as prose, OR put them in **Prep for AI -> AI
> Instructions / Verified Answers** on the model (which turns on a model-side AI layer and
> compromises the "legacy" control). Otherwise they are reference for whoever maintains the agent.
> Never hardcode a result; always compute from the data.

```
-- JOIN MAP (what DAX can traverse on this model)
-- Related (usable together): sales_order_lines + inventory_daily + products + locations,
--   via [sku]->products and [location_id]->locations.
-- Standalone (aggregate alone, cannot be joined to products): suppliers, ServiceWorkOrders,
--   ServicePartsUsage, hdTickets, hdCategories, mm_listings, mm_orders, mm_settlements,
--   LS_PRODUCT_LIST, LS_SALES_EXPORT, LS_STOCK_COUNT, sku_xref_master.
-- If a question needs a standalone source linked to a product/category, DECLINE (see PART 1).

-- PATTERN A - aggregate one column over a period (revenue, units, any total)
EVALUATE
ROW("<label>",
    CALCULATE( <SUM or SUMX over the table>, <period filter> ))
-- ERP period filter: <col>[date_key] >= <YYYYMMDD> && <col>[date_key] <= <YYYYMMDD>
-- ERP revenue expression: SUMX(sales_order_lines, sales_order_lines[qty_sold]*[unit_price])
-- Marketplace NET = SUM(mm_settlements[payoutAmount]); GROSS = SUM(mm_orders[grossAmount]).

-- PATTERN B - group + rank a measure (use for "by channel / by category / top N products")
EVALUATE
TOPN(<N>,
    SUMMARIZECOLUMNS( <group column(s)>,
        KEEPFILTERS(<optional period FILTER>),
        "<measure label>", <measure expression> ),
    [<measure label>], DESC)
ORDER BY [<measure label>] DESC      -- drop TOPN for the full breakdown

-- PATTERN C - a share/rate from one table (e.g. stockout rate, % of rows flagged)
EVALUATE
ROW("<rate label>",
    CALCULATE( DIVIDE(SUM(<flag column>), COUNTROWS(<table>)), <optional filter> ))

-- PATTERN D - sell-through / any (flow / average-stock) ratio for a NETWORK total.
-- Denominator = AVERAGE over the period of the network's TOTAL on-hand: sum on-hand WITHIN each
-- snapshot date, THEN average those per-date totals. Never average row-level on-hand. Each
-- network on its own grain/source; compare ratios, never legacy counts. Expect ~0.5x-5x; a value in
-- the tens/hundreds means a collapsed denominator - recompute.
VAR _units = CALCULATE(SUM(<units column>), <period filter>)
VAR _avgOH = AVERAGEX(
        FILTER(VALUES(<snapshot date column>), <period filter on that date column>),
        CALCULATE(SUM(<on_hand column>)))
RETURN DIVIDE(_units, _avgOH)

-- PATTERN E - per-entity ratio vs its group average, then "below average" (benchmark questions
-- such as overstock vs category). ERP-scope entities only. Mean of per-entity ratios, NOT a
-- pooled total. Rank by the entity's OWN ratio ASCENDING (slowest movers first) among
-- below-average entities - NOT by the gap (group avg - ratio). Ranking by the gap biases toward
-- whichever group has the highest average and can flag a fast-moving entity (high absolute
-- ratio) as "overstocked" just because its group average is higher still. Show each entity's
-- ratio next to its group average; never express as a percentage or a made-up "index"/"gap".
DEFINE
    VAR _ent = ADDCOLUMNS(
        SUMMARIZE(<fact>, <entity cols incl. the group key, e.g. products[category]>),
        "<ratio>", <ratio expression per entity, e.g. PATTERN D scoped to the entity> )
    VAR _withGrpAvg = ADDCOLUMNS(_ent,
        "<grp avg>", VAR _g = [<group key>]
                     RETURN AVERAGEX(FILTER(_ent, [<group key>] = _g), [<ratio>]) )
EVALUATE
TOPN(<N>, FILTER(_withGrpAvg, [<ratio>] < [<grp avg>]), [<ratio>], ASC)
ORDER BY [<ratio>] ASC

-- PATTERN F - Lakeside TEXT dates (DD/MM/YYYY) helpers (reuse inside any FILTER above)
--   year   = RIGHT(<date col>,4)
--   month  = MID(<date col>,4,2)          -- compare as text "01".."12", or VALUE(...) for ranges
--   exact day match: <date col> = "DD/MM/YYYY"   (state the DD/MM interpretation in the answer)

-- PATTERN G - multi-source total (e.g. "company-wide"): sum INDEPENDENT single-table aggregates
-- (PATTERN A per source) and add them. These are unrelated tables, so this is an UNCONFORMED sum
-- with no per-product reconciliation - say so, and state NET vs GROSS. Cannot attribute the total
-- back to specific products across sources on this model.
```

## Notes on the comparison

- This variant intentionally answers a smaller set than the SQL-endpoint Legacy. The honest
  contrast: with no conformance layer, legacy data over a relationship-poor model handles ERP-only
  questions and must decline the five cross-source ones (tickets/1K, attach rate, complaint+risk,
  attributable revenue, after-sale by category) - which is exactly the gap the Modeled agent
  closes.
- Keep questions, scoring, and conventions identical across agents (`eval/MultiSourceAgent_Eval.xlsx`).
- Do NOT add relationships, measures, or Prep-for-AI to `MultiSource_Legacy` to "rescue" it - that
  would turn it into a modeled agent and destroy the experiment's control.
