#!/usr/bin/env python3
"""Generate PBIR pages + visuals for the RAW and MODELED eval reports.

One page per eval question (12 each). The MODELED report answers each question
with the governed measures; the RAW report follows the honest-demo philosophy:
it shows the raw reality (partial numbers, disconnected tables, the planted
traps) and adds only two minimal report-level measures.

Author-only: no Power BI Desktop validation. Grammar verified against the
microsoft/json-schemas PBIR schemas (visualContainer 2.9.0, visualConfiguration
2.3.0, semanticQuery 1.4.0, filterConfiguration 1.2.0, reportExtension 1.0.0).
Idempotent: rerunning regenerates every page folder from scratch.
"""
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))

VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
EXT = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/reportExtension/1.0.0/schema.json"

# ----------------------------------------------------------------------------
# low-level field / projection / filter helpers
# ----------------------------------------------------------------------------

def field(entity, prop, measure=False):
    kind = "Measure" if measure else "Column"
    return {kind: {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def proj(entity, prop, measure=False):
    return {"field": field(entity, prop, measure),
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


def f_cat(name, entity, col, literal):
    """Categorical equality filter (col == literal)."""
    return {
        "name": name,
        "field": field(entity, col),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "f", "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": col}}],
                "Values": [[{"Literal": {"Value": literal}}]],
            }}}],
        },
    }


def f_range(name, entity, col, lo, hi):
    """Advanced between filter (lo <= col <= hi), integer/string literals."""
    cexpr = {"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": col}}
    return {
        "name": name,
        "field": field(entity, col),
        "type": "Advanced",
        "filter": {
            "Version": 2,
            "From": [{"Name": "f", "Entity": entity, "Type": 0}],
            "Where": [
                {"Condition": {"Comparison": {"ComparisonKind": 2, "Left": cexpr, "Right": {"Literal": {"Value": lo}}}}},
                {"Condition": {"Comparison": {"ComparisonKind": 4, "Left": cexpr, "Right": {"Literal": {"Value": hi}}}}},
            ],
        },
    }


def sort_desc(entity, prop, measure=True):
    return {"sortDefinition": {"sort": [{"field": field(entity, prop, measure), "direction": "Descending"}]}}


def sort_asc(entity, prop, measure=False):
    return {"sortDefinition": {"sort": [{"field": field(entity, prop, measure), "direction": "Ascending"}]}}


# ----------------------------------------------------------------------------
# visual builders -> (name, dict)
# ----------------------------------------------------------------------------

def textbox(name, x, y, w, h, lines):
    paragraphs = []
    for i, ln in enumerate(lines):
        size = 16 if i == 0 else 11
        bold = i == 0
        paragraphs.append({"textRuns": [{"value": ln, "textStyle": {
            "fontSize": f"{size}pt", **({"fontWeight": "bold"} if bold else {})}}]})
    return name, {
        "$schema": VC,
        "name": name,
        "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0},
        "visual": {"visualType": "textbox", "objects": {"general": [
            {"properties": {"paragraphs": paragraphs}}]}, "drillFilterOtherVisuals": True},
    }


def _visual(name, vtype, x, y, w, h, query, filters=None):
    v = {"visualType": vtype, "query": query, "drillFilterOtherVisuals": True}
    out = {
        "$schema": VC,
        "name": name,
        "position": {"x": x, "y": y, "z": 1000, "width": w, "height": h, "tabOrder": 0},
        "visual": v,
    }
    if filters:
        out["filterConfig"] = {"filters": filters}
    return name, out


def column_chart(name, x, y, w, h, cat, y_proj, filters=None, sort=None):
    query = {"queryState": {
        "Category": {"projections": [cat]},
        "Y": {"projections": [y_proj]},
    }}
    if sort:
        query.update(sort)
    return _visual(name, "clusteredColumnChart", x, y, w, h, query, filters)


def table(name, x, y, w, h, projections, filters=None, sort=None):
    query = {"queryState": {"Values": {"projections": projections}}}
    if sort:
        query.update(sort)
    return _visual(name, "tableEx", x, y, w, h, query, filters)


def card(name, x, y, w, h, data_proj, filters=None):
    query = {"queryState": {"Data": {"projections": [data_proj]}}}
    return _visual(name, "cardVisual", x, y, w, h, query, filters)


# ----------------------------------------------------------------------------
# page writer
# ----------------------------------------------------------------------------

def write_page(report_dir, page_id, display_name, visuals):
    pdir = os.path.join(report_dir, "definition", "pages", page_id)
    vdir = os.path.join(pdir, "visuals")
    if os.path.isdir(pdir):
        # wipe visuals but keep folder; rewrite page.json
        if os.path.isdir(vdir):
            shutil.rmtree(vdir)
    os.makedirs(vdir, exist_ok=True)
    with open(os.path.join(pdir, "page.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"$schema": PAGE, "name": page_id, "displayName": display_name,
                   "displayOption": "FitToPage", "height": 720, "width": 1280}, fh, indent=2)
    for vname, vobj in visuals:
        vsub = os.path.join(vdir, vname)
        os.makedirs(vsub, exist_ok=True)
        with open(os.path.join(vsub, "visual.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(vobj, fh, indent=2)


def write_pages_json(report_dir, order, active):
    p = os.path.join(report_dir, "definition", "pages", "pages.json")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"$schema": PAGES, "pageOrder": order, "activePageName": active}, fh, indent=2)


def clean_old_pages(report_dir, keep):
    """Remove page folders not in `keep` so reruns don't leave stale pages."""
    base = os.path.join(report_dir, "definition", "pages")
    if not os.path.isdir(base):
        return
    for entry in os.listdir(base):
        full = os.path.join(base, entry)
        if os.path.isdir(full) and entry not in keep:
            shutil.rmtree(full)


# ============================================================================
# MODELED report
# ============================================================================
MODELED = os.path.join(HERE, "modeled", "report_modeled.pbix.Report")
MQ1 = "9395695480646891e085"  # existing page folder, reuse for Q1

SU = "c_fact_sales_unified"   # all measures live here


def build_modeled():
    pages = []  # (page_id, display, visuals)

    def title(pid, n, q, gold):
        return textbox(f"m{pid}t", 16, 16, 1248, 56,
                       [f"Q{n} — {q}", f"Gold: {gold}"])

    # Q1
    pages.append((MQ1, "Q1 — Revenue by channel", [
        title(MQ1, 1, "Revenue in Q1 2026 by channel", "Online $7.030M / Retail $7.156M / Wholesale $6.911M"),
        column_chart(f"m{MQ1}v", 16, 88, 1248, 560,
                     proj("c_dim_channel", "channel"), proj(SU, "Revenue Net", True),
                     filters=[f_cat("mq1y", "c_dim_date", "year", "2026L"),
                              f_cat("mq1q", "c_dim_date", "quarter", "1L")],
                     sort=sort_desc(SU, "Revenue Net")),
    ]))

    def P(n):
        return f"m{n:02d}pageeval0000000000"[:20]

    # Q2
    p = P(2)
    pages.append((p, "Q2 — Top 5 products by revenue", [
        title(p, 2, "Top 5 products by revenue", "SKU-0074, 0094, 0014, 0079, 0080 (read top 5 rows)"),
        table(f"m{p}v", 16, 88, 900, 560,
              [proj("c_dim_product", "sku"), proj("c_dim_product", "product_name"),
               proj(SU, "Revenue Net", True)],
              sort=sort_desc(SU, "Revenue Net")),
    ]))

    # Q3
    p = P(3)
    pages.append((p, "Q3 — Stockout rate May 2026", [
        title(p, 3, "Stockout rate in May 2026", "1.52% of SKU-location-days"),
        card(f"m{p}v", 16, 88, 360, 200, proj(SU, "Stockout Rate %", True),
             filters=[f_cat("mq3y", "c_dim_date", "year", "2026L"),
                      f_cat("mq3m", "c_dim_date", "month", "5L")]),
    ]))

    # Q4 — four cards
    p = P(4)
    f4 = [f_cat("mq4y", "c_dim_date", "year", "2026L"), f_cat("mq4m", "c_dim_date", "month", "5L")]
    pages.append((p, "Q4 — Total company sales May 2026", [
        title(p, 4, "Total company sales May 2026 incl. Lakeside + marketplace",
              "$10.054M = ERP $8.382M + MM net $0.622M + Lakeside $1.051M"),
        card(f"m{p}a", 16, 88, 300, 200, proj(SU, "ERP Revenue", True), filters=f4),
        card(f"m{p}b", 328, 88, 300, 200, proj(SU, "Marketplace Net Revenue", True), filters=f4),
        card(f"m{p}c", 640, 88, 300, 200, proj(SU, "Lakeside Revenue", True), filters=f4),
        card(f"m{p}d", 952, 88, 300, 200, proj(SU, "Revenue Net", True), filters=f4),
    ]))

    # Q5
    p = P(5)
    pages.append((p, "Q5 — Net marketplace revenue by month", [
        title(p, 5, "Net marketplace revenue after fees, by month", "$7.335M net for the window (gross $8.534M, 14% fees)"),
        column_chart(f"m{p}v", 16, 88, 1248, 560,
                     proj("c_dim_date", "month"), proj(SU, "Marketplace Net Revenue", True),
                     sort=sort_asc("c_dim_date", "month")),
    ]))

    # Q6
    p = P(6)
    pages.append((p, "Q6 — Tickets per 1K units", [
        title(p, 6, "Products with most helpdesk tickets per 1,000 units sold", "SKU-0045, SKU-0014 (read top rows)"),
        table(f"m{p}v", 16, 88, 1100, 560,
              [proj("c_dim_product", "sku"), proj("c_dim_product", "product_name"),
               proj(SU, "Tickets per 1K Units", True), proj(SU, "Units Sold", True),
               proj(SU, "Tickets", True)],
              sort=sort_desc(SU, "Tickets per 1K Units")),
    ]))

    # Q7
    p = P(7)
    pages.append((p, "Q7 — Parts attach rate Hydraulics", [
        title(p, 7, "Service parts attach rate for Hydraulics products", "8.1 parts per 100 units"),
        card(f"m{p}v", 16, 88, 360, 200, proj(SU, "Parts per 100 Units", True),
             filters=[f_cat("mq7c", "c_dim_product", "category", "'Hydraulics'")]),
    ]))

    # Q8
    p = P(8)
    pages.append((p, "Q8 — A-class open complaints + stockout", [
        title(p, 8, "A-class products with open complaints AND stockout risk", "SKU-0014, SKU-0045 (top rows: complaints>0, low on-hand)"),
        table(f"m{p}v", 16, 88, 1100, 560,
              [proj("c_dim_product", "sku"), proj("c_dim_product", "product_name"),
               proj(SU, "Open Complaints", True), proj(SU, "Avg On-Hand Units", True)],
              filters=[f_cat("mq8a", "c_dim_product", "abc_class", "'A'")],
              sort=sort_desc(SU, "Open Complaints")),
    ]))

    # Q9
    p = P(9)
    pages.append((p, "Q9 — Lakeside vs DC sell-through", [
        title(p, 9, "Lakeside store sell-through vs DCs since acquisition", "Lakeside 2.85x vs DCs 1.70x"),
        column_chart(f"m{p}v", 16, 88, 1248, 560,
                     proj("c_dim_location", "location_type"), proj(SU, "Sell-Through Ratio", True),
                     filters=[f_cat("mq9p", "c_dim_date", "is_post_acquisition", "true")],
                     sort=sort_desc(SU, "Sell-Through Ratio")),
    ]))

    # Q10
    p = P(10)
    pages.append((p, "Q10 — Lakeside sales 03/02/2026", [
        title(p, 10, "Lakeside sales on 03/02/2026 (DD/MM/YYYY = 3 Feb)", "$36,836"),
        card(f"m{p}v", 16, 88, 360, 200, proj(SU, "Lakeside Revenue", True),
             filters=[f_cat("mq10d", "c_dim_date", "date_key", "20260203L")]),
    ]))

    # Q11
    p = P(11)
    pages.append((p, "Q11 — Lakeside revenue since acquisition", [
        title(p, 11, "Lakeside revenue since the acquisition (from 2026-02-01)", "$4.324M"),
        card(f"m{p}v", 16, 88, 360, 200, proj(SU, "Lakeside Revenue", True),
             filters=[f_cat("mq11p", "c_dim_date", "is_post_acquisition", "true")]),
    ]))

    # Q12
    p = P(12)
    pages.append((p, "Q12 — Marketplace revenue not tied to a product", [
        title(p, 12, "Marketplace revenue not tied to one of our products", "~$94K gross (orphan listings; here the UNMAPPED member)"),
        card(f"m{p}v", 16, 88, 360, 200, proj(SU, "Marketplace Gross Revenue", True),
             filters=[f_cat("mq12u", "c_dim_product", "sku", "'UNMAPPED'")]),
    ]))

    order = [pid for pid, _, _ in pages]
    clean_old_pages(MODELED, set(order))
    for pid, disp, vis in pages:
        write_page(MODELED, pid, disp, vis)
    write_pages_json(MODELED, order, order[0])
    return order


# ============================================================================
# RAW report — honest demo
# ============================================================================
RAW = os.path.join(HERE, "raw", "report_raw.Report")
RQ1 = "45dc5d48eca9b4541c4d"  # existing page folder, reuse for Q1


def remove_raw_extensions():
    """Honest-demo raw report uses no report-level measures (implicit
    aggregations only), so make sure no stale extension file is left behind."""
    p = os.path.join(RAW, "definition", "reportExtensions.json")
    if os.path.exists(p):
        os.remove(p)


def build_raw():
    pages = []

    def title(pid, n, q, note):
        return textbox(f"r{pid}t", 16, 16, 1248, 72,
                       [f"Q{n} — {q}", f"RAW reality: {note}"])

    def P(n):
        return f"r{n:02d}pageeval0000000000"[:20]

    # Q1 — ERP channels only; no revenue column exists in raw
    pages.append((RQ1, "Q1 — Revenue by channel (RAW)", [
        title(RQ1, 1, "Revenue in Q1 2026 by channel",
              "Raw ERP has NO revenue column (revenue = qty x price needs DAX the raw model lacks); chart shows UNITS by channel. ERP channels only - Lakeside & marketplace missing. No date dim -> hand-filter integer date_key 20260101-20260331."),
        column_chart(f"r{RQ1}v", 16, 100, 1248, 540,
                     proj("sales_order_lines", "channel"), proj("sales_order_lines", "qty_sold"),
                     filters=[f_range("rq1d", "sales_order_lines", "date_key", "20260101L", "20260331L")],
                     sort=sort_desc("sales_order_lines", "qty_sold", measure=False)),
    ]))

    # Q2 — rank by units (no revenue column)
    p = P(2)
    pages.append((p, "Q2 — Top products (RAW)", [
        title(p, 2, "Top 5 products by revenue",
              "No revenue column -> table ranks by UNITS sold (Sum qty_sold), not revenue. ERP sales only (sku->products join exists); excludes Lakeside & marketplace, so ranking can differ from gold."),
        table(f"r{p}v", 16, 100, 900, 540,
              [proj("sales_order_lines", "sku"), proj("products", "product_name"),
               proj("sales_order_lines", "qty_sold")],
              sort=sort_desc("sales_order_lines", "qty_sold", measure=False)),
    ]))

    # Q3 — stockout numerator only
    p = P(3)
    pages.append((p, "Q3 — Stockout rate (RAW)", [
        title(p, 3, "Stockout rate in May 2026",
              "is_stockout flag exists but there is NO rate measure. Card shows SUM(is_stockout)=stockout-day count; denominator/rate must be computed by hand."),
        card(f"r{p}v", 16, 100, 360, 200, proj("inventory_daily", "is_stockout"),
             filters=[f_range("rq3d", "inventory_daily", "date_key", "20260501L", "20260531L")]),
    ]))

    # Q4 — three disconnected numbers
    p = P(4)
    pages.append((p, "Q4 — Total company sales (RAW)", [
        title(p, 4, "Total company sales May 2026 incl. Lakeside + marketplace",
              "THE money trap: 3 disconnected tables, 3 incompatible shapes, no common key. ERP has no sales-amount column at all (card A shows UNITS); marketplace (gross $) and Lakeside (total $) each have their own amount column but cannot be date-filtered to May or summed together in one visual."),
        card(f"r{p}a", 16, 100, 405, 200, proj("sales_order_lines", "qty_sold"),
             filters=[f_range("rq4d", "sales_order_lines", "date_key", "20260501L", "20260531L")]),
        card(f"r{p}b", 437, 100, 405, 200, proj("mm_orders", "grossAmount")),
        card(f"r{p}c", 858, 100, 405, 200, proj("LS_SALES_EXPORT", "TOTAL_AMT")),
    ]))

    # Q5 — settlement totals, no month bucket
    p = P(5)
    pages.append((p, "Q5 — Net marketplace by month (RAW)", [
        title(p, 5, "Net marketplace revenue after fees, by month",
              "Gross & fees live on mm_settlements, but there is no date dim and mm_orders.orderDate is TEXT in a separate, unrelated table -> cannot bucket by month. Window totals only."),
        table(f"r{p}v", 16, 100, 900, 300,
              [proj("mm_settlements", "grossAmount"), proj("mm_settlements", "commissionFee"),
               proj("mm_settlements", "fulfillmentFee"), proj("mm_settlements", "payoutAmount")]),
    ]))

    # Q6 — two disconnected tables
    p = P(6)
    pages.append((p, "Q6 — Tickets per 1K units (RAW)", [
        title(p, 6, "Products with most helpdesk tickets per 1,000 units sold",
              "hdTickets.productRef is FREE-TEXT with no relationship to products.sku -> the two tables below cannot be joined; tickets-per-1K-units is impossible."),
        table(f"r{p}a", 16, 100, 616, 540,
              [proj("hdTickets", "ticketId"), proj("hdTickets", "productRef"),
               proj("hdTickets", "status")]),
        table(f"r{p}b", 648, 100, 616, 540,
              [proj("sales_order_lines", "sku"), proj("products", "product_name"),
               proj("sales_order_lines", "qty_sold")],
              sort=sort_desc("sales_order_lines", "qty_sold", measure=False)),
    ]))

    # Q7
    p = P(7)
    pages.append((p, "Q7 — Parts attach rate Hydraulics (RAW)", [
        title(p, 7, "Service parts attach rate for Hydraulics products",
              "ServiceWorkOrders/ServicePartsUsage use ITM- codes, not SKUs; mapping only via sku_xref_master and there are NO relationships -> category 'Hydraulics' (in products) is unreachable."),
        table(f"r{p}a", 16, 100, 616, 540,
              [proj("ServicePartsUsage", "ItemCode"), proj("ServicePartsUsage", "QtyUsed")],
              sort=sort_desc("ServicePartsUsage", "QtyUsed", measure=False)),
        table(f"r{p}b", 648, 100, 616, 540,
              [proj("ServiceWorkOrders", "WorkOrderID"), proj("ServiceWorkOrders", "ItemCode"),
               proj("ServiceWorkOrders", "WorkType"), proj("ServiceWorkOrders", "Status")]),
    ]))

    # Q8 — three disjoint lists
    p = P(8)
    pages.append((p, "Q8 — A-class open complaints + stockout (RAW)", [
        title(p, 8, "A-class products with open complaints AND stockout risk",
              "Three-way intersection impossible: helpdesk (free-text productRef), ABC class (products) and stockout (inventory_daily) share no usable join. Three disjoint lists below."),
        table(f"r{p}a", 16, 100, 405, 540,
              [proj("products", "sku"), proj("products", "product_name"), proj("products", "abc_class")],
              filters=[f_cat("rq8a", "products", "abc_class", "'A'")]),
        table(f"r{p}b", 437, 100, 405, 540,
              [proj("hdTickets", "ticketId"), proj("hdTickets", "productRef"), proj("hdTickets", "status")],
              filters=[f_cat("rq8s", "hdTickets", "status", "'open'")]),
        table(f"r{p}c", 858, 100, 405, 540,
              [proj("inventory_daily", "sku"), proj("inventory_daily", "location_id"),
               proj("inventory_daily", "is_stockout")],
              filters=[f_cat("rq8k", "inventory_daily", "is_stockout", "1L")]),
    ]))

    # Q9 — Lakeside vs DC, isolated
    p = P(9)
    pages.append((p, "Q9 — Lakeside vs DC sell-through (RAW)", [
        title(p, 9, "Lakeside store sell-through vs DCs since acquisition",
              "Lakeside (LS_* tables) is fully isolated with TEXT DD/MM/YYYY dates and no relationships; 'since acquisition' needs date parsing raw cannot do, and sell-through needs a sales/inventory join that is absent."),
        table(f"r{p}a", 16, 100, 616, 540,
              [proj("LS_SALES_EXPORT", "STORE_CODE"), proj("LS_SALES_EXPORT", "QTY"),
               proj("LS_SALES_EXPORT", "TOTAL_AMT")]),
        table(f"r{p}b", 648, 100, 616, 540,
              [proj("sales_order_lines", "location_id"), proj("sales_order_lines", "qty_sold")]),
    ]))

    # Q10 — date format trap (text equality works)
    p = P(10)
    pages.append((p, "Q10 — Lakeside sales 03/02/2026 (RAW)", [
        title(p, 10, "Lakeside sales on 03/02/2026",
              "SALE_DATE is TEXT DD/MM/YYYY. Text-equality on '03/02/2026' returns 3 Feb ($36,836) only if you KNOW the format; a US MM/DD reading would query the wrong day."),
        table(f"r{p}v", 16, 100, 800, 300,
              [proj("LS_SALES_EXPORT", "SALE_DATE"), proj("LS_SALES_EXPORT", "STORE_CODE"),
               proj("LS_SALES_EXPORT", "TOTAL_AMT")],
              filters=[f_cat("rq10d", "LS_SALES_EXPORT", "SALE_DATE", "'03/02/2026'")]),
    ]))

    # Q11 — no reliable date range on text dates
    p = P(11)
    pages.append((p, "Q11 — Lakeside revenue since acquisition (RAW)", [
        title(p, 11, "Lakeside revenue since the acquisition (from 2026-02-01)",
              "Can SUM TOTAL_AMT but cannot apply a correct date range on a TEXT DD/MM/YYYY column (string order != chronological). Card shows the WHOLE-window total, not the $4.324M since-acquisition figure."),
        card(f"r{p}v", 16, 100, 360, 200, proj("LS_SALES_EXPORT", "TOTAL_AMT")),
    ]))

    # Q12 — no referential integrity
    p = P(12)
    pages.append((p, "Q12 — Marketplace revenue not tied to a product (RAW)", [
        title(p, 12, "Marketplace revenue not tied to one of our products",
              "mm_listings maps listingId->sellerSku, but unmatched/orphan listings need an anti-join raw has no relationship for. Compare the two tables by hand; the ~$94K orphan gross is not isolable in a visual."),
        table(f"r{p}a", 16, 100, 616, 540,
              [proj("mm_orders", "mmOrderId"), proj("mm_orders", "listingId"),
               proj("mm_orders", "grossAmount")]),
        table(f"r{p}b", 648, 100, 616, 540,
              [proj("mm_listings", "listingId"), proj("mm_listings", "sellerSku"),
               proj("mm_listings", "status")]),
    ]))

    remove_raw_extensions()
    order = [pid for pid, _, _ in pages]
    clean_old_pages(RAW, set(order))
    for pid, disp, vis in pages:
        write_page(RAW, pid, disp, vis)
    write_pages_json(RAW, order, order[0])
    return order


# ============================================================================
# RAW_PLUS report — instructed raw: force an answer on every page using heavy
# report-level DAX (the report analog of the Raw_Plus agent's instructions).
# Connects to the SAME raw model; re-derives cross-source joins, parses text
# dates, and looks up the xref entirely in the report layer. Like the Raw_Plus
# agent (~9/24), several answers are approximate/wrong because the raw schema
# fights back (free-text helpdesk refs, mixed-grain inventory) — that is the point.
# ============================================================================
RAWPLUS = os.path.join(HERE, "raw_plus", "report_raw_plus.Report")
RP_LOGICAL_ID = "f7e6d5c4-b3a2-4190-8e7f-0a1b2c3d4e5f"
RP_HOME = "sales_order_lines"  # home table for all RP report-level measures

# DAX re-derivations. Dates: marketplace = ISO 'YYYY-MM-DD'; Lakeside SALE_DATE =
# text 'DD/MM/YYYY'. Helpdesk productRef is free text (exact-name match only).
RP_MEASURES = [
    ("RP Revenue",
     "SUMX(sales_order_lines, sales_order_lines[qty_sold] * sales_order_lines[unit_price])", "#,##0"),
    ("RP Stockout Rate",
     "DIVIDE(CALCULATE(COUNTROWS(inventory_daily), inventory_daily[is_stockout] = 1), COUNTROWS(inventory_daily))", "0.0%"),
    ("RP Marketplace Net",
     "SUM(mm_settlements[payoutAmount])", "#,##0"),
    ("RP ERP May",
     "CALCULATE(SUMX(sales_order_lines, sales_order_lines[qty_sold] * sales_order_lines[unit_price]), "
     "sales_order_lines[date_key] >= 20260501, sales_order_lines[date_key] <= 20260531)", "#,##0"),
    ("RP MM Net May",
     "SUMX(FILTER(mm_settlements, VALUE(LEFT(mm_settlements[settlementDate],4)) = 2026 "
     "&& VALUE(MID(mm_settlements[settlementDate],6,2)) = 5), mm_settlements[payoutAmount])", "#,##0"),
    ("RP LS May",
     "SUMX(FILTER(LS_SALES_EXPORT, VALUE(RIGHT(LS_SALES_EXPORT[SALE_DATE],4)) = 2026 "
     "&& VALUE(MID(LS_SALES_EXPORT[SALE_DATE],4,2)) = 5), LS_SALES_EXPORT[TOTAL_AMT])", "#,##0"),
    ("RP Total May",
     "VAR erp = CALCULATE(SUMX(sales_order_lines, sales_order_lines[qty_sold] * sales_order_lines[unit_price]), "
     "sales_order_lines[date_key] >= 20260501, sales_order_lines[date_key] <= 20260531) "
     "VAR mm = SUMX(FILTER(mm_settlements, VALUE(LEFT(mm_settlements[settlementDate],4)) = 2026 "
     "&& VALUE(MID(mm_settlements[settlementDate],6,2)) = 5), mm_settlements[payoutAmount]) "
     "VAR ls = SUMX(FILTER(LS_SALES_EXPORT, VALUE(RIGHT(LS_SALES_EXPORT[SALE_DATE],4)) = 2026 "
     "&& VALUE(MID(LS_SALES_EXPORT[SALE_DATE],4,2)) = 5), LS_SALES_EXPORT[TOTAL_AMT]) "
     "RETURN erp + mm + ls", "#,##0"),
    ("RP Tickets Exact",
     "VAR pn = SELECTEDVALUE(products[product_name]) "
     "RETURN COUNTROWS(FILTER(hdTickets, hdTickets[productRef] = pn))", "0"),
    ("RP Units",
     "SUM(sales_order_lines[qty_sold])", "#,##0"),
    ("RP Tickets per 1K",
     "VAR pn = SELECTEDVALUE(products[product_name]) "
     "VAR t = COUNTROWS(FILTER(hdTickets, hdTickets[productRef] = pn)) "
     "RETURN DIVIDE(t, SUM(sales_order_lines[qty_sold])) * 1000", "0.0"),
    ("RP Parts per 100 Hydraulics",
     "VAR parts = SUMX(FILTER(ServicePartsUsage, "
     "VAR s = LOOKUPVALUE(sku_xref_master[sku], sku_xref_master[itm_code], ServicePartsUsage[ItemCode]) "
     "RETURN NOT ISBLANK(s) && LOOKUPVALUE(products[category], products[sku], s) = \"Hydraulics\"), "
     "ServicePartsUsage[QtyUsed]) "
     "VAR units = CALCULATE(SUM(sales_order_lines[qty_sold]), products[category] = \"Hydraulics\") "
     "RETURN DIVIDE(parts, units) * 100", "0.0"),
    ("RP Open Complaints Exact",
     "VAR pn = SELECTEDVALUE(products[product_name]) "
     "RETURN COUNTROWS(FILTER(hdTickets, hdTickets[productRef] = pn "
     "&& hdTickets[categoryId] = 1 && hdTickets[status] = \"open\"))", "0"),
    ("RP At Stockout Risk",
     "VAR latest = CALCULATE(MAX(inventory_daily[date_key]), ALL(inventory_daily)) "
     "VAR oh = CALCULATE(SUM(inventory_daily[on_hand_qty]), inventory_daily[date_key] = latest) "
     "VAR ss = CALCULATE(SUM(inventory_daily[safety_stock]), inventory_daily[date_key] = latest) "
     "RETURN IF(oh <= ss, 1, 0)", "0"),
    ("RP Lakeside Sell-Through",
     "VAR u = SUMX(FILTER(LS_SALES_EXPORT, (VALUE(RIGHT(LS_SALES_EXPORT[SALE_DATE],4)) * 10000 "
     "+ VALUE(MID(LS_SALES_EXPORT[SALE_DATE],4,2)) * 100 + VALUE(LEFT(LS_SALES_EXPORT[SALE_DATE],2))) >= 20260201), "
     "LS_SALES_EXPORT[QTY]) VAR inv = AVERAGE(LS_STOCK_COUNT[QTY_ON_HAND]) RETURN DIVIDE(u, inv)", "0.00"),
    ("RP DC Sell-Through",
     "VAR u = CALCULATE(SUM(sales_order_lines[qty_sold]), sales_order_lines[date_key] >= 20260201) "
     "VAR inv = CALCULATE(AVERAGE(inventory_daily[on_hand_qty]), inventory_daily[date_key] >= 20260201) "
     "RETURN DIVIDE(u, inv)", "0.00"),
    ("RP Lakeside Sales 03Feb",
     "SUMX(FILTER(LS_SALES_EXPORT, LS_SALES_EXPORT[SALE_DATE] = \"03/02/2026\"), LS_SALES_EXPORT[TOTAL_AMT])", "#,##0"),
    ("RP Lakeside Since Acq",
     "SUMX(FILTER(LS_SALES_EXPORT, (VALUE(RIGHT(LS_SALES_EXPORT[SALE_DATE],4)) * 10000 "
     "+ VALUE(MID(LS_SALES_EXPORT[SALE_DATE],4,2)) * 100 + VALUE(LEFT(LS_SALES_EXPORT[SALE_DATE],2))) >= 20260201), "
     "LS_SALES_EXPORT[TOTAL_AMT])", "#,##0"),
    ("RP Unmatched MM Gross",
     "SUMX(mm_orders, VAR lid = mm_orders[listingId] "
     "VAR cnt = CALCULATE(COUNTROWS(sku_xref_master), sku_xref_master[mm_listing_id] = lid) "
     "RETURN IF(cnt = 0, mm_orders[grossAmount], 0))", "#,##0"),
]


def _copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)


def rp_scaffold():
    """Create the raw_plus PBIP shell from the raw report's scaffolding,
    bound to the SAME MultiSource_Raw model (definition.pbir copied verbatim)."""
    # connection + theme + report/version metadata copied from the raw report
    _copy(os.path.join(RAW, "definition.pbir"), os.path.join(RAWPLUS, "definition.pbir"))
    _copy(os.path.join(RAW, "definition", "report.json"), os.path.join(RAWPLUS, "definition", "report.json"))
    _copy(os.path.join(RAW, "definition", "version.json"), os.path.join(RAWPLUS, "definition", "version.json"))
    _copy(os.path.join(RAW, "StaticResources", "SharedResources", "BaseThemes", "CY26SU05.json"),
          os.path.join(RAWPLUS, "StaticResources", "SharedResources", "BaseThemes", "CY26SU05.json"))
    # .platform with its own displayName + logicalId
    with open(os.path.join(RAW, ".platform"), encoding="utf-8") as fh:
        plat = json.load(fh)
    plat["metadata"]["displayName"] = "report_raw_plus"
    plat["config"]["logicalId"] = RP_LOGICAL_ID
    with open(os.path.join(RAWPLUS, ".platform"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(plat, fh, indent=2)
    # the .pbip project file
    with open(os.path.join(HERE, "raw_plus", "report_raw_plus.pbip"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
                   "version": "1.0", "artifacts": [{"report": {"path": "report_raw_plus.Report"}}],
                   "settings": {"enableAutoRecovery": True}}, fh, indent=2)


def rp_extensions():
    os.makedirs(os.path.join(RAWPLUS, "definition"), exist_ok=True)
    measures = [{"name": n, "expression": e, "dataType": "Double", "formatString": f,
                 "hidden": False, "references": {"unrecognizedReferences": False}}
                for n, e, f in RP_MEASURES]
    with open(os.path.join(RAWPLUS, "definition", "reportExtensions.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump({"$schema": EXT, "name": "extension",
                   "entities": [{"name": RP_HOME, "measures": measures}]}, fh, indent=2)


def m(name):
    return proj(RP_HOME, name, True)


def build_raw_plus():
    rp_scaffold()
    rp_extensions()
    pages = []

    def P(n):
        return ("xp%02dpage" % n + "0" * 20)[:20]

    def title(pid, n, q, note):
        return textbox(f"x{pid}t", 16, 16, 1248, 72,
                       [f"Q{n} — {q}  [INSTRUCTED RAW / forced]", f"Forced via report-level DAX: {note}"])

    # Q1
    p = P(1)
    pages.append((p, "Q1 — Revenue by channel (RAW+)", [
        title(p, 1, "Revenue in Q1 2026 by channel",
              "RP Revenue = SUMX(qty x price) by channel, date_key 20260101-20260331. Correct for ERP channels (gold)."),
        column_chart(f"x{p}v", 16, 100, 1248, 540,
                     proj("sales_order_lines", "channel"), m("RP Revenue"),
                     filters=[f_range("xq1d", "sales_order_lines", "date_key", "20260101L", "20260331L")],
                     sort=sort_desc(RP_HOME, "RP Revenue")),
    ]))

    # Q2
    p = P(2)
    pages.append((p, "Q2 — Top 5 products by revenue (RAW+)", [
        title(p, 2, "Top 5 products by revenue",
              "RP Revenue by SKU, sorted desc. ERP-only (no marketplace/Lakeside) so ranking can differ from gold."),
        table(f"x{p}v", 16, 100, 900, 540,
              [proj("sales_order_lines", "sku"), proj("products", "product_name"), m("RP Revenue")],
              sort=sort_desc(RP_HOME, "RP Revenue")),
    ]))

    # Q3
    p = P(3)
    pages.append((p, "Q3 — Stockout rate May 2026 (RAW+)", [
        title(p, 3, "Stockout rate in May 2026",
              "RP Stockout Rate = stockout rows / total rows, visual-filtered to May date_key. Close to gold 1.52%."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Stockout Rate"),
             filters=[f_range("xq3d", "inventory_daily", "date_key", "20260501L", "20260531L")]),
    ]))

    # Q4
    p = P(4)
    pages.append((p, "Q4 — Total company sales May 2026 (RAW+)", [
        title(p, 4, "Total company sales May 2026 incl. Lakeside + marketplace",
              "Cross-source sum re-derived in DAX: ERP (date_key) + marketplace NET (parsed settlementDate) + Lakeside (parsed DD/MM/YYYY). Targets gold $10.054M."),
        card(f"x{p}a", 16, 100, 300, 200, m("RP ERP May")),
        card(f"x{p}b", 328, 100, 300, 200, m("RP MM Net May")),
        card(f"x{p}c", 640, 100, 300, 200, m("RP LS May")),
        card(f"x{p}d", 952, 100, 300, 200, m("RP Total May")),
    ]))

    # Q5
    p = P(5)
    pages.append((p, "Q5 — Net marketplace revenue (RAW+)", [
        title(p, 5, "Net marketplace revenue after fees, by month",
              "RP Marketplace Net = SUM(payoutAmount). No date dimension to bucket by month, so a single window total is forced (gold net $7.335M)."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Marketplace Net")),
    ]))

    # Q6
    p = P(6)
    pages.append((p, "Q6 — Tickets per 1K units (RAW+)", [
        title(p, 6, "Products with most helpdesk tickets per 1,000 units sold",
              "EXACT product-name match of free-text productRef to products[product_name]. Misspelled/spaced refs miss, so counts under-report vs gold (SKU-0045/0014)."),
        table(f"x{p}v", 16, 100, 1100, 540,
              [proj("products", "sku"), proj("products", "product_name"),
               m("RP Tickets Exact"), m("RP Units"), m("RP Tickets per 1K")],
              sort=sort_desc(RP_HOME, "RP Tickets per 1K")),
    ]))

    # Q7
    p = P(7)
    pages.append((p, "Q7 — Parts attach rate Hydraulics (RAW+)", [
        title(p, 7, "Service parts attach rate for Hydraulics products",
              "ITM- codes mapped to SKU via sku_xref_master LOOKUPVALUE, restricted to category Hydraulics; parts / units * 100. Targets gold 8.1."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Parts per 100 Hydraulics")),
    ]))

    # Q8
    p = P(8)
    pages.append((p, "Q8 — A-class open complaints + stockout (RAW+)", [
        title(p, 8, "A-class products with open complaints AND stockout risk",
              "A-class products with exact-match open complaints + latest-snapshot on-hand <= safety stock. Exact-name match may miss the gold SKUs (0014/0045)."),
        table(f"x{p}v", 16, 100, 1100, 540,
              [proj("products", "sku"), proj("products", "product_name"),
               m("RP Open Complaints Exact"), m("RP At Stockout Risk")],
              filters=[f_cat("xq8a", "products", "abc_class", "'A'")],
              sort=sort_desc(RP_HOME, "RP Open Complaints Exact")),
    ]))

    # Q9
    p = P(9)
    pages.append((p, "Q9 — Lakeside vs DC sell-through (RAW+)", [
        title(p, 9, "Lakeside store sell-through vs DCs since acquisition",
              "Both ratios re-derived since 2026-02-01 (Lakeside via parsed DD/MM/YYYY + weekly counts; DC via date_key + daily). Mixed grain makes both approximate (gold 2.85x vs 1.70x)."),
        card(f"x{p}a", 16, 100, 360, 200, m("RP Lakeside Sell-Through")),
        card(f"x{p}b", 392, 100, 360, 200, m("RP DC Sell-Through")),
    ]))

    # Q10
    p = P(10)
    pages.append((p, "Q10 — Lakeside sales 03/02/2026 (RAW+)", [
        title(p, 10, "Lakeside sales on 03/02/2026",
              "Text-equality on '03/02/2026' read as DD/MM/YYYY = 3 Feb. Forced CORRECTLY because the author knows the format (gold $36,836)."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Lakeside Sales 03Feb")),
    ]))

    # Q11
    p = P(11)
    pages.append((p, "Q11 — Lakeside revenue since acquisition (RAW+)", [
        title(p, 11, "Lakeside revenue since the acquisition (from 2026-02-01)",
              "SUM(TOTAL_AMT) where parsed DD/MM/YYYY >= 2026-02-01. Targets gold $4.324M."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Lakeside Since Acq")),
    ]))

    # Q12
    p = P(12)
    pages.append((p, "Q12 — Marketplace revenue not tied to a product (RAW+)", [
        title(p, 12, "Marketplace revenue not tied to one of our products",
              "Anti-join: SUM(mm_orders gross) where listingId has NO sku_xref_master[mm_listing_id] match. Targets gold ~$94K gross."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Unmatched MM Gross")),
    ]))

    order = [pid for pid, _, _ in pages]
    clean_old_pages(RAWPLUS, set(order))
    for pid, disp, vis in pages:
        write_page(RAWPLUS, pid, disp, vis)
    write_pages_json(RAWPLUS, order, order[0])
    return order


if __name__ == "__main__":
    mo = build_modeled()
    ro = build_raw()
    rp = build_raw_plus()
    print("MODELED pages:", len(mo))
    print("RAW pages:", len(ro))
    print("RAW_PLUS pages:", len(rp), "| measures:", len(RP_MEASURES))
