# Presentation Guide — Legacy vs Well-Modeled: Microsoft Fabric Demo

A slide-by-slide blueprint for building this deck. Each slide entry includes a **title**, the
**story beat** it carries, **key content / bullets**, and notes on **visuals/diagrams**. The
deck is structured in six acts.

---

## Act 1 — The Company (slides 1–5)

### Slide 1 — Title slide

**Title:** "One Company. Five Systems. Zero Common Language."  
**Subtitle:** Microsoft Fabric — Legacy vs Well-Modeled Data Agent Demo  

---

### Slide 2 — The Business (what the company does)

**Title:** "An industrial distributor that keeps factories running"  
**Story beat:** Introduce the business before any data complexity. Ground the audience.

**Content:**
- **What they sell:** unglamorous-but-essential industrial parts — rocker switches, solenoid
  valves, hydraulic hoses, terminal blocks, anchors and fasteners, stretch wrap. The things a
  production line can't run a single shift without.
- **Who they serve:** factories, contractors, and maintenance crews who order in volume and
  expect same-day or next-day fulfilment. When a part is out of stock, the customer's line stops
  — so inventory accuracy is a revenue issue, not a back-office one.
- **How big:** roughly **$115M in annual net revenue** across five selling motions — Online,
  Retail, Wholesale, the MegaMart marketplace, and the newly acquired Lakeside stores.
- **The catalogue:** ~**100 canonical SKUs** across **Electronics, Hydraulics, Fasteners, and
  Mechanical** categories, with **A/B/C inventory classification** in active use (A-class items
  are the high-velocity, must-never-stock-out parts).
- **How they got here:** grew from one clean ERP system into a multi-channel, multi-geography
  business by **bolting on a new system every time the business expanded** — a service desk, a
  helpdesk tool, a marketplace, and finally an acquisition. Each made sense on its own.

**Talking point:** "This is a healthy, growing distributor. Nothing here is broken. The problem
isn't the business — it's that five chapters of growth each left behind their own data language."

**Visual:** simple company diagram — one hub (ERP) with arrows pointing to Online, Retail, and
Wholesale channels, plus two later additions (MegaMart, Lakeside) drawn in a different colour to
foreshadow the fragmentation.

---

### Slide 3 — The Timeline: How the data mess was created

**Title:** "Five years of growth, five different data languages"  
**Story beat:** Walk the audience through each addition chronologically so the data fragmentation
feels inevitable, not incompetent.

**Visual:** horizontal timeline with icons at each milestone.

| Date | Event | In plain English | Data consequence |
|---|---|---|---|
| *Origin* | Clean ERP/WMS launched | "We started with one tidy system that ran the whole company — sales, stock, and suppliers all in one place." | One system, one language — `snake_case` SKUs, daily inventory counts |
| *+2 yrs* | Service department added | "We began repairing and servicing what we sell, so we bought a tool built for work orders — and it numbers parts its own way." | Separate system — `ITM-` part codes, `PascalCase` columns, no link back to SKUs |
| *+3 yrs* | Helpdesk SaaS adopted | "Customer complaints needed a proper ticketing tool, so support staff now type the product name in by hand." | Free-text `productRef` typed by humans — ~8% misspelled, ~4% left blank |
| *+4 yrs* | MegaMart marketplace launched | "We opened a storefront on a big online marketplace — they keep a cut of every sale and pay us the rest weekly." | Own `listingId`, own order feed, ~14% commission fee; the money that lands ≠ the price shown |
| **Feb 1, 2026** | **Lakeside Supply Co. acquired** | "We bought a regional competitor that still runs on Access and Excel. Their stores count stock once a week and write dates the British way." | Legacy Access/Excel; DD/MM/YYYY text dates; `LSP-` codes; weekly stock counts; store-brand items the parent never carried |

**Talking point:** "Every one of these expansions made perfect business sense. Each created a
small data island. Today leadership wants answers that cross all five islands — and the
integration project is months away."

---

### Slide 4 — The Five Islands (data source map)

**Title:** "Five source systems, 17 tables, no common key"  
**Story beat:** Make the fragmentation visible and concrete.

**Visual:** five-island diagram — each island is a coloured box with its tables listed inside;
a "bridge" labelled `sku_xref_master` (95% complete) connects them, drawn with visible cracks.

| System | Tables | Naming | The quirk |
|---|---|---|---|
| **ERP / WMS** | `products`, `suppliers`, `locations`, `sales_order_lines`, `inventory_daily` | `snake_case` | Clean baseline. Stockout rate ~2%, concentrated in A/B products. |
| **Service Dept** | `ServiceWorkOrders`, `ServicePartsUsage` | `PascalCase` | Products are `ITM-####`, not SKUs. Must bridge through `sku_xref_master`. |
| **Helpdesk SaaS** | `hdTickets`, `hdCategories` | `camelCase` | `productRef` is free text. ~12% unresolvable. Complaints only via `categoryId = 1`. |
| **MegaMart** | `mm_listings`, `mm_orders`, `mm_settlements` | `mm_` prefix | Gross vs net (14% fees). ~10 stale listings. 2 dual-listed SKUs. |
| **Lakeside Supply** | `LS_SALES_EXPORT`, `LS_PRODUCT_LIST`, `LS_STORES`, `LS_STOCK_COUNT` | `UPPER_SNAKE` | DD/MM/YYYY text dates. `LSP-` codes. Weekly counts (not daily). Store-brand-only items. |
| **Glue** | `sku_xref_master` | analyst Excel | ~95% complete: 3 TODO gaps, 1 retired SKU, 2 conflicting entries. |

**The same problem, in actual rows.** Put one slice of each system side by side — the audience
*sees* that nothing lines up:

| Source | Sample row (abridged) | What's wrong with it |
|---|---|---|
| Lakeside `LS_SALES_EXPORT` | `LSS0000001, 03/01/2026, LS04, "LAKESIDE PRO SHOP TOWELS 12PK", 3, 39.48` | Date is **text** `DD/MM/YYYY` → `03/01` is **3 Jan**, not 1 Mar. Product is a free-text store-brand name with no SKU. Store code `LS04` is Lakeside's own. |
| Helpdesk `hdTickets` | `HD-00002, "Titan Solenoid Valve1 in", categoryId=1, status=open` | `productRef` is hand-typed — `"Valve1 in"` is missing a space (should be `Valve 1in`). `categoryId=1` is the only signal it's a complaint. |
| Helpdesk `hdTickets` | `HD-00006, "Meridian Full Brim Hard Hat lCass G Blue", ...` | `"lCass"` is a typo for `"Class"` — fuzzy-matching territory, no clean join exists. |
| Glue `sku_xref_master` | `SKU-0001, ITM-0001, <blank lsp_code>, <blank mm_listing_id>` | The bridge itself is **incomplete** — many SKUs have no Lakeside or marketplace mapping, so a naive join silently drops rows. |

**Talking point:** "There is no shared key. A SKU in the ERP, an `ITM-` code in service, a typed
name in the helpdesk, a `listingId` on the marketplace, and an `LSP-` code at Lakeside can all be
the *same physical product* — and nothing in the legacy data says so."

---

### Slide 5 — The Problem: Questions leadership needs answered *now*

**Title:** "Leadership can't wait for the integration project"  
**Story beat:** Create urgency. The audience feels the pressure.

**Content — 12 questions the business is actually asking:**

| # | Tier | Question | Why it's hard |
|---|---|---|---|
| Q1 | Easy | Revenue in Q1 2026 by channel? | Baseline — but cross-source totalling starts here |
| Q2 | Easy | Stockout rate in May 2026? | Definition drift: share of rows vs share of SKUs |
| Q3 | Medium | Total company sales in May 2026 incl. Lakeside & marketplace? | Cross-source + gross/net rule |
| Q4 | Medium | Products with most helpdesk tickets per 1,000 units sold? | Free-text conformance + ratio convention |
| Q5 | Medium | Service parts attach rate for Hydraulics? | ITM-code conformance |
| Q6 | Hard | A-class products with open complaints AND at stockout risk? | Multi-hop: ERP + Helpdesk + Inventory + Xref |
| Q7 | Hard | Lakeside store sell-through vs DCs since the acquisition? | Mixed-grain inventory + acquisition date |
| Q8 | Hard | Lakeside sales on 03/02/2026? | Date-format trap — DD/MM reads as Feb 3, not Mar 2 |
| Q9 | Medium | Lakeside revenue since the acquisition? | Period convention |
| Q10 | Hard | How much revenue can we tie to a known product? | Governance / honest gap surfacing |
| Q11 | Hard | Worst after-sale reliability by category? | Dual conformance: free-text + ITM + category rollup |
| Q12 | Hard | Most overstocked products vs their category sell-through? | Nested measure + mixed-grain inventory |

**Talking point:** "Every one of these is answerable. The question is *how accurately* — and how
many wrong turns, clarification round-trips, and confidently-false answers it takes to get there."

---

## Act 2 — Two Options: How to structure the data (slides 6–9)

### Slide 6 — Option A: Legacy model — "just land the tables"

**Title:** "Option A: 17 legacy tables, as landed"  
**Story beat:** Describe the path of least resistance honestly — it is not a strawman.

**Content:**
- All 17 source tables loaded directly into the lakehouse, `Direct Lake` mode.
- Relationships: only the obvious within-ERP joins that auto-detect would find
  (`sales_order_lines[sku] → products[sku]`, `inventory_daily[sku] → products[sku]`,
  two `location_id` equivalents).
- **No** cross-source joins (no xref, no LSP/ITM/listing bridges).
- No date dimension; no unified sales fact; no measures; no column descriptions;
  no Prep-for-AI instructions on the model.
- **Named in this demo:** `MultiSource_Legacy` semantic model.

**Pros column:**
- Zero transformation effort — tables are live immediately.
- A clever human analyst *can* derive correct answers from this model.

**Cons column:**
- Every cross-source question requires the analyst (or the AI agent) to re-derive the
  conformance recipe from scratch.
- Gross/net, date parsing, grain mismatches, free-text joins — all fall on the query author.
- Wrong answers aren't always obviously wrong.

**Visual:** screenshot of the `MultiSource_Legacy` model diagram in Fabric web modeling — 17
table boxes with only 4 thin relationship lines drawn, the rest floating disconnected.
*(Placeholder: capture from the deployed model once the workspace rename is published.)*

---

### Slide 7 — Option B: Modeled — "one notebook, one governed star"

**Title:** "Option B: One notebook transforms 17 tables into a governed star"  
**Story beat:** Show that the correct approach isn't a months-long project — it's one notebook.

**Content:**
The notebook `build_modeled_layer` does in one run:

1. Reads `sku_xref_master`, drops the retired-SKU row, resolves dual-listing conflicts
   (primary listing wins), builds governed mapping tables.
2. Fixes Lakeside's DD/MM/YYYY text dates.
3. Stacks all sales (ERP + MegaMart **net** via settlements + Lakeside) into one unified fact
   with a `source` column.
4. Merges inventory (ERP daily + Lakeside weekly), flagged by `grain` so grains are never mixed.
5. Resolves `ITM-` codes (service) and free-text helpdesk product names to SKUs.
   Unresolvable rows become explicit `UNMAPPED`/`UNRESOLVED` members — surfaced, not hidden.

**Result: 9 `c_*` tables in a clean star:**

| Type | Table | What it holds |
|---|---|---|
| Dimension | `c_dim_product` | 115 rows = 100 SKUs + 13 Lakeside-local + UNMAPPED/UNRESOLVED |
| Dimension | `c_dim_date` | One row/day; `is_post_acquisition` flag; fiscal columns |
| Dimension | `c_dim_location` | DCs + Lakeside stores + marketplace — one list |
| Dimension | `c_dim_channel` | Online, Retail, Wholesale, Marketplace, Lakeside |
| Fact | `c_fact_sales_unified` | 193,500 rows — all sources, gross + net |
| Fact | `c_fact_inventory` | 195,220 rows — ERP daily + Lakeside weekly, grain-flagged |
| Fact | `c_fact_service` | Work orders |
| Fact | `c_fact_service_parts` | Parts consumed |
| Fact | `c_fact_helpdesk` | Tickets with `is_complaint`, `is_open` flags |

**Named in this demo:** `MultiSource_Modeled` semantic model.

**Visual:** star schema diagram — 4 dimension boxes pointing inward to 5 fact boxes in the
centre, all connected by shared keys (`sku`, `date_key`, `location_id`, `channel`). *(Placeholder:
capture from the deployed `MultiSource_Modeled` model diagram.)*

---

### Slide 8 — The measures: what the model does that the legacy tables can't

**Title:** "14 governed measures — defined once, correct everywhere"  
**Story beat:** Measures are the governance layer. They encode the business rules so no one has
to re-derive them.

**Content (key measures to highlight):**

| Measure | What it encodes |
|---|---|
| `Revenue Gross` / `Revenue Net` | `SUM(gross_amount)` vs `SUM(net_amount)` — gross/net distinction always clear |
| `Marketplace Net Revenue` | Pre-filtered to MegaMart source; fee-adjusted automatically |
| `Lakeside Revenue` | Pre-filtered to Lakeside source |
| `Stockout Rate %` | Correct definition: share of daily ERP snapshot rows with `is_stockout = 1`, grain = 'daily' |
| `Sell-Through Ratio` | Units sold / average on-hand — paired per network, never cross-grain |
| `Open Complaints` | `is_complaint = TRUE AND is_open = TRUE` — definition locked |
| `Tickets per 1K Units` | Ratio correctly excludes UNMAPPED/UNRESOLVED |
| `Parts per 100 Units` | Service conformance pre-baked |

**The same answer, two ways — Q7 Lakeside sell-through (the worst case).** In the modeled star,
the question is a one-liner against a governed measure. Over the legacy tables, the same number
has to be reconstructed inline — including **parsing the DD/MM/YYYY text date with string
functions** just to filter "since the acquisition":

```dax
-- LEGACY (report-level DAX over legacy tables): re-parse text dates, hard-code the grain
RP Lakeside Sell-Through =
VAR u =
    SUMX (
        FILTER (
            LS_SALES_EXPORT,
            ( VALUE ( RIGHT ( LS_SALES_EXPORT[SALE_DATE], 4 ) ) * 10000      -- year
            + VALUE ( MID   ( LS_SALES_EXPORT[SALE_DATE], 4, 2 ) ) * 100     -- month
            + VALUE ( LEFT  ( LS_SALES_EXPORT[SALE_DATE], 2 ) ) )            -- day
                >= 20260201                                                  -- acquisition date
        ),
        LS_SALES_EXPORT[QTY]
    )
VAR inv = AVERAGE ( LS_STOCK_COUNT[QTY_ON_HAND] )   -- weekly grain, silently mixed
RETURN DIVIDE ( u, inv )
```

```dax
-- MODELED (governed measure): the date is already a real date, the grain is already separated
Sell-Through Ratio = DIVIDE ( [Units Sold], [Avg On-Hand Units] )
-- the author just drops [Sell-Through Ratio] on the visual and filters c_dim_date[is_post_acquisition]
```

**Talking point:** "Without these measures, an AI agent (or a report author) has to reconstruct
each definition from instructions every time — including string-parsing a date that should never
have been text. With them, it just calls the measure."

---

### Slide 9 — The honest trade-off

**Title:** "What modeling costs, and what it buys"

| | Legacy model | Modeled star |
|---|---|---|
| **Setup effort** | Minutes (land tables) | One notebook run (~12 min on F4) |
| **Schema** | 17 tables, mixed conventions | 9 governed `c_*` tables |
| **Relationships** | 4 (within-ERP only) | 13 (full star) |
| **Measures** | 0 | 14 |
| **Descriptions** | None | Full table + column descriptions |
| **Gross/net clarity** | Agent must derive | Encoded in measures |
| **Date traps** | Agent must handle DD/MM | Fixed at load time |
| **Unmapped rows** | Hidden or causes join failure | Explicit UNMAPPED member |
| **AI prep** | None | Prep-for-AI instructions on model |
| **Query speed** | Identical (same lakehouse) | Identical (Direct Lake) |

**Bottom line:** Speed is equal. Every other dimension favours the modeled approach.

---

## Act 3 — Power BI Reports (slides 10–13)

### Slide 10 — Two reports, same 12 questions

**Title:** "Same questions, two models — the visual side-by-side"  
**Story beat:** Before we involve AI agents, show that the modeling difference is already visible
in a standard Power BI report.

**Content:**
- Both reports are `byConnection` (live connect) to their respective deployed models.
- Both have **one page per eval question** — same 12 pages, same layout.
- `build_reports.py` generates both deterministically; every visual field binding is verified
  against the deployed model at generation time.

**Talking point:** "These are the same 12 questions a Data Agent will be asked later — but here a
human author had to build them. How hard that authoring was is itself the evidence."

---

### Slide 11 — Report: Legacy (`report_legacy`)

**Title:** "Report A: Answering the 12 questions over legacy tables"  
**Story beat:** Show it works — with caveats.

**Content:**
- Points at `MultiSource_Legacy` semantic model.
- To answer every question, ~21 **report-level DAX measures** are added in
  `reportExtensions.json` — cross-source sums, text-date parsing, xref lookups, free-text
  matching against typed product names.
- These extension measures must reference `SourceRef: { "Schema": "extension" }` or Power BI
  raises `Missing_References` — a technical complexity the report author must manage manually.
- Results: answers are achievable but some are approximate (gross/net ambiguity,
  date-format guesses, unresolved helpdesk refs silently dropped).

**Visual suggestion:** screenshot of one "hard" question page (e.g. Q7 sell-through) showing the
multi-line text-date-parsing DAX needed in the extension measure vs the clean model-measure call.

**Key message:** "It works. But every measure is custom, one-off, and not reusable outside
this report."

---

### Slide 12 — Report: Modeled (`report_modeled`)

**Title:** "Report B: Same questions, governed model"  
**Story beat:** Show the contrast — clean, no workarounds.

**Content:**
- Points at `MultiSource_Modeled` semantic model.
- Uses **only governed model measures** — no report-level DAX needed.
- Every visual just calls a measure like `[Revenue Net]`, `[Stockout Rate %]`,
  `[Open Complaints]`, `[Sell-Through Ratio]`.
- Results are exact: correct gross/net split, correct date parsing, explicit UNMAPPED
  row surfaced.

**Visual suggestion:** the same Q6 multi-hop question page — visuals calling two measures
(`[Open Complaints]`, `[Stockout Rate %]`) with a slicer on `abc_class = A`.

**Key message:** "The model pre-answered the hard parts. The report author just visualises."

---

### Slide 13 — Report comparison summary

**Title:** "What the reports reveal about the underlying model quality"

| | Legacy report | Modeled report |
|---|---|---|
| **Report-level measures** | ~21 custom DAX extensions | 0 |
| **Gross vs net** | Must select correct column in each visual | Pre-encoded in `[Revenue Net]` |
| **Date trap (DD/MM)** | Report-level string-parse expression | Fixed at lakehouse load |
| **Unmapped products** | Silently dropped by inner joins | Visible as `UNMAPPED` dimension member |
| **Reusability** | Per-report workarounds | Measures work in any tool connected to the model |
| **Author skill required** | Advanced DAX | Basic drag-drop |

---

## Act 4 — Data Agents (slides 14–18)

### Slide 14 — Introducing Data Agents

**Title:** "Microsoft Fabric Data Agents: natural language to DAX/SQL"  
**Story beat:** Brief orientation for any audience member who hasn't used Data Agents.

**Content:**
- A Fabric Data Agent accepts a natural-language question and generates a query
  (DAX for semantic model sources, T-SQL for SQL endpoint sources), executes it,
  and returns an answer.
- The quality of the answer depends on: (1) the quality of the model it queries,
  (2) the Prep-for-AI instructions on the model, and (3) the agent-level instructions.
- **Critical Fabric behaviour:** the DAX generator reads **only the model's Prep-for-AI
  instructions**, not the agent-level instructions. So data semantics must live in the model;
  agent-level instructions are style only.

**Visual:** simple flow diagram — User question → Data Agent → [Prep-for-AI + Model] → DAX/SQL
→ Lakehouse → Answer.

---

### Slide 15 — Agent A: SupplyAgent_Legacy

**Title:** "Agent A: Legacy data + maximum agent instructions — the instructions-only experiment"  
**Story beat:** Test the hypothesis that instructions alone can close the modeling gap.

**Content:**
- **Data source:** `lh_supply_demo` SQL analytics endpoint (T-SQL, 17 legacy tables, no model).
  Not the `MultiSource_Legacy` semantic model — a SQL endpoint lets agent instructions steer
  query generation; a model source produces DAX and the agent instructions don't reach the
  DAX generator.
- **Model preparation:** none (no relationships, no measures, no descriptions, no Prep-for-AI).
- **Agent instructions:** ~15,000 characters of compensating instructions —
  full table schema documentation, the cross-source conformance recipe, business conventions
  (gross/net, date formats, stockout definition, sell-through grain rules, complaint definition),
  and example SQL queries for the hardest questions.
- **Named:** `SupplyAgent_Legacy`.

**Visual:** icon of a "heavy backpack" on the agent — metaphor for compensating with instructions
what the model doesn't provide.

---

### Slide 16 — Agent B: SupplyAgent_Modeled

**Title:** "Agent B: Governed model + Prep-for-AI — the proper approach"  
**Story beat:** Show what happens when the model does the work.

**Content:**
- **Data source:** `MultiSource_Modeled` semantic model (9 `c_*` tables, 14 measures,
  full descriptions, 13 relationships).
- **Prep-for-AI instructions (model-level, 10 conventions):**
  1. Data window 2025-06-01 to 2026-05-31; acquisition date flag.
  2. "Total" sales = all sources, net unless gross specified.
  3. Stockout = share of daily ERP snapshot rows with `is_stockout = 1`.
  4. Complaint = `is_complaint = TRUE`; open = also `is_open = TRUE`.
  5. Per-unit ratios: SKUs ≥1,000 units; exclude UNMAPPED/UNRESOLVED; ~12% caveat.
  6. Sell-through: paired per network on its own grain; compare ratios, not legacy counts.
  7. Category average sell-through: mean of per-product ratios (not total/total).
  8. Lakeside dates are already converted; interpret ambiguous dates as DD/MM.
  9. Default period = data window; always state period used.
  10. Make reasonable assumptions, state them, answer — don't ask.
- **Agent instructions:** style only — no emojis, state period/sources/basis, one "Analysis:"
  line, answer-don't-ask, admit when something isn't derivable.
- **Named:** `SupplyAgent_Modeled`.

**Visual:** same agent icon but now the model carries the backpack, not the agent — the
intelligence is in the data layer.

---

### Slide 17 — Head-to-head: the 12 evaluation questions

**Title:** "Same 12 questions, both agents, scored live"  
**Story beat:** The centrepiece of the demo — show the contrast on real answers.

**Visual:** table with all 12 questions and two score columns (filled live during the demo).

| # | Question | Legacy | Modeled |
|---|---|---|---|
| Q1 | Revenue Q1 2026 by channel? | | |
| Q2 | Stockout rate May 2026? | | |
| Q3 | Total company sales May 2026 (incl. Lakeside + marketplace)? | | |
| Q4 | Most helpdesk tickets per 1,000 units sold? | | |
| Q5 | Service parts attach rate for Hydraulics? | | |
| Q6 | A-class products: open complaints + stockout risk? | | |
| Q7 | Lakeside sell-through vs DCs since acquisition? | | |
| Q8 | Lakeside sales on 03/02/2026? | | |
| Q9 | Lakeside revenue since the acquisition? | | |
| Q10 | Revenue attributable to a known product? | | |
| Q11 | Worst after-sale reliability by category? | | |
| Q12 | Most overstocked vs category sell-through? | | |

**Scoring:** 2 = correct · 1 = partially correct · 0 = wrong · −1 = hallucinated (confident and false)

**What a live run looks like (from the filled eval workbook):** the modeled agent scored
**2/2 on almost every question**. The legacy agent landed the easy baselines (Q1, Q2) but
**hallucinated on Q7** (reported a sell-through of ~684× by averaging weekly Lakeside counts
against daily DC counts — they looked "nearly identical" only because the grains were mixed),
**hallucinated on Q10** (claimed revenue tied to ERP product-mapping only, inventing a total and
hiding the unmapped gap), **overstated Q3** by adding marketplace *gross* instead of net, and on
**Q12** found "no overstocked products" where the model surfaces three. Several legacy answers
were only correct **after a clarification round-trip** (Q8 date, Q9 acquisition window).

**Gold answers to highlight during the demo:**
- **Q3:** $10.054M = ERP $8.382M + marketplace net $0.622M + Lakeside $1.051M. Legacy often
  reports gross marketplace (~$0.7M+ gross vs $0.622M net), overstating the marketplace slice by ~14%.
- **Q6:** SKU-0014 Titan Rocker Switch 20A and SKU-0045 Titan Solenoid Valve 1in — requires
  joining ERP inventory, helpdesk (free-text resolved), and xref in one answer.
- **Q7:** Lakeside 2.85× vs DCs 1.70× (Feb–May 2026). Legacy mixes weekly vs daily on-hand
  and can return a wildly inflated, near-equal ratio for both networks.
- **Q8:** $36,836 on Feb 3, 2026. Legacy misparses as Mar 2 = $44,972.
- **Q10:** Modeled surfaces $0.553M unattributable (stale MegaMart listings). Legacy reports
  effectively 100% attributable, hiding the governance gap.

---

### Slide 18 — Why the gap exists (technical explanation)

**Title:** "Where Legacy fails — and why instructions can't fully close the gap"

**Three failure modes to illustrate:**

**1. Gross vs net (Q3)**
- Legacy must be told "marketplace net = `mm_settlements.payoutAmount`" and reconstruct the
  join every query. One misfire conflates gross `mm_orders.grossAmount` (~14% higher).
- Modeled: `[Marketplace Net Revenue]` measure pre-applies the settlement join. The DAX
  generator calls the measure; the error is structurally impossible.

**2. Date format trap (Q8)**
- Legacy instructions say "parse DD/MM" but the T-SQL generator may still write
  `WHERE SALE_DATE = '2026-03-02'` when the user asks for "03/02/2026".
- Modeled: the notebook already converted the dates at load time. The column is a proper date;
  no ambiguity remains.

**3. Multi-hop gap-surfacing (Q10)**
- Legacy: inner joins drop unmatched rows silently → 100% attribution looks clean.
- Modeled: `UNMAPPED` is an explicit dimension member → $0.553M unattributable is visible
  and the agent reports it honestly.

**Key insight:** "Instructions describe what to do. The model *does it*. For structural problems
— wrong column type, missing join key, dropped rows — instructions can advise but can't fix."

---

## Act 5 — Conclusion (slides 19–20)

### Slide 19 — The benefits of a proper model

**Title:** "What you get from one notebook and one governed semantic model"

**Content — six benefits:**

1. **Accuracy** — structural conformance (gross/net, date parsing, grain) is fixed once at the
   model layer, not re-derived per query. Fewer wrong answers by construction.

2. **Honesty** — `UNMAPPED`/`UNRESOLVED` members surface governance gaps instead of hiding them
   in dropped rows. The model is honest about what it doesn't know.

3. **Reusability** — 14 measures defined once work in Power BI, Data Agents, Excel, Copilot,
   and any future tool connected to the model. No per-report or per-agent duplication.

4. **Fewer round-trips** — the agent answers in one shot instead of asking "did you mean gross or
   net?" or being corrected and re-asked. The model does the disambiguation the agent would
   otherwise push back to the user.

5. **Maintainability** — when a business rule changes (e.g. the complaint definition, the
   fee rate), it changes in one place: the measure or the prep instruction. Not in 12 agent
   instructions and 21 report-level DAX formulas.

6. **Trustworthy answers to non-technical stakeholders** — leadership gets correct, sourced,
   period-stated answers without knowing what DD/MM/YYYY means.

---

### Slide 20 — Summary scorecard

**Title:** "The verdict"

| Dimension | Legacy tables | Legacy + Instructions | Governed model + Prep-for-AI |
|---|---|---|---|
| Setup time | Minutes | + 30 min instructions | + 1 notebook run (~12 min) |
| Query speed | Baseline | Same | Same (Direct Lake) |
| Cross-source accuracy | Low | Medium | High |
| Structural errors (gross/net, dates) | Frequent | Reduced | Near-zero |
| Governance gaps surfaced | No | Partial | Yes |
| Measure reuse | None | None | Full |
| Clarification round-trips | Frequent | Some | Rare |
| Recommended for production AI | ✗ | ✗ | ✓ |

---

## Act 6 — What's next: optimization options (slide 21)

### Slide 21 — Further optimization options

**Title:** "The model is the foundation — here's what you can build on top"

**Option 1 — Synonyms / linguistic schema**  
- Maps business terms ("sales," "revenue," "income") to model columns automatically.
- Requires XMLA write access (Pro or PPU licence).
- Reduces the need for explicit conventions in Prep-for-AI; the model understands natural
  business vocabulary natively.
- Estimated effort: ~30 minutes with Tabular Editor once the licence is available.

**Option 2 — Ontology / knowledge graph layer**  
- Encode the cross-source relationships (SKU ↔ ITM code ↔ LSP code ↔ listing ID) as a
  formal ontology rather than a flat xref spreadsheet.
- Enables semantic reasoning ("what is the service history of this product across all systems?")
  that goes beyond tabular joins.
- Tooling: Azure Purview, a dedicated knowledge graph (e.g. Apache Jena / Neptune), or a
  Fabric-native ontology layer when available.

**Option 3 — Automated xref completion**  
- The 3 "TODO" gaps and 2 conflicting entries in `sku_xref_master` are currently surfaced as
  `UNMAPPED` — governance honest, but still an open data quality issue.
- An LLM-assisted matching pass (product name similarity + supplier cross-reference) could
  close the remaining ~5%, promoting `UNMAPPED` rows to attributed products.

**Option 4 — Real-time / streaming layer**  
- The current model is batch (notebook re-run). Adding a streaming ingest path
  (Fabric Eventstream) would enable live stockout alerts and intra-day sales tracking
  without changing the semantic model or reports.

**Option 5 — Copilot Studio / Teams integration**  
- Both agents can be published to Microsoft Teams or embedded in Copilot Studio for
  organisation-wide access — business users ask questions in Teams, the governed model
  ensures they get correct answers.
- Out of scope for this demo but a one-step configuration once the model is trusted.

---

## Appendix — Reference data for the presenter

### The 14 DAX measures (for Q&A)

```dax
Revenue Gross = SUM ( c_fact_sales_unified[gross_amount] )
Revenue Net = SUM ( c_fact_sales_unified[net_amount] )
Units Sold = SUM ( c_fact_sales_unified[qty] )
ERP Revenue = CALCULATE ( [Revenue Net], c_fact_sales_unified[source] = "ERP" )
Marketplace Net Revenue = CALCULATE ( [Revenue Net], c_fact_sales_unified[source] = "MegaMart" )
Marketplace Gross Revenue = CALCULATE ( [Revenue Gross], c_fact_sales_unified[source] = "MegaMart" )
Lakeside Revenue = CALCULATE ( [Revenue Net], c_fact_sales_unified[source] = "Lakeside" )
Stockout Rate % = DIVIDE(
    CALCULATE( SUM(c_fact_inventory[is_stockout]), c_fact_inventory[grain]="daily" ),
    CALCULATE( COUNTROWS(c_fact_inventory), c_fact_inventory[grain]="daily" )
)
Avg On-Hand Units = AVERAGEX( VALUES(c_dim_date[date_key]),
    CALCULATE( SUM(c_fact_inventory[on_hand_qty]) ) )
Sell-Through Ratio = DIVIDE( [Units Sold], [Avg On-Hand Units] )
Tickets = COUNTROWS( c_fact_helpdesk )
Open Complaints = CALCULATE( [Tickets],
    c_fact_helpdesk[is_complaint]=TRUE, c_fact_helpdesk[is_open]=TRUE )
Tickets per 1K Units = DIVIDE( [Tickets], [Units Sold] ) * 1000
Parts per 100 Units = DIVIDE( SUM(c_fact_service_parts[qty_used]), [Units Sold] ) * 100
```

### Gold answers for the 12 questions

| Q | Gold answer |
|---|---|
| Q1 | Online $7.030M / Retail $7.156M / Wholesale $6.911M = total $21.097M (ERP, Jan–Mar 2026) |
| Q2 | 1.52% of SKU-location-day snapshots (ERP daily, May 2026) |
| Q3 | $10.054M = ERP $8.382M + marketplace net $0.622M + Lakeside $1.051M |
| Q4 | SKU-0045 Titan Solenoid Valve 142.7/1K · SKU-0014 Titan Rocker Switch 115.9/1K |
| Q5 | 8.1 parts per 100 units (Hydraulics; 16,156 parts / 199,192 units) |
| Q6 | SKU-0014 Titan Rocker Switch 20A + SKU-0045 Titan Solenoid Valve 1in |
| Q7 | Lakeside 2.85× vs DCs 1.70× (Feb–May 2026) |
| Q8 | $36,836 on Feb 3, 2026 (DD/MM misparse = Mar 2 = $44,972) |
| Q9 | $4.324M (Feb 1 – May 31, 2026; ~9% store-brand items) |
| Q10 | 99.5% attributable; $0.553M unattributable = stale MegaMart UNMAPPED listings |
| Q11 | Hydraulics 88.5 issues/1K units (complaints + service parts); Electrical 27.9 |
| Q12 | SKU-0029 Atlas Drop-In Anchor M8 (0.47×) · SKU-0039 Sterling Sleeve Anchor M12 (0.50×) · SKU-0081 Atlas O-Ring Kit (0.50×) |

### Key planted traps (for presenter awareness)

- **Stockout rate:** "share of A-class SKUs" vs "share of daily snapshot rows" — two different
  numbers, both defensible. The Prep-for-AI locks the definition.
- **Marketplace gross vs net:** ~14% fee; gross ≈ $0.723M, net ≈ $0.622M for May 2026.
- **Lakeside date trap:** 03/02/2026 → Feb 3 ($36,836) not Mar 2 ($44,972).
- **Q10 governance gap:** $0.553M lives in stale UNMAPPED MegaMart listings —
  legacy agents report ~100% attribution; the modeled agent surfaces the gap.
- **Unresolved helpdesk refs:** ~12% of `productRef` values don't map to a SKU.
  Convention: state the caveat, exclude UNRESOLVED from per-unit ratios.
