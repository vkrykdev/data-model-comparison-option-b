# MultiSource_Modeled — "Prep for AI" instructions

Paste this into **MultiSource_Modeled → Prep for AI → AI instructions** (model-level).
The Data Agent's DAX generator reads ONLY these model instructions, not the agent-level
instructions — so all data semantics live here.

Also confirm in Prep for AI:
- **AI data schema:** include all 9 `c_*` tables and the measures. Nothing to exclude — the
  notebook already left technical noise behind.
- **Descriptions:** already carried in the model definition (TMDL). Skim them; they double as
  the business glossary the agent uses.
- **Synonyms:** unavailable on this license (needs XMLA write). The conformed column names are
  the business terms; descriptions carry common alternates. This is an honest limitation to
  state in the pitch.

---

## Instruction text (paste verbatim)

```
Conventions for querying this model:
1. Data window is 2025-06-01 to 2026-05-31. Lakeside Supply Co. was acquired 2026-02-01;
   "since the acquisition" means c_dim_date[is_post_acquisition] = TRUE.
2. "Total" or "company" sales include all sources (ERP + marketplace + Lakeside) using
   net_amount. Marketplace revenue is NET of fees unless the user explicitly says gross.
   Always state which sources and which basis (net or gross) the answer used.
3. Stockout rate = share of daily snapshot rows with is_stockout = 1, ERP locations only
   (grain = 'daily'). "At stockout risk" = on_hand <= safety_stock at the latest snapshot,
   or a near-zero latest weekly count for Lakeside stores.
4. Complaints = c_fact_helpdesk[is_complaint] = TRUE. "Open complaints" additionally require
   is_open = TRUE.
5. Per-unit ratios (tickets per 1,000 units, parts per 100 units) are reported for SKUs with
   at least 1,000 units sold and exclude sku = 'UNRESOLVED' and sku = 'UNMAPPED'. State that
   roughly 12% of ticket references could not be resolved to a product.
6. Sell-through ratio = units sold / average on-hand units over the period. Lakeside on-hand
   is weekly; compare ratios, never raw snapshot counts, across networks.
7. Lakeside source dates were DD/MM/YYYY text and are already converted. If the user writes an
   ambiguous date such as 03/02/2026, interpret it as DD/MM (3 February 2026) and say so.
8. Default period for "this year" is the data window. Always state the period used.
9. When a question is ambiguous, make the most reasonable assumption, state it, and answer.
   Do not ask clarifying questions for period, source-scope, or net/gross choices.
```
