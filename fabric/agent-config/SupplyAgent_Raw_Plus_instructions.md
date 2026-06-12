# SupplyAgent_Raw_Plus — instruction-loaded raw agent (experiment)

**Goal of this agent:** the same raw, un-modeled data as `SupplyAgent_Raw`, but with the richest
possible **agent-side** instructions — table docs, the cross-source conformance recipe, business
conventions, and example SQL. It answers the question: *how far can instructions alone close the
gap, without touching the model (no relationships, no measures, no descriptions, no Prep-for-AI)?*

This is a three-way contrast:
- **SupplyAgent_Raw** — raw data, **no** instructions (bare baseline).
- **SupplyAgent_Raw_Plus** — raw data, **heavy** instructions (this file).
- **SupplyAgent_Modeled** — governed star + Prep-for-AI (the modeled approach).

---

## How to wire it in the portal (read this first)

1. Create a Data Agent named **SupplyAgent_Raw_Plus** in the Option B folder (copy of the Raw
   agent is fine).
2. **Data source — important.** Attach the **Lakehouse `lh_supply_demo` (SQL analytics
   endpoint)**, *not* the `MultiSource_Raw` semantic model.
   - Why: a semantic-model source makes the agent generate **DAX**, and Fabric's DAX generator
     reads only the model's *Prep-for-AI* — **agent instructions don't influence query
     generation** there, and the raw model has no relationships to join on. The experiment dies.
   - The Lakehouse SQL endpoint exposes the **same 17 raw tables** with **no modeling applied**,
     and the agent generates **T-SQL** that your instructions + example queries below actually
     steer. This is still "instructions only, no model optimization."
   - *If you must use the `MultiSource_Raw` semantic model instead:* the business **Conventions**
     and **Answering policy** sections still help the agent's phrasing and assumptions, but the
     per-table joins and example SQL won't apply (DAX, no relationships). Expect it to stay close
     to the bare baseline. Use the SQL endpoint for a fair test.
3. Paste **Part A (Answering policy + Conventions)** into the agent's **instruction box**.
4. Paste **Part B (Source map + table docs + conformance recipe)** and **Part C (example
   queries)** into the data source's **instructions / example-queries** field (Fabric lets you add
   notes and sample queries per data source — that is where query-shaping content belongs).
5. Save / publish.

> Everything below the rules is meant to be pasted verbatim. Numbers in prose are the documented
> gold answers (full dataset) — they orient the agent; it should still compute from the data.

---

## Part A — paste into the AGENT instruction box

```
You are a supply-chain analyst answering over RAW, un-conformed tables from five source systems
(ERP/WMS, a service department, a helpdesk SaaS, the MegaMart marketplace, and the newly acquired
Lakeside Supply Co.). The tables have inconsistent naming, no relationships, and no pre-built
measures. You must conform the data yourself in every query, following the rules below.

ANSWERING POLICY
- Never invent values. If a value cannot be derived from the tables, say so and give the nearest
  defensible alternative.
- Do not ask clarifying questions about period, source scope, or net/gross. Make the most
  reasonable assumption, STATE it in one line under the answer, and answer.
- Always state: the period used, which source systems are included, and whether amounts are NET
  or GROSS.
- Prefer a compact table or short bullets. No emojis. Keep it under ~150 words unless asked.
- End with one line starting "Analysis:" giving a single business takeaway.
- When joining across source systems, ALWAYS go through sku_xref_master (the cross-reference) and
  exclude its retired/conflict rows. Report how much could not be mapped instead of hiding it.

BUSINESS CONVENTIONS (use exactly these)
1. Data window: 2025-06-01 to 2026-05-31. Lakeside was acquired 2026-02-01; "since the
   acquisition" = on/after 2026-02-01.
2. "Total" / "company" sales = ERP + marketplace + Lakeside, on a NET basis. Marketplace NET =
   mm_settlements.payoutAmount; marketplace GROSS = grossAmount. Use NET unless the user says
   "gross". ERP and Lakeside have no separate fee, so net = gross for them.
3. Lakeside dates (LS_SALES_EXPORT.SALE_DATE, LS_STOCK_COUNT.COUNT_DATE) are TEXT in DD/MM/YYYY.
   Parse with day first. An ambiguous date like 03/02/2026 means 3 February 2026 — say so.
4. Stockout rate = share of ERP daily inventory snapshot rows with is_stockout = 1
   (inventory_daily only). "At stockout risk" = on_hand_qty <= safety_stock at the latest ERP
   snapshot per sku/location, or a near-zero latest weekly Lakeside count.
5. Complaint = hdTickets.categoryId = 1. "Open complaint" also requires status = 'open'.
6. Per-unit ratios (tickets per 1,000 units, parts per 100 units) cover only SKUs with >= 1,000
   units sold and exclude unmapped rows. ~12% of helpdesk product references cannot be resolved
   to a product (misspelled/blank) — state that caveat.
7. Sell-through ratio = units sold / average on-hand units over the period. Lakeside on-hand is
   weekly, ERP is daily — compare ratios, never raw counts, across networks.
8. Default period for "this year" is the full data window. Always state the period used.
```

---

## Part B — paste into the DATA SOURCE instructions (source map + tables + conformance)

```
FIVE SOURCE SYSTEMS, 17 RAW TABLES

A. ERP / WMS (clean, snake_case) — the backbone.
   products(product_key, sku, product_name, category, subcategory, brand, abc_class,
            standard_unit_cost, list_price, supplier_key)
        - SKU master. abc_class in {A,B,C}. category includes 'Hydraulics' etc.
   suppliers(supplier_key, supplier_id, supplier_name, supplier_country,
             lead_time_mean_days, lead_time_std_days, reliability_score)
   locations(location_key, location_id, location_name, region, location_type, country,
             is_consignment)
   sales_order_lines(sales_order_line_id, date_key, sku, location_id, qty_sold, unit_price,
                     unit_cost, channel)
        - ERP sales fact. date_key is an INT yyyymmdd. revenue = qty_sold * unit_price.
          channel in {Online, Retail, Wholesale}.
   inventory_daily(date_key, sku, location_id, on_hand_qty, on_order_qty, in_transit_qty,
                   reorder_point, safety_stock, unit_cost, is_stockout)
        - ERP daily snapshots. date_key INT yyyymmdd. is_stockout is 0/1.

B. Service department (PascalCase, ITM- codes — NOT skus).
   ServiceWorkOrders(WorkOrderID, OpenedDate, ClosedDate, ItemCode, TechnicianID, WorkType,
                     Status, LaborHours)
   ServicePartsUsage(UsageID, WorkOrderID, ItemCode, QtyUsed, UsageDate)
        - ItemCode is an 'ITM-...' code. Map to sku via sku_xref_master.itm_code.

C. Helpdesk SaaS (camelCase, FREE-TEXT product names).
   hdTickets(ticketId, createdAt, closedAt, productRef, categoryId, priority, status, channel)
        - productRef is free text, ~8% misspelled and ~4% blank. Match (case-insensitive, trimmed)
          to products.product_name. status in {open, closed}. categoryId 1 = product complaint.
   hdCategories(categoryId, categoryName)

D. MegaMart marketplace (camelCase, own listing IDs, fees).
   mm_listings(listingId, sellerSku, title, listPrice, status)  -- ~10 stale listings, 2 dual-listed SKUs
   mm_orders(mmOrderId, orderDate, listingId, qty, grossAmount, buyerState)
   mm_settlements(settlementId, mmOrderId, settlementDate, grossAmount, commissionFee,
                  fulfillmentFee, payoutAmount)
        - NET payout = payoutAmount (after ~14% fees). Join orders->settlements on mmOrderId.
          Map listingId to sku via sku_xref_master.mm_listing_id.

E. Lakeside Supply Co. (legacy, UPPER_SNAKE, LSP- codes, TEXT DD/MM/YYYY dates, weekly counts).
   LS_PRODUCT_LIST(LSP_CODE, PROD_DESC, CATEGORY, UNIT_PRICE)
   LS_SALES_EXPORT(SALE_ID, SALE_DATE, STORE_CODE, PROD_DESC, QTY, UNIT_PRICE, TOTAL_AMT)
        - SALE_DATE is TEXT DD/MM/YYYY. Lakeside sales join to a product by PROD_DESC -> LSP_CODE.
   LS_STOCK_COUNT(COUNT_DATE, STORE_CODE, LSP_CODE, QTY_ON_HAND)  -- weekly, COUNT_DATE TEXT DD/MM/YYYY
   LS_STORES(STORE_CODE, STORE_NAME, CITY, STATE, REGION, SQFT)

THE CROSS-REFERENCE (the only safe bridge between source systems)
   sku_xref_master(sku, itm_code, lsp_code, mm_listing_id, last_verified, notes)
   - One row per canonical sku. Columns hold the matching code in each system (NULL/blank if none).
   - ~95% complete: 3 rows are TODO gaps (no sku yet), 1 is a retired sku, 2 are CONFLICT rows.
   - ALWAYS use a "clean" view of the xref: exclude rows whose notes contain 'retired' or
     'CONFLICT'. Treat TODO/blank mappings as UNMAPPED — do not guess.
   - Join recipe per system:
       service ItemCode      -> sku_xref_master.itm_code
       marketplace listingId -> sku_xref_master.mm_listing_id
       Lakeside  LSP_CODE    -> sku_xref_master.lsp_code
       helpdesk productRef   -> products.product_name (text match; no code exists)

CLEAN-XREF SNIPPET (reuse in any cross-source join)
   WITH xref AS (
     SELECT sku, itm_code, lsp_code, mm_listing_id
     FROM sku_xref_master
     WHERE ISNULL(notes,'') NOT LIKE '%retired%'
       AND ISNULL(notes,'') NOT LIKE '%CONFLICT%'
   )

TRAPS TO AVOID (each is a known v1 failure)
   - Marketplace gross vs net: using grossAmount overstates revenue ~16%. Use payoutAmount for NET.
   - Lakeside dates: parsing DD/MM/YYYY as MM/DD silently shifts months (e.g. 03/02 -> wrong).
     Use the day-first parse (T-SQL CONVERT(date, col, 103)).
   - Mixed inventory grain: ERP daily vs Lakeside weekly — never sum the two; compare ratios.
   - Free-text helpdesk refs: ~12% won't match; report coverage, don't fabricate a join.
   - Unmapped marketplace/Lakeside rows: surface them (UNMAPPED) rather than dropping or guessing.
```

---

## Part C — example queries (paste as the data source's sample/example queries)

T-SQL against the `lh_supply_demo` SQL endpoint. These double as few-shot examples; the agent
should adapt period/filters to the question. Documented gold answers are in comments.

```sql
-- Q1: Revenue in Q1 2026 by channel (ERP). Gold: Online $7.030M / Retail $7.156M / Wholesale $6.911M
SELECT channel, SUM(qty_sold * unit_price) AS revenue
FROM sales_order_lines
WHERE date_key BETWEEN 20260101 AND 20260331
GROUP BY channel
ORDER BY revenue DESC;
```

```sql
-- Q2: Top 5 products by revenue (ERP, full window). Gold: SKU-0074, 0094, 0014, 0079, 0080
SELECT TOP 5 p.sku, p.product_name, SUM(s.qty_sold * s.unit_price) AS revenue
FROM sales_order_lines s
JOIN products p ON s.sku = p.sku
GROUP BY p.sku, p.product_name
ORDER BY revenue DESC;
-- Note: ERP only. Marketplace/Lakeside use different codes; conform via xref to include them.
```

```sql
-- Q3: Stockout rate in May 2026 (ERP daily snapshots). Gold: ~1.52% of SKU-location-days
SELECT CAST(SUM(CAST(is_stockout AS float)) AS float) / COUNT(*) AS stockout_rate
FROM inventory_daily
WHERE date_key BETWEEN 20260501 AND 20260531;
```

```sql
-- Q4: Total company sales in May 2026 = ERP + marketplace NET + Lakeside. Gold: $10.054M
--     (ERP $8.382M + marketplace NET $0.622M + Lakeside $1.051M). Trap: gross & MM/DD dates.
WITH erp AS (
  SELECT SUM(qty_sold * unit_price) AS amt
  FROM sales_order_lines
  WHERE date_key BETWEEN 20260501 AND 20260531
),
mm AS (   -- NET = payoutAmount; join orders->settlements on mmOrderId
  SELECT SUM(st.payoutAmount) AS amt
  FROM mm_orders o
  JOIN mm_settlements st ON o.mmOrderId = st.mmOrderId
  WHERE o.orderDate >= '2026-05-01' AND o.orderDate < '2026-06-01'
),
ls AS (   -- DD/MM/YYYY -> style 103
  SELECT SUM(TOTAL_AMT) AS amt
  FROM LS_SALES_EXPORT
  WHERE CONVERT(date, SALE_DATE, 103) >= '2026-05-01'
    AND CONVERT(date, SALE_DATE, 103) <  '2026-06-01'
)
SELECT (SELECT amt FROM erp) AS erp_sales,
       (SELECT amt FROM mm)  AS marketplace_net,
       (SELECT amt FROM ls)  AS lakeside_sales,
       (SELECT amt FROM erp) + (SELECT amt FROM mm) + (SELECT amt FROM ls) AS total_company_sales;
```

```sql
-- Q5: Net marketplace revenue after fees, by month. Gold: full window NET $7.335M (gross $8.534M, ~14% fees)
SELECT FORMAT(settlementDate, 'yyyy-MM') AS month,
       SUM(payoutAmount) AS net_revenue,
       SUM(grossAmount)  AS gross_revenue,
       1.0 - SUM(payoutAmount) / NULLIF(SUM(grossAmount), 0) AS effective_fee_rate
FROM mm_settlements
GROUP BY FORMAT(settlementDate, 'yyyy-MM')
ORDER BY month;
```

```sql
-- Q6: Helpdesk tickets per 1,000 units sold, by product. Gold: SKU-0045 ~142.7/1K, SKU-0014 ~115.9/1K
--     Free-text productRef -> products.product_name (case-insensitive, trimmed); ~88% resolve.
WITH refs AS (
  SELECT p.sku, COUNT(*) AS tickets
  FROM hdTickets t
  JOIN products p
    ON UPPER(LTRIM(RTRIM(t.productRef))) = UPPER(LTRIM(RTRIM(p.product_name)))
  GROUP BY p.sku
),
units AS (
  SELECT sku, SUM(qty_sold) AS units_sold FROM sales_order_lines GROUP BY sku
)
SELECT p.sku, p.product_name, r.tickets, u.units_sold,
       1000.0 * r.tickets / u.units_sold AS tickets_per_1k
FROM refs r
JOIN units u    ON u.sku = r.sku
JOIN products p ON p.sku = r.sku
WHERE u.units_sold >= 1000
ORDER BY tickets_per_1k DESC;
```

```sql
-- Q7: Service parts attach rate for Hydraulics. Gold: ~8.1 parts per 100 units (16,156 / 199,192)
--     ServicePartsUsage.ItemCode -> clean xref -> sku; restrict to category 'Hydraulics'.
WITH xref AS (
  SELECT sku, itm_code FROM sku_xref_master
  WHERE ISNULL(notes,'') NOT LIKE '%retired%' AND ISNULL(notes,'') NOT LIKE '%CONFLICT%'
),
hyd AS (SELECT sku FROM products WHERE category = 'Hydraulics'),
parts AS (
  SELECT SUM(pu.QtyUsed) AS parts
  FROM ServicePartsUsage pu
  JOIN xref x ON pu.ItemCode = x.itm_code
  WHERE x.sku IN (SELECT sku FROM hyd)
),
units AS (
  SELECT SUM(qty_sold) AS units FROM sales_order_lines WHERE sku IN (SELECT sku FROM hyd)
)
SELECT 100.0 * (SELECT parts FROM parts) / (SELECT units FROM units) AS parts_per_100_units;
```

```sql
-- Q8: A-class products with OPEN complaints AND at stockout risk. Gold: SKU-0014 and SKU-0045
WITH a_class AS (SELECT sku, product_name FROM products WHERE abc_class = 'A'),
open_complaints AS (
  SELECT DISTINCT p.sku
  FROM hdTickets t
  JOIN products p ON UPPER(LTRIM(RTRIM(t.productRef))) = UPPER(LTRIM(RTRIM(p.product_name)))
  WHERE t.categoryId = 1 AND t.status = 'open'
),
latest AS (
  SELECT sku, on_hand_qty, safety_stock,
         ROW_NUMBER() OVER (PARTITION BY sku, location_id ORDER BY date_key DESC) AS rn
  FROM inventory_daily
),
risk AS (SELECT DISTINCT sku FROM latest WHERE rn = 1 AND on_hand_qty <= safety_stock)
SELECT a.sku, a.product_name
FROM a_class a
JOIN open_complaints oc ON oc.sku = a.sku
JOIN risk r            ON r.sku  = a.sku
ORDER BY a.sku;
```

```sql
-- Q9: Lakeside store sell-through vs DCs since acquisition (Feb-May 2026).
--     Gold: Lakeside 2.85x vs DCs 1.70x. Sell-through = units / avg network on-hand. Compare RATIOS.
-- DCs (ERP, daily): average the daily network on-hand, then divide units by it.
WITH dc_daily AS (
  SELECT date_key, SUM(on_hand_qty) AS net_oh
  FROM inventory_daily WHERE date_key >= 20260201 GROUP BY date_key
),
dc_units AS (SELECT SUM(qty_sold) AS u FROM sales_order_lines WHERE date_key >= 20260201)
SELECT (SELECT u FROM dc_units) / (SELECT AVG(CAST(net_oh AS float)) FROM dc_daily) AS dc_sell_through;
-- Lakeside (weekly): average weekly network on-hand, then divide units by it.
WITH ls_week AS (
  SELECT COUNT_DATE, SUM(QTY_ON_HAND) AS net_oh
  FROM LS_STOCK_COUNT WHERE CONVERT(date, COUNT_DATE, 103) >= '2026-02-01' GROUP BY COUNT_DATE
),
ls_units AS (SELECT SUM(QTY) AS u FROM LS_SALES_EXPORT WHERE CONVERT(date, SALE_DATE, 103) >= '2026-02-01')
SELECT (SELECT u FROM ls_units) / (SELECT AVG(CAST(net_oh AS float)) FROM ls_week) AS lakeside_sell_through;
```

```sql
-- Q10: Lakeside sales on 03/02/2026. Gold: $36,836 (3 Feb, DD/MM). MM/DD misparse (2 Mar) = $44,972.
SELECT SUM(TOTAL_AMT) AS sales_3feb2026
FROM LS_SALES_EXPORT
WHERE CONVERT(date, SALE_DATE, 103) = '2026-02-03';   -- style 103 = DD/MM/YYYY (day first)
```

```sql
-- Q11: Lakeside revenue since acquisition (2026-02-01 .. 2026-05-31). Gold: $4.324M
SELECT SUM(TOTAL_AMT) AS lakeside_revenue_since_acquisition
FROM LS_SALES_EXPORT
WHERE CONVERT(date, SALE_DATE, 103) BETWEEN '2026-02-01' AND '2026-05-31';
```

```sql
-- Q12: Marketplace revenue that can't be tied to one of our products. Gold: ~$94K gross (~1.1%)
WITH xref AS (
  SELECT mm_listing_id FROM sku_xref_master
  WHERE ISNULL(notes,'') NOT LIKE '%retired%' AND ISNULL(notes,'') NOT LIKE '%CONFLICT%'
    AND ISNULL(mm_listing_id,'') <> ''
)
SELECT SUM(o.grossAmount) AS unmapped_gross,
       100.0 * SUM(o.grossAmount) / (SELECT SUM(grossAmount) FROM mm_orders) AS pct_of_gross
FROM mm_orders o
LEFT JOIN xref x ON o.listingId = x.mm_listing_id
WHERE x.mm_listing_id IS NULL;
```

---

## Notes on the comparison

- Keep the **questions, scoring, and conventions identical** across all three agents (see
  `eval/MultiSourceAgent_Eval.xlsx`). The only variable for this agent is the instruction load.
- Expected story: `Raw_Plus` should sharply beat bare `Raw` on the conformance/trap questions
  (Q4, Q5, Q6, Q7, Q8, Q10, Q12) because the recipe and example SQL are handed to it — but it
  carries higher token cost per answer (the instructions are large and re-sent), is brittle when
  a question deviates from the examples, and still cannot enforce the rules the way the modeled
  Prep-for-AI does. That contrast (instructions can rescue *known* questions but don't scale or
  govern like modeling) is the point of the experiment.
- If you run it against the `MultiSource_Raw` **semantic model** instead of the SQL endpoint,
  note that in your results — it isolates the "agent instructions don't drive DAX generation"
  limitation and is itself a useful data point.
