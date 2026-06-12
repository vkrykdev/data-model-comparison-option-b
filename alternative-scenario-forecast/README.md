# ARCHIVED — Forecast vs Actuals (earlier Option B exploration)

This is **not** the active demo. It's an earlier take on "Option B": a 20-table,
production-grade *Demand Forecast vs Actuals* model (snowflaked dims, header/detail orders,
multi-currency, SCD2 customers, promo bridge, returns, multi-version forecast). Kept as a
reference and a possible fallback narrative.

The active demo is the multi-source raw-vs-modeled build in the repo root.

```bash
python generate_data.py   # regenerates the 20 CSVs into ./data (self-contained, seed 42)
```

See `GUIDE.md` for its full build steps. Real product/brand names, synthetic numbers.
Spike SKU is Whoop 4.0; the model carries 12 deliberate v1 traps (multi-version forecast,
mixed currency, role-playing dates, SCD2 over-count, gross-vs-net, etc.).
