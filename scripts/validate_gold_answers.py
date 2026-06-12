import pandas as pd, numpy as np
from pathlib import Path
D = str(Path(__file__).resolve().parent.parent / "data")
g = lambda f: pd.read_csv(f"{D}/{f}.csv")
prod, sol, inv = g("products"), g("sales_order_lines"), g("inventory_daily")
wo, pu, hd, hc = g("ServiceWorkOrders"), g("ServicePartsUsage"), g("hdTickets"), g("hdCategories")
mml, mmo, mms = g("mm_listings"), g("mm_orders"), g("mm_settlements")
lsp, lss, lsc, lst = g("LS_PRODUCT_LIST"), g("LS_SALES_EXPORT"), g("LS_STOCK_COUNT"), g("LS_STORES")
xref = g("sku_xref_master")

Q = ["SKU-0014", "SKU-0045"]
name_of = dict(zip(prod.sku, prod.product_name))

# ---- conformance (what the v2 notebook does)
xc = xref[(xref.sku != "SKU-0999") & (~xref.notes.fillna("").str.contains("CONFLICT"))]
lsp2sku = dict(zip(xc[xc.lsp_code.notna() & (xc.lsp_code != "")].lsp_code, xc[xc.lsp_code.notna() & (xc.lsp_code != "")].sku))
itm2sku = dict(zip(xc.itm_code, xc.sku))
listing2sku = dict(zip(mml.sellerSku.map(lambda s: s), mml.listingId))  # placeholder
l2s = {r.listingId: (r.sellerSku if r.sellerSku in name_of.values() or r.sellerSku in set(prod.sku) else None) for _, r in mml.iterrows()}

sol["rev"] = sol.qty_sold * sol.unit_price
sol["month"] = sol.date_key // 100
lss["dt"] = pd.to_datetime(lss.SALE_DATE, format="%d/%m/%Y")
lss["month"] = lss.dt.dt.year * 100 + lss.dt.dt.month
mmo["dt"] = pd.to_datetime(mmo.orderDate)
mmo["month"] = mmo.dt.dt.year * 100 + mmo.dt.dt.month
mm = mmo.merge(mms[["mmOrderId", "payoutAmount"]], on="mmOrderId")
mm["sku"] = mm.listingId.map(l2s)

print("=== GOLD ANSWERS (multi-source) ===\n")
print("Q1 [T1] ERP revenue Q1-2026 (Jan-Mar) by channel:")
q1 = sol[sol.month.isin([202601, 202602, 202603])].groupby("channel").rev.sum()
for c, v in q1.items(): print(f"   {c:10s} ${v/1e6:.3f}M")
print(f"   TOTAL      ${q1.sum()/1e6:.3f}M")

print("\nQ2 [T1] Top 5 products by ERP revenue (full window):")
t5 = sol.groupby("sku").rev.sum().nlargest(5)
for s, v in t5.items(): print(f"   {s} {name_of[s][:38]:40s} ${v/1e3:,.0f}K")

may_so = inv[inv.date_key // 100 == 202605]
print(f"\nQ3 [T1] ERP stockout rate May-2026: {may_so.is_stockout.mean():.2%} "
      f"(window avg {inv.is_stockout.mean():.2%}; was 0.02% in Option A)")

erp_may = sol[sol.month == 202605].rev.sum()
mm_may_net = mm[mm.month == 202605].payoutAmount.sum()
mm_may_gross = mm[mm.month == 202605].grossAmount.sum()
ls_may = lss[lss.month == 202605].TOTAL_AMT.sum()
print(f"\nQ4 [T2] Total company sales May-2026 (ERP + marketplace NET + Lakeside):")
print(f"   ERP ${erp_may/1e6:.3f}M + MM net ${mm_may_net/1e6:.3f}M + Lakeside ${ls_may/1e6:.3f}M"
      f" = ${(erp_may+mm_may_net+ls_may)/1e6:.3f}M")
print(f"   v1 traps: ERP-only ${erp_may/1e6:.3f}M; or with MM GROSS ${(erp_may+mm_may_gross)/1e6:.3f}M (no Lakeside — text dates)")

tot_g, tot_n = mm.grossAmount.sum(), mm.payoutAmount.sum()
print(f"\nQ5 [T2] Marketplace net revenue (full window): ${tot_n/1e6:.3f}M "
      f"(gross ${tot_g/1e6:.3f}M, fees {(tot_g-tot_n)/tot_g:.1%})")
for m_, v in mm.groupby("month").payoutAmount.sum().tail(3).items(): print(f"   {m_}: ${v/1e3:,.0f}K net")

# units sold company-wide per SKU (ERP + Lakeside mapped + MM mapped)
ls_join = lss.merge(lsp[["LSP_CODE", "PROD_DESC"]], on="PROD_DESC")
ls_join["sku"] = ls_join.LSP_CODE.map(lsp2sku)
units = pd.concat([sol.groupby("sku").qty_sold.sum(),
                   ls_join.dropna(subset=["sku"]).groupby("sku").QTY.sum(),
                   mm.dropna(subset=["sku"]).groupby("sku")["qty"].sum()], axis=1).fillna(0).sum(axis=1)
hd["ref_norm"] = hd.productRef.fillna("").str.strip().str.upper()
n2s = {v.upper(): k for k, v in name_of.items()}
hd["sku"] = hd.ref_norm.map(n2s)
res_rate = hd.sku.notna().mean()
tp = (hd.groupby("sku").size() / units * 1000).dropna().sort_values(ascending=False)
print(f"\nQ6 [T2] Helpdesk tickets per 1,000 units sold (resolved refs = {res_rate:.0%}): top 3")
for s, v in tp.head(3).items():
    print(f"   {s} {name_of[s][:36]:38s} {v:6.1f} t/1K  ({int(hd[hd.sku==s].shape[0]):,} tickets / {int(units[s]):,} units)")

hyd = set(prod[prod.category == "Hydraulics"].sku)
pu["sku"] = pu.ItemCode.map(itm2sku)
parts_h = pu[pu.sku.isin(hyd)].QtyUsed.sum()
units_h = units[units.index.isin(hyd)].sum()
print(f"\nQ7 [T2] Service parts attach, Hydraulics: {parts_h:,} parts / {int(units_h):,} units "
      f"= {parts_h/units_h*100:.1f} per 100 units sold")

# Q8 multi-hop
last_dk = inv.date_key.max()
erp_last = inv[inv.date_key == last_dk].groupby("sku").agg(oh=("on_hand_qty", "sum"), ss=("safety_stock", "sum"))
erp_risk = set(erp_last[erp_last.oh <= erp_last.ss].index)
lsc["dt"] = pd.to_datetime(lsc.COUNT_DATE, format="%d/%m/%Y")
last_cnt = lsc[lsc.dt == lsc.dt.max()].groupby("LSP_CODE").QTY_ON_HAND.sum()
ls_risk = {lsp2sku.get(k) for k, v in last_cnt.items() if v <= 4 and lsp2sku.get(k)}
open_compl = set(hd[(hd.status == "open") & (hd.categoryId == 1) & hd.sku.notna()].sku)
a_cls = set(prod[prod.abc_class == "A"].sku)
ans8 = sorted(a_cls & open_compl & (erp_risk | ls_risk))
print(f"\nQ8 [T3] A-class & open complaints & stockout risk (merged network): {ans8}")
for s in ans8:
    print(f"   {s} {name_of[s]} | open complaints {len(hd[(hd.sku==s)&(hd.status=='open')&(hd.categoryId==1)]):,} | "
          f"ERP OH/SS {int(erp_last.loc[s].oh)}/{int(erp_last.loc[s].ss)} | LS last counts "
          f"{[int(last_cnt.get(k,-1)) for k,v in lsp2sku.items() if v==s]}")

# Q9 sell-through since acquisition (Feb-May 2026)
acq = [202602, 202603, 202604, 202605]
ls_u = ls_join[ls_join.month.isin(acq)].QTY.sum()
ls_oh = lsc[lsc.dt >= "2026-02-01"].QTY_ON_HAND.mean() * len(lsp) * 4 / (len(lsp) * 4)
ls_avg_oh = lsc[lsc.dt >= "2026-02-01"].groupby("dt").QTY_ON_HAND.sum().mean()
erp_u = sol[sol.month.isin(acq)].qty_sold.sum()
erp_avg_oh = inv[inv.date_key >= 20260201].groupby("date_key").on_hand_qty.sum().mean()
print(f"\nQ9 [T3] Sell-through since acquisition (units sold ÷ avg on-hand, Feb–May 2026):")
print(f"   Lakeside stores: {ls_u:,} / {ls_avg_oh:,.0f} = {ls_u/ls_avg_oh:.2f}x")
print(f"   Our DCs:         {erp_u:,} / {erp_avg_oh:,.0f} = {erp_u/erp_avg_oh:.2f}x")

d_trap = lss[lss.SALE_DATE == "03/02/2026"].TOTAL_AMT.sum()
d_wrong = lss[lss.SALE_DATE == "02/03/2026"].TOTAL_AMT.sum()
print(f"\nQ10 [T3] Lakeside sales on 03/02/2026 (= Feb 3): ${d_trap:,.0f} "
      f"(MM/DD misparse would give Mar 2 = ${d_wrong:,.0f})")

ls_since = lss[lss.dt >= "2026-02-01"].TOTAL_AMT.sum()
sb = lsp[lsp.CATEGORY == "MISC"].PROD_DESC
sb_share = lss[lss.dt >= "2026-02-01"].merge(lsp, on="PROD_DESC").query("CATEGORY=='MISC'").TOTAL_AMT.sum()
print(f"\nQ11 [T2] Lakeside revenue since acquisition (Feb 1, 2026): ${ls_since/1e6:.3f}M "
      f"(store-brand items: {sb_share/ls_since:.0%})")

stale = mm.sku.isna()
print(f"\nQ12 [T3] Marketplace revenue not mappable to a product (stale listings): "
      f"${mm[stale].grossAmount.sum()/1e3:,.0f}K gross = {mm[stale].grossAmount.sum()/tot_g:.1%} of gross")

print(f"\n--- conformance stats: LS rows mapped to SKU {ls_join.sku.notna().mean():.0%}, "
      f"ticket refs resolved {res_rate:.0%}, listings mapped {pd.Series([v is not None for v in l2s.values()]).mean():.0%}")
