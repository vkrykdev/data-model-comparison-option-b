# `data/` — sample legacy multi-source tables

These are the 17 legacy tables, exactly as the five source systems export them (mixed naming, text
dates, own product codes, free-text fields). They feed **MultiSource_Legacy** and are conformed by the
`build_modeled_layer` notebook into the governed `c_*` star for **MultiSource_Modeled**.

> **These files are illustrative samples, not the full dataset.** The large fact tables have been
> **truncated to the header + the first 10 rows** so the repo stays small and the structure is easy
> to read. They are here to show **column layout and example values**, not to run the full demo.
> The small dimension/reference tables are committed in full.

## What's in each file

| File | Source system | Rows here | Full dataset | Notes |
|---|---|---|---|---|
| `products.csv` | ERP | 100 (full) | 100 | SKU master |
| `suppliers.csv` | ERP | 10 (full) | 10 | |
| `locations.csv` | ERP | 5 (full) | 5 | DCs / regions |
| `sales_order_lines.csv` | ERP | 10 (sample) | 128,500 | ERP sales fact |
| `inventory_daily.csv` | ERP | 10 (sample) | 182,500 | daily on-hand / stockout fact |
| `ServiceWorkOrders.csv` | Service dept (`ITM-` codes) | 10 (sample) | 6,000 | |
| `ServicePartsUsage.csv` | Service dept | 10 (sample) | 9,000 | |
| `hdTickets.csv` | Helpdesk SaaS | 10 (sample) | 12,000 | free-text `productRef` |
| `hdCategories.csv` | Helpdesk SaaS | 6 (full) | 6 | |
| `mm_orders.csv` | MegaMart marketplace | 10 (sample) | 25,000 | gross amounts |
| `mm_listings.csv` | MegaMart marketplace | 102 (full) | 102 | own listing IDs |
| `mm_settlements.csv` | MegaMart marketplace | 10 (sample) | 25,000 | net payout after ~14% fees |
| `LS_SALES_EXPORT.csv` | Lakeside Supply Co. (legacy) | 10 (sample) | 40,000 | DD/MM/YYYY **text** dates |
| `LS_PRODUCT_LIST.csv` | Lakeside Supply Co. | 60 (full) | 60 | own `LSP-` codes |
| `LS_STORES.csv` | Lakeside Supply Co. | 4 (full) | 4 | |
| `LS_STOCK_COUNT.csv` | Lakeside Supply Co. | 10 (sample) | 12,720 | weekly counts, text dates |
| `sku_xref_master.csv` | Cross-reference | 103 (full) | 103 | ~95% complete; TODO/conflict/retired rows on purpose |

## Regenerating the full dataset

The full synthetic dataset is **not committed**. These samples are for explanation only — to run the
actual Fabric build you supply the complete legacy tables to the lakehouse (see `PLAN.md` Phase 2–3).
