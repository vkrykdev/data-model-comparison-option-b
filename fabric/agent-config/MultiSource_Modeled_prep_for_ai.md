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
6. Sell-through ratio = units sold / average on-hand units over the period, computed per
   network on its own grain. ERP on-hand comes from daily snapshots; Lakeside on-hand comes
   from weekly counts. For each network, divide THAT network's units sold by the average of
   THAT network's own on-hand over the period - never divide one source's units sold by
   another source's on-hand. Compare ratios across networks, never raw snapshot counts.
   To compare networks (e.g. "Lakeside stores vs DCs"), GROUP [Sell-Through Ratio] by
   c_dim_location[location_type] - never report a single blended network figure when the
   question asks to compare. The location_type values are: Lakeside stores = 'Retail Store';
   distribution centers (DCs) = 'Distribution Center'. Exclude 'Marketplace' and 'Consignment'
   from a store-vs-DC comparison. The measure already pairs each network's units with its own
   on-hand, so grouping by location_type is sufficient. "Since the acquisition" applies the
   post-acquisition filter from convention 1. Expected magnitudes are roughly 1x-3x.
   Sanity guard: a network sell-through that comes out at or near zero almost always means the
   on-hand base was pulled from the wrong source or grain (e.g. ERP on-hand under Lakeside
   units); a value in the tens or hundreds means the on-hand denominator collapsed (a single
   snapshot used instead of the period average). Recheck the source/grain pairing - and that
   on-hand is averaged across snapshot dates, not row-level - before reporting such a result.
7. Category average sell-through = the mean of the individual product sell-through ratios
   within a category (average of per-product ratios, NOT total category units / total
   category on-hand), excluding sku = 'UNMAPPED' and sku = 'UNRESOLVED'. A product is
   overstocked when its own sell-through ratio is below its category's average. Rank "most
   overstocked" by the product's OWN sell-through ratio ASCENDING - the slowest-moving products
   first - and list only products that are actually below their category average. Do NOT sort
   by the absolute gap (category average minus product ratio): that just surfaces whichever
   category has the highest average and can flag a genuinely fast-moving product (e.g. one
   turning at 6x) as "overstocked" merely because its category average is higher still. For
   each listed product show its own ratio next to the category average (e.g. "0.47x vs 6.24x
   category avg") so the shortfall is visible without being the sort key. Always express
   sell-through as the ratio from convention 6 - never as a percentage and never as an invented
   composite "index" or "overstock gap" column. Also report how the underperformers split by
   ABC class (count of A / B / C products below their category average), because A-class
   overstock carries the most financial impact (in this data, no A-class product sells below
   its category average - the underperformers are B- and C-class).
8. Lakeside source dates were DD/MM/YYYY text and are already converted. If the user writes an
   ambiguous date such as 03/02/2026, interpret it as DD/MM (3 February 2026), answer on that
   basis, and state the interpretation you used.
9. Default period for "this year" is the data window. Always state the period used in the
   answer.
10. When a question is ambiguous, make the most reasonable assumption, state it, and answer.
    Do not ask clarifying questions for period, source-scope, net/gross, date-format, or
    benchmark-definition choices - apply the conventions above and proceed.
```
