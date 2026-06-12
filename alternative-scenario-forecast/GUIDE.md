# Option B — Demand Forecast vs Actuals (Production-Grade Model)
## Data Agent v1 vs v2: Step-by-Step Build Guide

**Demo narrative:** v1 and v2 are *structurally identical* semantic models — same 20 tables, same relationships, same measures, same report. The **only delta is the AI layer** on v2 (descriptions, AI data schema, model AI instructions, verified answers). This dataset is deliberately shaped like a real production model — snowflaked dimensions, header/detail facts, multi-currency, SCD2, role-playing dates, a many-to-many promotion bridge, returns — because that's where an undescribed model fails hardest and where the upgrade pitch lands.

All product, brand, and retailer names are real-world names; **every number is synthetic** (say this once in the demo).

**Environment assumed:** workspace *Microsoft Fabric Demo Stand* on F4 *fabricassesmentcoe* (West Europe), Free license + Fabric trial → browser-only build (web modeling, Direct Lake), no XMLA (no synonyms via linguistic schema — known limitation), agents published in Fabric and consumed in **M365 Copilot**.

---

## 1. The schema (20 tables)

```
                       dim_category (4)
                            │ 1:*
                       dim_subcategory (10)          dim_brand (40)   dim_supplier (10)
                            │ 1:*                         │ 1:*            │ 1:*
                            └────────────► dim_product (120) ◄────────────┘
                                                │ 1:*
        dim_promotion (12) ──1:*── bridge_promotion_product (246) ──*:1(both)── dim_product
                                                │
 dim_date (913) ──┬─ active ──► fact_order_header[OrderDateKey] (32,625)
                  ├─ INACTIVE ► fact_order_header[ShipDateKey]
                  ├─ INACTIVE ► fact_order_header[RequestedDeliveryDateKey]
                  │                     │ 1:*  (OrderId)
                  │             fact_order_line (239,471)  ◄── dim_currency (6)
                  │                     │ *:1 dim_product        ▲ 1:*
                  ├─ active ──► fact_returns (6,473) ◄── dim_return_reason (5)
                  ├─ active ──► fact_fx_rate (5,478) ◄── dim_currency
                  ├─ active ──► fact_forecast (130,137) ◄── dim_forecast_version (24)
                  └─ active ──► fact_annual_plan (768) ◄── dim_category[CategoryName]
 dim_market (8) ──1:*──► fact_order_header / fact_returns / fact_forecast / fact_annual_plan / dim_customer
 dim_customer (53, SCD2) ──1:*──► fact_order_header[CustomerKey]
 dim_channel (3) ──1:*──► fact_order_header
```

| Table | Grain / rows | Production realism it adds |
|---|---|---|
| `dim_category` → `dim_subcategory` → `dim_product` | 4 / 10 / 120 | **Snowflake**: Category is 2 hops from products (no Category column on dim_product) |
| `dim_brand`, `dim_supplier` | 40 / 10 | Real brands (Apple, Samsung, Sony, JBL, Anker, …) + distributors (Ingram Micro, TD Synnex, …) |
| `dim_customer` | 53 rows / **45 accounts** | **SCD2**: surrogate `CustomerKey`, `ValidFrom/ValidTo/IsCurrent`; 8 accounts changed Segment in 2025. Real retailers: Best Buy, Walmart, MediaMarkt, Currys, Yodobashi, JB Hi-Fi… |
| `dim_market`, `dim_channel`, `dim_currency` | 8 / 3 / 6 | Markets carry local currency (USD, EUR, GBP, BRL, JPY, AUD) |
| `dim_promotion` + `bridge_promotion_product` | 12 / 246 | **Many-to-many** promo↔SKU via bridge; promos have date windows |
| `dim_forecast_version`, `dim_return_reason`, `dim_date` | 24 / 5 / 913 | Calendar extends past last actuals (`IsFutureMonth`) |
| `fact_order_header` | order: 32,625 | **Header/detail**; 3 date roles (Order/Ship/RequestedDelivery), CustomerKey, channel, currency, ship method |
| `fact_order_line` | line: 239,471 | Qty, **USD and local-currency amounts side by side** |
| `fact_returns` | RMA: 6,473 | Reason codes; links to dims and (inactive) to the originating order line |
| `fact_fx_rate` | day × currency: 5,478 | Daily rates per USD |
| `fact_forecast` | month × SKU × market × **version**: 130,137 | 24 monthly cycles, LagMonths 1–6, horizon → Nov 2026 |
| `fact_annual_plan` | month × **category** × market: 768 | Locked pre-FY, +5% stretch |

### The twelve traps (v1 failure modes → v2 instructions)

| # | Trap | Naive v1 behavior | Gold behavior (v2) |
|---|---|---|---|
| T1 | Multi-version forecast | Sums all versions: FY26 forecast **1,558,651** units (6.0× reality) | LagMonths = 1 → 261,484; states the convention |
| T2 | Grain mismatch | Invents "forecast by channel/customer" | Forecast exists only at month × SKU × market |
| T3 | Future horizon | Includes Jun–Nov 2026 (401,582 fc units, zero actuals) in "accuracy" | Excludes `IsFutureMonth = TRUE` |
| T4 | Lifecycle bias | Misses it | EOL +51.5% over-forecast; New −18.4% under |
| T5 | Mar-2026 disruption | Averages it away | Power & Charging actuals at 48% of forecast |
| T6 | Viral spike | Misses it | **Whoop 4.0**: Oct-25 actual 3,618 vs forecast 1,026 (3.5×); Nov cycle partially catches up |
| T7 | **Mixed currencies** | Sums `LocalNetAmount` across markets → **1,475.5M of meaningless mixed units (21.4× USD)** | Always `NetAmountUSD` / USD measures |
| T8 | **Role-playing dates** | Reports ordered as shipped | Nov-25 ordered $6.41M vs shipped $5.96M (−6.9%); ship-date analysis needs the inactive relationship |
| T9 | **Gross vs net** | Ignores returns | FY26 gross $37.42M − refunds $0.54M = net $36.87M |
| T10 | **SCD2** | DISTINCTCOUNT(CustomerKey) = 53 "customers" | 45 accounts via `CustomerId` / `IsCurrent` |
| T11 | **Promo bridge** | Joins promos wrong or sums outside the promo window | Bridge + promo date window: Black Friday 2025 Audio = $3.01M on 25 SKUs |
| T12 | **Snowflake** | Can't find Category (it's 2 joins away) | Navigates product → subcategory → category |

### Gold answers (FY2026 = Jun 2025 – May 2026; lag-1; actualized months; USD)

| Metric | Value |
|---|---|
| Forecast accuracy / WMAPE / bias | **78.6% / 21.4% / −1.8%** |
| WMAPE by lag 1→6 | 21.4 / 23.3 / 24.3 / 25.9 / 26.8 / 28.7 % |
| By lifecycle (WMAPE, bias) | EOL **53.3%, +51.5%** · Mature 17.9%, −3.5% · New 25.0%, **−18.4%** |
| By category (WMAPE, bias) | Audio 16.9%, −5.2% · P&C 22.1%, −3.5% · Smart Home **31.4%, +16.9%** · Wearables 20.3%, −9.2% |
| FY26 actual vs lag-1 forecast units | 266,394 vs 261,484 |
| FY26 gross / refunds / net revenue | $37.42M / $0.54M / $36.87M |
| Attainment vs plan | TOTAL **102.9%** ($37.42M / $36.35M): Audio 103.0% · P&C 99.6% · **Smart Home 77.7%** · Wearables 111.1% |
| Mar-26 Power & Charging | forecast 4,244 vs actual 2,029 (+109% bias) |
| Returns problem brand | **Govee 4.0%** unit return rate vs company 1.6% (2.5×); 76% of its returns quality-related |
| Top customers (2-yr gross) | Amazon US $3.6M · Walmart $3.4M · Best Buy $3.2M · Costco $2.8M · MediaMarkt $2.6M |
| 2-yr gross revenue | $68.83M |

Keep this table out of the model — it's your eval sheet (same role as `InventoryAgent_Eval.xlsx`). Numbers regenerate identically from `generate_option_b_prod.py` (seed 42).

---

## 2. Step 1 — Lakehouse

1. New Lakehouse in *Microsoft Fabric Demo Stand*: **`lh_forecast_vs_actuals`** (don't reuse Option A's — `dim_date`/`dim_product` names collide).
2. Upload all 20 CSVs to **Files**, then **Load to Tables** each, keeping the snake_case names.
3. Type checks: keys and quantities integer; amounts decimal; `EndOfLifeDate` has empty strings (loads as string — intended); booleans (`IsCurrent`, `IsWeekend`, `IsFutureMonth`, `IsLatest`, `IsQualityRelated`) may load as boolean or "True"/"False" strings — note which, and match in DAX filters.

---

## 3. Step 2 — Semantic model `ForecastVsActuals_v1`

New semantic model from the lakehouse (Direct Lake) → select all 20 tables → name `ForecastVsActuals_v1`. Create relationships exactly as follows (all 1:* single-direction unless stated):

**Snowflake / dimension-to-dimension**
| From (1) | To (*) |
|---|---|
| `dim_category[CategoryKey]` | `dim_subcategory[CategoryKey]` |
| `dim_subcategory[SubcategoryKey]` | `dim_product[SubcategoryKey]` |
| `dim_brand[BrandKey]` | `dim_product[BrandKey]` |
| `dim_supplier[SupplierKey]` | `dim_product[SupplierKey]` |
| `dim_market[MarketId]` | `dim_customer[MarketId]` |

**Orders (header/detail + date roles)**
| From (1) | To (*) | Mode |
|---|---|---|
| `dim_date[DateKey]` | `fact_order_header[OrderDateKey]` | **Active** |
| `dim_date[DateKey]` | `fact_order_header[ShipDateKey]` | **Inactive** |
| `dim_date[DateKey]` | `fact_order_header[RequestedDeliveryDateKey]` | **Inactive** |
| `fact_order_header[OrderId]` | `fact_order_line[OrderId]` | Active (header filters lines) |
| `dim_customer[CustomerKey]` | `fact_order_header[CustomerKey]` | Active |
| `dim_market[MarketId]` | `fact_order_header[MarketId]` | Active |
| `dim_channel[ChannelId]` | `fact_order_header[ChannelId]` | Active |
| `dim_product[SKU]` | `fact_order_line[SKU]` | Active |
| `dim_currency[CurrencyCode]` | `fact_order_line[CurrencyCode]` | Active |

> ⚠️ Do **not** relate `dim_date` to `fact_order_line[DateKey]`. Lines inherit dates through the header; the column is a denormalized convenience copy (very production-typical). Relating it would break the ship-date `USERELATIONSHIP` pattern.

**Returns, FX, forecast, plan, promo bridge**
| From (1) | To (*) | Mode |
|---|---|---|
| `dim_date[DateKey]` | `fact_returns[ReturnDateKey]` | Active |
| `dim_product[SKU]` | `fact_returns[SKU]` | Active |
| `dim_market[MarketId]` | `fact_returns[MarketId]` | Active |
| `dim_return_reason[ReasonKey]` | `fact_returns[ReasonKey]` | Active |
| `fact_order_line[SalesOrderLineId]` | `fact_returns[SalesOrderLineId]` | **Inactive** (audit drill only; active would create ambiguous paths) |
| `dim_date[DateKey]` | `fact_fx_rate[DateKey]` | Active |
| `dim_currency[CurrencyCode]` | `fact_fx_rate[CurrencyCode]` | Active |
| `dim_date[DateKey]` | `fact_forecast[DateKey]` | Active (month-start keys) |
| `dim_product[SKU]` | `fact_forecast[SKU]` | Active |
| `dim_market[MarketId]` | `fact_forecast[MarketId]` | Active |
| `dim_forecast_version[VersionId]` | `fact_forecast[VersionId]` | Active |
| `dim_date[DateKey]` | `fact_annual_plan[DateKey]` | Active |
| `dim_market[MarketId]` | `fact_annual_plan[MarketId]` | Active |
| `dim_category[CategoryName]` | `fact_annual_plan[Category]` | Active |
| `dim_promotion[PromotionId]` | `bridge_promotion_product[PromotionId]` | Active, single |
| `dim_product[SKU]` | `bridge_promotion_product[SKU]` | Active, **cross-filter Both** (so a promo selection filters products → sales) |

Mark `dim_date` as the date table. Create `_Measures` and add (identical in v1 and v2):

```dax
Units Sold = SUM ( fact_order_line[QtySold] )

Gross Revenue USD = SUM ( fact_order_line[NetAmountUSD] )

COGS USD = SUMX ( fact_order_line, fact_order_line[QtySold] * fact_order_line[UnitCostUSD] )

Gross Margin USD = [Gross Revenue USD] - [COGS USD]
Gross Margin % = DIVIDE ( [Gross Margin USD], [Gross Revenue USD] )
Avg Selling Price USD = DIVIDE ( [Gross Revenue USD], [Units Sold] )

Refunds USD = SUM ( fact_returns[RefundAmountUSD] )
Units Returned = SUM ( fact_returns[QtyReturned] )
Return Rate % = DIVIDE ( [Units Returned], [Units Sold] )
Net Revenue USD = [Gross Revenue USD] - [Refunds USD]

Shipped Revenue USD =
CALCULATE (
    [Gross Revenue USD],
    USERELATIONSHIP ( dim_date[DateKey], fact_order_header[ShipDateKey] )
)

Customer Count = DISTINCTCOUNT ( fact_order_header[CustomerId] )
-- NOT CustomerKey: dim_customer is SCD2 (53 rows, 45 accounts)

Order Count = DISTINCTCOUNT ( fact_order_header[OrderId] )

Forecast Units (All Versions) = SUM ( fact_forecast[ForecastQty] )
-- deliberately present: the T1 trap measure

Forecast Units (Lag-1) =
CALCULATE ( SUM ( fact_forecast[ForecastQty] ), fact_forecast[LagMonths] = 1 )

Forecast Revenue USD (Lag-1) =
CALCULATE ( SUM ( fact_forecast[ForecastRevenueUSD] ), fact_forecast[LagMonths] = 1 )

Forecast Units (Lag-1, Actualized) =
CALCULATE (
    SUM ( fact_forecast[ForecastQty] ),
    fact_forecast[LagMonths] = 1,
    dim_date[IsFutureMonth] = FALSE
)

Abs Error Units (Lag-1) =
VAR Grain =
    DISTINCT (
        UNION (
            SUMMARIZE ( fact_order_line, dim_date[MonthKey], dim_product[SKU], dim_market[MarketId] ),
            CALCULATETABLE (
                SUMMARIZE ( fact_forecast, dim_date[MonthKey], dim_product[SKU], dim_market[MarketId] ),
                fact_forecast[LagMonths] = 1,
                dim_date[IsFutureMonth] = FALSE
            )
        )
    )
RETURN
    SUMX (
        Grain,
        VAR A = CALCULATE ( SUM ( fact_order_line[QtySold] ) )
        VAR F = CALCULATE ( SUM ( fact_forecast[ForecastQty] ), fact_forecast[LagMonths] = 1 )
        RETURN ABS ( F - A )
    )

WMAPE % (Lag-1) = DIVIDE ( [Abs Error Units (Lag-1)], [Units Sold] )
Forecast Accuracy % (Lag-1) = 1 - [WMAPE % (Lag-1)]
Forecast Bias % (Lag-1) =
DIVIDE ( [Forecast Units (Lag-1, Actualized)] - [Units Sold], [Units Sold] )

Plan Revenue USD = SUM ( fact_annual_plan[PlanRevenueUSD] )
Plan Units = SUM ( fact_annual_plan[PlanQty] )
Attainment % = DIVIDE ( [Gross Revenue USD], [Plan Revenue USD] )

Avg FX Rate per USD = AVERAGE ( fact_fx_rate[RatePerUSD] )
```

*(If booleans loaded as strings, use `= "False"`.)*
*(The `dim_date[MonthKey]`/`dim_market[MarketId]` references inside `SUMMARIZE(fact_order_line, …)` resolve through the line → header → dim chains.)*

**Stop here for v1: no descriptions, no Prep-for-AI, nothing.**

## 4. Step 3 — `ForecastVsActuals_v2`

Rebuild identically (same tables, relationships, measures). Manual rebuild is the proof that schemas are genuinely identical; without XMLA there's no clean copy anyway. Validate: 3 identical visuals on both models must match to the unit.

---

## 5. Step 4 — The AI layer (v2 only)

`ForecastVsActuals_v2` → **Prep for AI**:

### 5.1 AI data schema
Include all tables + `_Measures`. Exclude technical columns: surrogate/key columns the user never names (`ProductKey`, `SubcategoryKey`, `BrandKey`, `SupplierKey`, `MarketKey`, `ChannelKey`, `ForecastVersionKey`, `SalesOrderLineId`, `MonthStartDateKey` if present). Keep `CustomerKey` visible (needed to explain SCD2) but describe it.

### 5.2 Descriptions (paste, trim to UI limits)
- `fact_order_line` — "Sales order lines (detail). Amounts exist twice: NetAmountUSD (corporate currency — use for ALL aggregation) and LocalNetAmount in the order's local currency (display only; NEVER sum across markets/currencies). DateKey duplicates the order date and has no relationship — date analysis flows through fact_order_header."
- `fact_order_header` — "One row per sales order. Three date roles: OrderDateKey (active default), ShipDateKey and RequestedDeliveryDateKey (inactive). 'When did we ship/deliver' requires the inactive relationships (see Shipped Revenue measure)."
- `fact_returns` — "Product returns (RMAs) with reason codes. Net revenue = gross − refunds. Return rate = units returned / units sold."
- `fact_forecast` — "Demand forecast at MONTH × SKU × market grain, MULTIPLE versions per target month (cycles, LagMonths 1–6). Never sum across versions/lags — default LagMonths=1. Contains future months with no actuals. No channel/customer dimension."
- `fact_annual_plan` — "Annual operating plan at month × CATEGORY × market, locked pre-FY. Not available at SKU/brand/customer/channel level."
- `fact_fx_rate` — "Daily exchange rates, local units per 1 USD. Reference only — order lines already carry USD amounts."
- `dim_customer` — "B2B accounts, SCD TYPE 2: one account (CustomerId) can have multiple rows (CustomerKey) as Segment changes. Count accounts by CustomerId or filter IsCurrent=TRUE; counting CustomerKey overcounts."
- `dim_product` — "120 SKUs. Category is reached via Subcategory → Category (snowflake). LifecycleStage: New / Mature / EOL."
- `dim_promotion` + `bridge_promotion_product` — "Promotions apply to subsets of SKUs via the bridge, within StartDate–EndDate. Promo analysis = bridge membership AND the promo's date window."
- `dim_date` — "Day grain; fiscal year June–May (FY2026 = Jun 2025–May 2026). IsFutureMonth=TRUE → months after the last actuals (June 2026 onward)."
- Short one-liners for: `LagMonths`, `ForecastQty` ("one row per version — unfiltered sums multiply ~6×"), `NetAmountUSD`, `LocalNetAmount`, `CustomerKey`/`CustomerId`, `IsFutureMonth`, `ShipDateKey`, and each measure. For `Forecast Units (All Versions)`: "only for analyzing version evolution — never 'the forecast'."

### 5.3 Model AI instructions (the DAX-generation tool reads these — data logic lives HERE, not in the agent)

```
Conventions for querying this model:
1. Currency: all reporting is in USD. Use NetAmountUSD / the USD measures. Never aggregate
   LocalNetAmount or LocalUnitPrice across markets or currencies.
2. "Revenue" defaults to gross revenue USD by ORDER date. "Net revenue" = gross − refunds.
   Shipping/delivery timing questions require ShipDateKey via the inactive relationship
   (use the [Shipped Revenue USD] measure).
3. "The forecast" = fact_forecast filtered to LagMonths = 1, unless the user names a cycle
   (VersionId) or lag. Always state the lag/version used. Never sum forecast across
   versions or lags.
4. Exclude dim_date[IsFutureMonth] = TRUE from accuracy, bias, or forecast-vs-actual
   comparisons; months after May 2026 have forecasts but no actuals.
5. Forecast accuracy = 1 − WMAPE; WMAPE = SUM(ABS(F−A)) / SUM(A) at month × SKU × market.
   Use [WMAPE % (Lag-1)] / [Forecast Accuracy % (Lag-1)] / [Forecast Bias % (Lag-1)].
6. Grains: forecast is month × SKU × market only (no channel, customer, brand splits);
   annual plan is month × category × market only. If asked below those grains, say it is
   not available and offer the nearest valid alternative.
7. Customers: dim_customer is SCD2. Count accounts with DISTINCTCOUNT of CustomerId or
   IsCurrent = TRUE, never CustomerKey.
8. Product hierarchy is snowflaked: product → subcategory → category. Brand is a separate
   dimension and is not the same as supplier (suppliers are distributors).
9. Promotion questions: filter SKUs through bridge_promotion_product AND restrict dates to
   the promotion's StartDate–EndDate.
10. Fiscal year runs June–May; FY2026 = 2025-06-01 to 2026-05-31. Default period for "this
    year / last fiscal year" is FY2026. Always state the period used.
11. Ambiguous questions: make the most reasonable assumption, state it, and answer. Do not
    ask back for period, lag, currency, or unit choices.
```

### 5.4 Verified answers (from report visuals)
- "What was our forecast accuracy in FY2026?" → card `Forecast Accuracy % (Lag-1)`, FY2026
- "How are we tracking against the annual plan?" → Attainment % by category
- "Which brand has a returns problem?" → Return Rate % by BrandName
- "Does forecast accuracy improve closer to the month?" → WMAPE by LagMonths

---

## 6. Step 5 — Report (build once, save-as for the other model)

1. **Forecast vs Actuals** — monthly `Units Sold` vs `Forecast Units (Lag-1)`; cards Accuracy/Bias/WMAPE; slicers FiscalYear, Category (from dim_category), Market.
2. **Where forecasting breaks** — WMAPE by LagMonths; Bias % by LifecycleStage; month × category bias matrix (Mar-26 P&C and Smart Home glow).
3. **Revenue quality** — Gross vs Net Revenue USD; Return Rate % by Brand (Govee stands out); ordered vs shipped revenue by month.
4. **Plan attainment** — Attainment % by Category and Market; cumulative actual vs plan.

## 7. Step 6 — Data agents

- **ForecastAgent_v1** → source `ForecastVsActuals_v1`, **no instructions**.
- **ForecastAgent_v2** → source `ForecastVsActuals_v2`, agent instructions = **style only**:

```
Response style:
- No emojis. Compact tables or short bullets for numbers.
- Always state period, filters, currency (USD), and forecast lag/version used — one line
  under the data.
- End with one line starting "Analysis:" containing a single business takeaway.
- If a question is ambiguous, state your assumption and answer; do not ask back.
- If a requested breakdown does not exist (forecast by channel, plan by SKU, etc.), say so
  and offer the nearest valid alternative.
- Keep answers under ~150 words unless asked for detail.
```

Publish both → consume in M365 Copilot (proven path; the emoji-reformatting caveat from Option A still applies — win on numbers, not formatting).

---

## 8. Step 7 — Demo script (14 questions)

| # | Question | v1 likely failure | v2 gold answer |
|---|---|---|---|
| 1 | "What was our forecast accuracy in FY2026?" | Mixes versions/lags, includes future months | 78.6% (WMAPE 21.4%), lag-1, FY2026, actualized months |
| 2 | "How much did we sell vs forecast in FY2026?" | Forecast ≈ 1.56M units (6×, T1) | 266,394 actual vs 261,484 lag-1 (bias −1.8%) |
| 3 | "What was total revenue last fiscal year?" | May sum LocalNetAmount → ~1.5B nonsense (T7) | $37.42M gross USD ($36.87M net of returns) |
| 4 | "Net revenue after returns, FY2026?" | Ignores returns (T9) | $36.87M (refunds $0.54M, 1.5% of gross) |
| 5 | "Does accuracy improve closer to the month?" | Can't separate lags | 21.4% lag-1 → 28.7% lag-6 |
| 6 | "Where is forecasting worst?" | Generic | EOL SKUs: WMAPE 53.3%, +51.5% over-forecast; Smart Home worst category (31.4%, +16.9%) |
| 7 | "What happened in March 2026 in Power & Charging?" | Averages away (T5) | Actuals at 48% of forecast (2,029 vs 4,244) — supply disruption |
| 8 | "Which product blew past forecast in Oct 2025?" | Misses (T6) | Whoop 4.0: 3,618 vs 1,026 forecast (3.5×); Nov cycle partially caught up |
| 9 | "How many customers do we have?" | 53 (CustomerKey, T10) | 45 active accounts (SCD2 explained) |
| 10 | "Revenue we *shipped* in November 2025?" | Returns ordered revenue (T8) | $5.96M shipped vs $6.41M ordered (−6.9%) |
| 11 | "How did Black Friday 2025 perform for Audio?" | Wrong join/window (T11) | $3.01M on the 25 promo SKUs in Nov-25 |
| 12 | "Which brand has a returns problem?" | No idea | Govee: 4.0% unit return rate vs 1.6% company avg; 76% quality-related |
| 13 | "How are we tracking against the annual plan?" | Wrong grain | 102.9% total; Smart Home only 77.7%, Wearables 111.1% |
| 14 | "Forecast accuracy by channel?" | **Hallucinates** a split (T2) | Doesn't exist (forecast has no channel); offers market/category instead |

Scoring: gold-answer match ±1% + a 0/1 flag for "stated its convention (lag, period, currency)".

## 9. Measurement, limitations, effort

- **Tokens/CU:** unchanged — Capacity Metrics app needs capacity-admin on `fabricassesmentcoe`; otherwise Foundry/Python SDK for literal tokens. The v1-vs-v2 contrast also shows up as retries and longer responses.
- **Synonyms/linguistic schema:** still blocked without XMLA — descriptions partially substitute; position honestly.
- **Effort:** Lakehouse + v1 ≈ ½–1 day (31 relationships, 26 measures), v2 + AI layer ≈ ½ day, report + agents + eval ≈ ½ day. The richer schema is the point: it makes v1's failures look like *your customer's* failures.

## 10. Reproducibility

`generate_option_b_prod.py` (seed 42) regenerates everything, including all twelve traps and the gold numbers. Tunable: promo calendar, disruption month/severity, lifecycle bias coefficients, Govee return rate, FX volatility.
