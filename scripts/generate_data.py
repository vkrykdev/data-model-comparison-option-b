"""
Option B (multi-source) — "Raw vs Well-Modeled" generator
Reuses Option A's ERP world (/mnt/project), adds 5 source systems with their own
naming conventions + deliberate quirks. 17 tables total.

Planted traps:
  - inventory_daily: stockout rate raised 0.02% -> ~2%, concentrated in A/B SKUs
  - 2 "quality SKUs" (A-class): high helpdesk tickets, open complaints in May-2026,
    AND below safety stock at window end -> the multi-hop tier-3 question
  - hdTickets.productRef: free-text names, ~8% misspelled, ~4% blank
  - mm_listings: ~10 stale listings (sellerSku doesn't exist) + 2 SKUs with dual listings
  - mm_settlements: gross vs net trap (fees ~14%)
  - LS_*: dates as TEXT DD/MM/YYYY, weekly stock counts, own LSP codes, 10 store-brand
    products that exist nowhere else
  - sku_xref_master: ~95% complete, 3 TODO gaps, 1 retired-SKU conflict, dual-listing rows
"""
import numpy as np
import pandas as pd
import os, re

rng = np.random.default_rng(7)
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-erp-optionA"   # Option A dimensional export = the ERP source system
OUT = ROOT / "data"                 # the 17 raw multi-source tables
os.makedirs(OUT, exist_ok=True)

prod = pd.read_csv(f"{SRC}/DimProduct.csv")
supp = pd.read_csv(f"{SRC}/DimSupplier.csv")
loc  = pd.read_csv(f"{SRC}/DimLocation.csv")
sales = pd.read_csv(f"{SRC}/FactSales.csv")
inv  = pd.read_csv(f"{SRC}/FactInventorySnapshot.csv")

def snake(df):
    def cv(c):
        c = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", c)
        c = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", c)
        return c.lower()
    return df.rename(columns=cv)

dates = pd.date_range("2025-06-01", "2026-05-31", freq="D")
dk = dates.strftime("%Y%m%d").astype(int)

# ---------------------------------------------------------------- planted quality/risk SKUs
cand = prod[(prod.ABCClass == "A") & prod.Category.isin(["Hydraulics", "Electrical"])]
quality_skus = cand.SKU.head(2).tolist()
print("Quality/risk SKUs:", quality_skus,
      prod.set_index("SKU").loc[quality_skus, "ProductName"].tolist())

# ================================================================ A. ERP (snake_case)
snake(prod).to_csv(f"{OUT}/products.csv", index=False)
snake(supp).to_csv(f"{OUT}/suppliers.csv", index=False)
snake(loc).to_csv(f"{OUT}/locations.csv", index=False)
snake(sales).to_csv(f"{OUT}/sales_order_lines.csv", index=False)

# inventory_daily: copy + inject stockout episodes (A/B SKUs) + end-of-window risk for planted SKUs
inv2 = snake(inv).copy()
ab = prod[prod.ABCClass.isin(["A", "B"])].SKU.tolist()
pairs = inv2[inv2.sku.isin(ab)][["sku", "location_id"]].drop_duplicates()
pairs = pairs.sample(n=min(100, len(pairs)), random_state=11)
inv2 = inv2.sort_values(["sku", "location_id", "date_key"]).reset_index(drop=True)
idx_map = inv2.groupby(["sku", "location_id"]).indices
stock_rows = []
for _, p in pairs.iterrows():
    ix = idx_map[(p.sku, p.location_id)]
    n_ep = rng.integers(4, 8)
    for _ in range(n_ep):
        start = rng.integers(0, len(ix) - 12)
        length = rng.integers(5, 10)
        stock_rows.extend(ix[start:start + length])
stock_rows = np.unique(stock_rows)
inv2.loc[stock_rows, "on_hand_qty"] = 0
inv2.loc[stock_rows, "is_stockout"] = 1
# planted: last 12 days below safety stock at every DC (risk, not necessarily stocked out)
last12 = set(dk[-12:])
for s in quality_skus:
    m = (inv2.sku == s) & inv2.date_key.isin(last12)
    inv2.loc[m, "on_hand_qty"] = np.maximum((inv2.loc[m, "safety_stock"] * 0.35).astype(int), 1)
    inv2.loc[m, "is_stockout"] = 0
print(f"inventory_daily stockout rate: {inv2.is_stockout.mean():.2%} ({inv2.is_stockout.sum():,} rows)")
inv2.to_csv(f"{OUT}/inventory_daily.csv", index=False)

# ================================================================ B. Service (PascalCase)
sku_digits = prod.SKU.str.replace("SKU-", "", regex=False)
itm_of = dict(zip(prod.SKU, "ITM-" + sku_digits))
hyd_el = prod[prod.Category.isin(["Hydraulics", "Electrical"])].SKU.tolist()
other = prod[~prod.Category.isin(["Hydraulics", "Electrical"])].SKU.tolist()
n_wo = 6000
wo_sku = np.concatenate([rng.choice(hyd_el, int(n_wo * 0.7)), rng.choice(other, n_wo - int(n_wo * 0.7))])
rng.shuffle(wo_sku)
opened = rng.choice(dates[:-30], n_wo)
dur = rng.integers(1, 21, n_wo)
closed = pd.to_datetime(opened) + pd.to_timedelta(dur, "D")
status = np.where(rng.random(n_wo) < 0.07, "Open",
         np.where(rng.random(n_wo) < 0.05, "In Progress", "Closed"))
wo = pd.DataFrame({
    "WorkOrderID": [f"WO-{100001+i}" for i in range(n_wo)],
    "OpenedDate": pd.to_datetime(opened).strftime("%Y-%m-%d"),
    "ClosedDate": np.where(status == "Closed", closed.strftime("%Y-%m-%d"), ""),
    "ItemCode": [itm_of[s] for s in wo_sku],
    "TechnicianID": rng.choice([f"T-{i:02d}" for i in range(1, 26)], n_wo),
    "WorkType": rng.choice(["Repair", "Preventive Maintenance", "Installation"], n_wo, p=[.55, .3, .15]),
    "Status": status,
    "LaborHours": np.round(rng.gamma(2, 1.4, n_wo), 1),
})
wo.to_csv(f"{OUT}/ServiceWorkOrders.csv", index=False)

n_pu = 9000
pu_wo = rng.choice(wo.WorkOrderID, n_pu)
wo_item = dict(zip(wo.WorkOrderID, wo.ItemCode))
hyd_itm = [itm_of[s] for s in prod[prod.Category == "Hydraulics"].SKU]
pu_item = np.where(rng.random(n_pu) < 0.55, rng.choice(hyd_itm, n_pu),
                   [wo_item[w] for w in pu_wo])
pu = pd.DataFrame({
    "UsageID": [f"PU-{200001+i}" for i in range(n_pu)],
    "WorkOrderID": pu_wo,
    "ItemCode": pu_item,
    "QtyUsed": rng.integers(1, 5, n_pu),
    "UsageDate": pd.to_datetime(rng.choice(dates, n_pu)).strftime("%Y-%m-%d"),
})
pu.to_csv(f"{OUT}/ServicePartsUsage.csv", index=False)

# ================================================================ C. Helpdesk (camelCase)
hd_cat = pd.DataFrame({"categoryId": [1, 2, 3, 4, 5, 6],
    "categoryName": ["Product complaint", "How-to question", "Warranty claim",
                     "Shipping issue", "Billing inquiry", "Feature request"]})
hd_cat.to_csv(f"{OUT}/hdCategories.csv", index=False)

def misspell(name, r):
    w = list(name)
    i = int(r * (len(w) - 2)) + 1
    if r > 0.5 and i < len(w) - 1:
        w[i], w[i + 1] = w[i + 1], w[i]
    else:
        del w[i]
    return "".join(w)

n_t = 12000
base_w = np.full(len(prod), 1.0)
qmask = prod.SKU.isin(quality_skus).to_numpy()
base_w[qmask] = 28.0                       # quality SKUs: ~28x ticket weight
t_sku = rng.choice(prod.SKU, n_t, p=base_w / base_w.sum())
name_of = dict(zip(prod.SKU, prod.ProductName))
t_dt = pd.to_datetime(rng.choice(dates, n_t)) + pd.to_timedelta(rng.integers(8 * 3600, 19 * 3600, n_t), "s")
# quality SKUs: tickets skew to the last ~3.5 months
sel_q = np.where(pd.Series(t_sku).isin(quality_skus))[0]
t_dt = t_dt.to_numpy().copy()
t_dt[sel_q[: int(len(sel_q) * 0.6)]] = (pd.to_datetime(rng.choice(dates[-110:], int(len(sel_q) * 0.6)))
    + pd.to_timedelta(rng.integers(8 * 3600, 19 * 3600, int(len(sel_q) * 0.6)), "s")).to_numpy()
cat_p_norm = [.18, .30, .12, .18, .12, .10]
cat_p_qual = [.55, .10, .20, .07, .04, .04]
t_cat = np.where(pd.Series(t_sku).isin(quality_skus),
                 rng.choice([1, 2, 3, 4, 5, 6], n_t, p=cat_p_qual),
                 rng.choice([1, 2, 3, 4, 5, 6], n_t, p=cat_p_norm))
t_open = rng.random(n_t) < np.where(pd.Series(t_sku).isin(quality_skus), 0.35, 0.10)
t_created = pd.to_datetime(t_dt)
t_closed = t_created + pd.to_timedelta(rng.integers(1, 240, n_t), "h")
refs = []
for s in t_sku:
    r = rng.random()
    if r < 0.04: refs.append("")
    elif r < 0.12: refs.append(misspell(name_of[s], rng.random()))
    else: refs.append(name_of[s])
hd = pd.DataFrame({
    "ticketId": [f"HD-{i:05d}" for i in range(1, n_t + 1)],
    "createdAt": t_created.strftime("%Y-%m-%dT%H:%M:%S"),
    "closedAt": np.where(t_open, "", t_closed.strftime("%Y-%m-%dT%H:%M:%S")),
    "productRef": refs,
    "categoryId": t_cat,
    "priority": rng.choice(["low", "normal", "high", "urgent"], n_t, p=[.25, .5, .18, .07]),
    "status": np.where(t_open, "open", "closed"),
    "channel": rng.choice(["email", "phone", "web"], n_t, p=[.45, .25, .30]),
})
hd.to_csv(f"{OUT}/hdTickets.csv", index=False)

# ================================================================ D. MegaMart
mapped_skus = prod.SKU.sample(90, random_state=3).tolist()
dual = mapped_skus[:2]                                  # 2 SKUs with two listings
listings = []
lid = 200001
for s in mapped_skus:
    listings.append({"listingId": f"ML-{lid}", "sellerSku": s,
                     "title": name_of[s][:40] + " | Fast Ship", "listPrice":
                     round(float(prod.set_index('SKU').ListPrice[s]) * 1.08, 2), "status": "active"}); lid += 1
for s in dual:
    listings.append({"listingId": f"ML-{lid}", "sellerSku": s,
                     "title": name_of[s][:34] + " (2-PACK)", "listPrice":
                     round(float(prod.set_index('SKU').ListPrice[s]) * 2.05, 2), "status": "active"}); lid += 1
stale_skus = [f"SKU-{i}" for i in [990, 991, 992, 993]] + ["SK-77", "SK-78", "OLD-CARTON-XL", "SKU0042b", "SKU-0042-B", "TEST-DO-NOT-USE"]
for s in stale_skus:
    listings.append({"listingId": f"ML-{lid}", "sellerSku": s, "title": f"Clearance item {s}",
                     "listPrice": round(rng.uniform(5, 60), 2), "status": rng.choice(["inactive", "active"])}); lid += 1
mm_l = pd.DataFrame(listings)
mm_l.to_csv(f"{OUT}/mm_listings.csv", index=False)

n_mo = 25000
w = np.where(mm_l.status == "active", 1.0, 0.15)
o_listing = rng.choice(mm_l.listingId, n_mo, p=w / w.sum())
lp_of = dict(zip(mm_l.listingId, mm_l.listPrice))
o_qty = rng.integers(1, 5, n_mo)
o_gross = np.round([lp_of[l] for l in o_listing] * o_qty * rng.normal(1, 0.015, n_mo), 2)
o_date = pd.to_datetime(rng.choice(dates, n_mo))
mm_o = pd.DataFrame({"mmOrderId": [f"MM-{7000001+i}" for i in range(n_mo)],
    "orderDate": o_date.strftime("%Y-%m-%d"), "listingId": o_listing,
    "qty": o_qty, "grossAmount": o_gross,
    "buyerState": rng.choice(["NJ","CA","OH","TX","PA","IL","FL","NY","GA","WA"], n_mo)})
mm_o.to_csv(f"{OUT}/mm_orders.csv", index=False)

comm = np.round(o_gross * 0.12, 2)
ful = np.round(2.20 * o_qty + 1.50, 2)
mm_s = pd.DataFrame({"settlementId": [f"ST-{9000001+i}" for i in range(n_mo)],
    "mmOrderId": mm_o.mmOrderId,
    "settlementDate": (o_date + pd.Timedelta(days=14)).strftime("%Y-%m-%d"),
    "grossAmount": o_gross, "commissionFee": comm, "fulfillmentFee": ful,
    "payoutAmount": np.round(o_gross - comm - ful, 2)})
mm_s.to_csv(f"{OUT}/mm_settlements.csv", index=False)

# ================================================================ E. Lakeside (UPPERCASE, legacy)
ls_stores = pd.DataFrame({
    "STORE_CODE": ["LS01", "LS02", "LS03", "LS04"],
    "STORE_NAME": ["LAKESIDE SUPPLY ERIE", "LAKESIDE SUPPLY BUFFALO",
                   "LAKESIDE SUPPLY ROCHESTER", "LAKESIDE SUPPLY CLEVELAND"],
    "CITY": ["ERIE", "BUFFALO", "ROCHESTER", "CLEVELAND"],
    "STATE": ["PA", "NY", "NY", "OH"], "REGION": ["GREAT LAKES"] * 4,
    "SQFT": [12500, 18000, 15200, 21000]})
ls_stores.to_csv(f"{OUT}/LS_STORES.csv", index=False)

ls_mapped = prod.SKU.sample(50, random_state=5).tolist()
# make sure quality SKUs are sold at Lakeside too (merged-network story)
for s in quality_skus:
    if s not in ls_mapped: ls_mapped[-1 if ls_mapped[-1] not in quality_skus else -2] = s
ls_cat_map = {"Electrical": "ELEC", "Fasteners": "FAST", "Hydraulics": "HYDR",
              "Packaging": "PACK", "Safety": "SAFE"}
ls_rows = []
for i, s in enumerate(ls_mapped, 1):
    r = prod.set_index("SKU").loc[s]
    ls_rows.append({"LSP_CODE": f"LSP-{i:04d}", "PROD_DESC": r.ProductName.upper(),
                    "CATEGORY": ls_cat_map[r.Category],
                    "UNIT_PRICE": round(float(r.ListPrice) * rng.uniform(0.95, 1.12), 2)})
store_brand = ["LAKESIDE PRO SHOP TOWELS 12PK", "LAKESIDE WINTER SALT PELLETS 50LB",
    "LAKESIDE UTILITY KNIFE 3PK", "LAKESIDE STORM TARP 10X12FT", "LAKESIDE WORK GLOVES L",
    "LAKESIDE EXTENSION CORD 25FT", "LAKESIDE STORAGE TOTE 27GAL", "LAKESIDE BUNGEE SET 24PC",
    "LAKESIDE LED SHOP LIGHT 4FT", "LAKESIDE MOVING BLANKET"]
for j, nm in enumerate(store_brand, 51):
    ls_rows.append({"LSP_CODE": f"LSP-{j:04d}", "PROD_DESC": nm, "CATEGORY": "MISC",
                    "UNIT_PRICE": round(rng.uniform(8, 45), 2)})
ls_p = pd.DataFrame(ls_rows)
ls_p.to_csv(f"{OUT}/LS_PRODUCT_LIST.csv", index=False)

n_ls = 40000
lsp_w = np.concatenate([np.full(50, 1.0), np.full(10, 1.6)])    # store brand sells well
ls_pick = rng.choice(len(ls_p), n_ls, p=lsp_w / lsp_w.sum())
ls_date = pd.to_datetime(rng.choice(dates, n_ls))
ls_qty = rng.integers(1, 7, n_ls)
ls_up = ls_p.UNIT_PRICE.to_numpy()[ls_pick] * rng.normal(1, 0.01, n_ls)
ls_sales = pd.DataFrame({
    "SALE_ID": [f"LSS{i:07d}" for i in range(1, n_ls + 1)],
    "SALE_DATE": ls_date.strftime("%d/%m/%Y"),                  # TEXT DD/MM/YYYY trap
    "STORE_CODE": rng.choice(ls_stores.STORE_CODE, n_ls, p=[.2, .3, .22, .28]),
    "PROD_DESC": ls_p.PROD_DESC.to_numpy()[ls_pick],
    "QTY": ls_qty,
    "UNIT_PRICE": np.round(ls_up, 2),
    "TOTAL_AMT": np.round(ls_qty * ls_up, 2)})
ls_sales.to_csv(f"{OUT}/LS_SALES_EXPORT.csv", index=False)

sundays = pd.date_range("2025-06-01", "2026-05-31", freq="W-SUN")
sc = []
base_stock = rng.integers(8, 120, (4, len(ls_p)))
for wi, d in enumerate(sundays):
    drift = rng.integers(-12, 13, (4, len(ls_p)))
    base_stock = np.clip(base_stock + drift, 0, 200)
    for si, st in enumerate(ls_stores.STORE_CODE):
        for pi, lsp in enumerate(ls_p.LSP_CODE):
            sc.append((d.strftime("%d/%m/%Y"), st, lsp, base_stock[si, pi]))
ls_sc = pd.DataFrame(sc, columns=["COUNT_DATE", "STORE_CODE", "LSP_CODE", "QTY_ON_HAND"])
# planted risk SKUs: near-zero at all stores in the last 3 counts
q_lsp = ls_p[ls_p.PROD_DESC.isin([name_of[s].upper() for s in quality_skus])].LSP_CODE.tolist()
last3 = set(pd.Series(sundays[-3:]).dt.strftime("%d/%m/%Y"))
m = ls_sc.COUNT_DATE.isin(last3) & ls_sc.LSP_CODE.isin(q_lsp)
ls_sc.loc[m, "QTY_ON_HAND"] = rng.integers(0, 3, m.sum())
ls_sc.to_csv(f"{OUT}/LS_STOCK_COUNT.csv", index=False)

# ================================================================ F. sku_xref_master
lsp_of = {}
for i, s in enumerate(ls_mapped, 1): lsp_of[s] = f"LSP-{i:04d}"
listing_of = {}
for _, r in mm_l.iterrows():
    if r.sellerSku in name_of and r.sellerSku not in listing_of:
        listing_of[r.sellerSku] = r.listingId
xref = []
todo_lsps = list(lsp_of.items())[3:6]                      # 3 mappable LSPs left unmapped
todo_skus = [s for s, _ in todo_lsps]
for s in prod.SKU:
    xref.append({"sku": s, "itm_code": itm_of[s],
                 "lsp_code": "" if s in todo_skus else lsp_of.get(s, ""),
                 "mm_listing_id": listing_of.get(s, ""),
                 "last_verified": rng.choice(["2025-11-15", "2026-01-20", "2026-03-02"]),
                 "notes": "TODO confirm Lakeside code w/ Dana" if s in todo_skus else ""})
dual_l = mm_l[mm_l.sellerSku.isin(dual) & mm_l.title.str.contains("2-PACK")]
for _, r in dual_l.iterrows():                              # conflict: second row per dual SKU
    xref.append({"sku": r.sellerSku, "itm_code": itm_of[r.sellerSku],
                 "lsp_code": lsp_of.get(r.sellerSku, ""), "mm_listing_id": r.listingId,
                 "last_verified": "2026-02-10", "notes": "CONFLICT? two live listings"})
xref.append({"sku": "SKU-0999", "itm_code": "ITM-0999", "lsp_code": "LSP-0999",
             "mm_listing_id": "", "last_verified": "2024-09-01",
             "notes": "retired SKU - do not use"})
pd.DataFrame(xref).to_csv(f"{OUT}/sku_xref_master.csv", index=False)

for f in sorted(os.listdir(OUT)):
    df = pd.read_csv(f"{OUT}/{f}", dtype=str)
    print(f"{f:26s} rows={len(df):>7,}  cols={df.shape[1]}")
