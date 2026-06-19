#!/usr/bin/env python3
"""Generate PBIR pages + visuals for the LEGACY and MODELED eval reports.

The MODELED report answers each question with the governed measures. The
LEGACY report ("instructed legacy") live-connects to the MultiSource_Legacy model
and forces an answer on every tile via report-level DAX (cross-source sums,
text-date parsing, xref lookups) — like the Legacy agent, some answers stay
approximate because the legacy schema fights back.

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

def field(entity, prop, measure=False, extension=False):
    kind = "Measure" if measure else "Column"
    # Report-level (extension) measures MUST be referenced with Schema="extension",
    # otherwise Power BI resolves against the model, fails, and raises Missing_References.
    sref = {"Schema": "extension", "Entity": entity} if extension else {"Entity": entity}
    return {kind: {"Expression": {"SourceRef": sref}, "Property": prop}}


def proj(entity, prop, measure=False, extension=False):
    return {"field": field(entity, prop, measure, extension),
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


def sort_desc(entity, prop, measure=True, extension=False):
    return {"sortDefinition": {"sort": [{"field": field(entity, prop, measure, extension), "direction": "Descending"}]}}


def sort_asc(entity, prop, measure=False, extension=False):
    return {"sortDefinition": {"sort": [{"field": field(entity, prop, measure, extension), "direction": "Ascending"}]}}


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

def write_page(report_dir, page_id, display_name, visuals, width=1280, height=720, objects=None):
    pdir = os.path.join(report_dir, "definition", "pages", page_id)
    vdir = os.path.join(pdir, "visuals")
    if os.path.isdir(pdir):
        # wipe visuals but keep folder; rewrite page.json
        if os.path.isdir(vdir):
            shutil.rmtree(vdir)
    os.makedirs(vdir, exist_ok=True)
    page = {"$schema": PAGE, "name": page_id, "displayName": display_name,
            "displayOption": "FitToPage", "height": height, "width": width}
    if objects:
        page["objects"] = objects
    with open(os.path.join(pdir, "page.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(page, fh, indent=2)
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
MODELED = os.path.join(HERE, "modeled", "report_modeled.Report")
MQ1 = "9395695480646891e085"  # existing page folder, reuse for Q1
MSUMMARY = "0496682b32921312e05e"  # the "Summary" page (1920x1080) — all 12 answers

SU = "c_fact_sales_unified"   # all measures live here

# ----------------------------------------------------------------------------
# Shared branding for the Summary pages (theme + registered background image).
# The modeled report holds the canonical theme + image; legacy gets a
# copy so both Summary pages render identically. Encoding it here keeps it
# drift-safe — regeneration re-applies the look instead of wiping it.
# ----------------------------------------------------------------------------
# Theme = CY26SU05 base + AccessibleTidal custom (the committed restyle). Each
# report owns its OWN committed StaticResources: the two theme JSONs and a
# per-report background PNG (the two reports use DIFFERENT images). Regeneration
# must PRESERVE those files and only (re)write report.json + the Summary page
# background to point at the report's own image — never copy or clobber them.
THEME_VER = {"visual": "2.9.0", "report": "3.3.0", "page": "2.3.1"}
CUSTOM_VER = {"visual": "2.10.0", "report": "3.4.0", "page": "2.3.1"}


def _bg_image(report_dir):
    """The report's own registered background image (first PNG under RegisteredResources)."""
    rr = os.path.join(report_dir, "StaticResources", "RegisteredResources")
    pngs = sorted(f for f in os.listdir(rr) if f.lower().endswith(".png")) if os.path.isdir(rr) else []
    return pngs[0] if pngs else None


def branding(image_name):
    pkgs = [{"name": "SharedResources", "type": "SharedResources", "items": [
        {"name": "AccessibleTidal", "path": "BuiltInThemes/AccessibleTidal.json", "type": "CustomTheme"},
        {"name": "CY26SU05", "path": "BaseThemes/CY26SU05.json", "type": "BaseTheme"}]}]
    if image_name:
        pkgs.append({"name": "RegisteredResources", "type": "RegisteredResources",
                     "items": [{"name": image_name, "path": image_name, "type": "Image"}]})
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY26SU05", "reportVersionAtImport": THEME_VER, "type": "SharedResources"},
            "customTheme": {"name": "AccessibleTidal", "reportVersionAtImport": CUSTOM_VER, "type": "SharedResources"},
        },
        "objects": {
            "section": [{"properties": {"verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}],
            "outspacePane": [{"properties": {"expanded": {"expr": {"Literal": {"Value": "false"}}}}}],
        },
        "resourcePackages": pkgs,
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True},
    }


def summary_bg(image_name):
    """Page-level background = the report's registered image, scaled to fit, 85% transparent
    (the AccessibleTidal theme gives every visual an opaque fill so tiles stay readable)."""
    return {"background": [{"properties": {
        "image": {"image": {
            "name": {"expr": {"Literal": {"Value": "'img.png'"}}},
            "url": {"expr": {"ResourcePackageItem": {
                "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": image_name}}},
            "scaling": {"expr": {"Literal": {"Value": "'Fit'"}}},
        }},
        "transparency": {"expr": {"Literal": {"Value": "85D"}}},
    }}]}


def brand_report(report_dir):
    """Rewrite report.json to register the committed CY26SU05 + AccessibleTidal
    themes and the report's own background image. Does NOT copy or create any
    StaticResources — they are committed per report."""
    with open(os.path.join(report_dir, "definition", "report.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(branding(_bg_image(report_dir)), fh, indent=2)


def build_modeled_summary():
    """One overview page (1920x1080) holding a compact tile per eval question,
    each driven by the same governed measure the per-question page uses. The
    point of the Summary page is that the modeled star answers all 12 at once."""
    SUM = MSUMMARY
    visuals = [textbox(f"s{SUM}title", 16, 16, 1888, 60,
                       ["MultiSource Modeled — all 12 answers",
                        "One governed star schema answers every eval question"])]

    cols = [16, 492, 968, 1444]   # 4 columns, width 460
    rows = [100, 421, 742]        # 3 rows, height 305
    W = 460
    HH = 64                       # header textbox height
    CY = 72                       # content offset within the tile
    CH = 229                      # content visual height
    CW_CARD = 220                 # card width (single-value answers)

    def cell(i):
        return cols[i % 4], rows[i // 4]

    def hdr(n, x, y, q, gold):
        return textbox(f"s{SUM}h{n:02d}", x, y, W, HH, [f"Q{n} — {q}", f"Gold: {gold}"])

    # Q1 — revenue by channel (Q1 2026)
    x, y = cell(0)
    visuals.append(hdr(1, x, y, "Revenue by channel, Q1 2026", "Online 7.03 / Retail 7.16 / Wholesale 6.91 ($M)"))
    visuals.append(column_chart(f"s{SUM}v01", x, y + CY, W, CH,
                                proj("c_dim_channel", "channel"), proj(SU, "Revenue Net", True),
                                filters=[f_cat("sq1y", "c_dim_date", "year", "2026L"),
                                         f_cat("sq1q", "c_dim_date", "quarter", "1L")],
                                sort=sort_desc(SU, "Revenue Net")))

    # Q2 — stockout rate May 2026
    x, y = cell(1)
    visuals.append(hdr(2, x, y, "Stockout rate, May 2026", "1.52% of SKU-location-days"))
    visuals.append(card(f"s{SUM}v02", x, y + CY, CW_CARD, CH, proj(SU, "Stockout Rate %", True),
                        filters=[f_cat("sq2y", "c_dim_date", "year", "2026L"),
                                 f_cat("sq2m", "c_dim_date", "month", "5L")]))

    # Q3 — total company sales May 2026
    x, y = cell(2)
    visuals.append(hdr(3, x, y, "Total company sales, May 2026", "$10.054M (ERP + MM net + Lakeside)"))
    visuals.append(card(f"s{SUM}v03", x, y + CY, CW_CARD, CH, proj(SU, "Revenue Net", True),
                        filters=[f_cat("sq3y", "c_dim_date", "year", "2026L"),
                                 f_cat("sq3m", "c_dim_date", "month", "5L")]))

    # Q4 — tickets per 1K units
    x, y = cell(3)
    visuals.append(hdr(4, x, y, "Tickets per 1K units", "SKU-0045, SKU-0014"))
    visuals.append(table(f"s{SUM}v04", x, y + CY, W, CH,
                         [proj("c_dim_product", "sku"), proj("c_dim_product", "product_name"),
                          proj(SU, "Tickets per 1K Units", True)],
                         sort=sort_desc(SU, "Tickets per 1K Units")))

    # Q5 — parts attach rate Hydraulics
    x, y = cell(4)
    visuals.append(hdr(5, x, y, "Parts attach rate, Hydraulics", "8.1 parts per 100 units"))
    visuals.append(card(f"s{SUM}v05", x, y + CY, CW_CARD, CH, proj(SU, "Parts per 100 Units", True),
                        filters=[f_cat("sq5c", "c_dim_product", "category", "'Hydraulics'")]))

    # Q6 — A-class open complaints + stockout
    x, y = cell(5)
    visuals.append(hdr(6, x, y, "A-class open complaints + stockout", "SKU-0014, SKU-0045"))
    visuals.append(table(f"s{SUM}v06", x, y + CY, W, CH,
                         [proj("c_dim_product", "sku"), proj("c_dim_product", "product_name"),
                          proj(SU, "Open Complaints", True), proj(SU, "Avg On-Hand Units", True)],
                         filters=[f_cat("sq6a", "c_dim_product", "abc_class", "'A'")],
                         sort=sort_desc(SU, "Open Complaints")))

    # Q7 — Lakeside vs DC sell-through
    x, y = cell(6)
    visuals.append(hdr(7, x, y, "Lakeside vs DC sell-through", "Lakeside 2.85x vs DCs 1.70x"))
    visuals.append(column_chart(f"s{SUM}v07", x, y + CY, W, CH,
                                proj("c_dim_location", "location_type"), proj(SU, "Sell-Through Ratio", True),
                                filters=[f_cat("sq7p", "c_dim_date", "is_post_acquisition", "true")],
                                sort=sort_desc(SU, "Sell-Through Ratio")))

    # Q8 — Lakeside sales 03/02/2026
    x, y = cell(7)
    visuals.append(hdr(8, x, y, "Lakeside sales 03/02/2026 (3 Feb)", "$36,836"))
    visuals.append(card(f"s{SUM}v08", x, y + CY, CW_CARD, CH, proj(SU, "Lakeside Revenue", True),
                        filters=[f_cat("sq8d", "c_dim_date", "date_key", "20260203L")]))

    # Q9 — Lakeside revenue since acquisition
    x, y = cell(8)
    visuals.append(hdr(9, x, y, "Lakeside revenue since acquisition", "$4.324M"))
    visuals.append(card(f"s{SUM}v09", x, y + CY, CW_CARD, CH, proj(SU, "Lakeside Revenue", True),
                        filters=[f_cat("sq9p", "c_dim_date", "is_post_acquisition", "true")]))

    # Q10 — share of revenue tied to a known product
    x, y = cell(9)
    visuals.append(hdr(10, x, y, "Revenue tied to a known product", "99.5% attributable; $0.55M unmapped"))
    visuals.append(card(f"s{SUM}v10", x, y + CY, CW_CARD, CH, proj(SU, "Attributable Revenue %", True)))

    # Q11 — worst after-sale reliability by category
    x, y = cell(10)
    visuals.append(hdr(11, x, y, "After-sale issues per 1K, by category", "Hydraulics 88.5/1K (worst)"))
    visuals.append(table(f"s{SUM}v11", x, y + CY, W, CH,
                         [proj("c_dim_product", "category"), proj(SU, "After-Sale Issues per 1K Units", True),
                          proj(SU, "Complaints", True), proj(SU, "Service Parts Used", True)],
                         sort=sort_desc(SU, "After-Sale Issues per 1K Units")))

    # Q12 — most overstocked vs category-average sell-through
    x, y = cell(11)
    visuals.append(hdr(12, x, y, "Overstock vs category avg sell-through", "SKU-0029/0039/0081 (~0.5x vs ~6x)"))
    visuals.append(table(f"s{SUM}v12", x, y + CY, W, CH,
                         [proj("c_dim_product", "category"), proj("c_dim_product", "sku"),
                          proj(SU, "Sell-Through Ratio", True), proj(SU, "Category Avg Sell-Through", True)],
                         sort=sort_asc(SU, "Sell-Through Ratio", measure=True)))

    return (SUM, "Summary", visuals)


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

    # Q2 — stockout rate May 2026
    p = P(2)
    pages.append((p, "Q2 — Stockout rate May 2026", [
        title(p, 2, "Stockout rate in May 2026", "1.52% of SKU-location-days"),
        card(f"m{p}v", 16, 88, 360, 200, proj(SU, "Stockout Rate %", True),
             filters=[f_cat("mq2y", "c_dim_date", "year", "2026L"),
                      f_cat("mq2m", "c_dim_date", "month", "5L")]),
    ]))

    # Q3 — total company sales May 2026 (four cards)
    p = P(3)
    f3 = [f_cat("mq3y", "c_dim_date", "year", "2026L"), f_cat("mq3m", "c_dim_date", "month", "5L")]
    pages.append((p, "Q3 — Total company sales May 2026", [
        title(p, 3, "Total company sales May 2026 incl. Lakeside + marketplace",
              "$10.054M = ERP $8.382M + MM net $0.622M + Lakeside $1.051M"),
        card(f"m{p}a", 16, 88, 300, 200, proj(SU, "ERP Revenue", True), filters=f3),
        card(f"m{p}b", 328, 88, 300, 200, proj(SU, "Marketplace Net Revenue", True), filters=f3),
        card(f"m{p}c", 640, 88, 300, 200, proj(SU, "Lakeside Revenue", True), filters=f3),
        card(f"m{p}d", 952, 88, 300, 200, proj(SU, "Revenue Net", True), filters=f3),
    ]))

    # Q4 — tickets per 1K units
    p = P(4)
    pages.append((p, "Q4 — Tickets per 1K units", [
        title(p, 4, "Products with most helpdesk tickets per 1,000 units sold", "SKU-0045, SKU-0014 (read top rows)"),
        table(f"m{p}v", 16, 88, 1100, 560,
              [proj("c_dim_product", "sku"), proj("c_dim_product", "product_name"),
               proj(SU, "Tickets per 1K Units", True), proj(SU, "Units Sold", True),
               proj(SU, "Tickets", True)],
              sort=sort_desc(SU, "Tickets per 1K Units")),
    ]))

    # Q5 — parts attach rate Hydraulics
    p = P(5)
    pages.append((p, "Q5 — Parts attach rate Hydraulics", [
        title(p, 5, "Service parts attach rate for Hydraulics products", "8.1 parts per 100 units"),
        card(f"m{p}v", 16, 88, 360, 200, proj(SU, "Parts per 100 Units", True),
             filters=[f_cat("mq5c", "c_dim_product", "category", "'Hydraulics'")]),
    ]))

    # Q6 — A-class open complaints + stockout
    p = P(6)
    pages.append((p, "Q6 — A-class open complaints + stockout", [
        title(p, 6, "A-class products with open complaints AND stockout risk", "SKU-0014, SKU-0045 (top rows: complaints>0, low on-hand)"),
        table(f"m{p}v", 16, 88, 1100, 560,
              [proj("c_dim_product", "sku"), proj("c_dim_product", "product_name"),
               proj(SU, "Open Complaints", True), proj(SU, "Avg On-Hand Units", True)],
              filters=[f_cat("mq6a", "c_dim_product", "abc_class", "'A'")],
              sort=sort_desc(SU, "Open Complaints")),
    ]))

    # Q7 — Lakeside vs DC sell-through
    p = P(7)
    pages.append((p, "Q7 — Lakeside vs DC sell-through", [
        title(p, 7, "Lakeside store sell-through vs DCs since acquisition", "Lakeside 2.85x vs DCs 1.70x"),
        column_chart(f"m{p}v", 16, 88, 1248, 560,
                     proj("c_dim_location", "location_type"), proj(SU, "Sell-Through Ratio", True),
                     filters=[f_cat("mq7p", "c_dim_date", "is_post_acquisition", "true")],
                     sort=sort_desc(SU, "Sell-Through Ratio")),
    ]))

    # Q8 — Lakeside sales 03/02/2026
    p = P(8)
    pages.append((p, "Q8 — Lakeside sales 03/02/2026", [
        title(p, 8, "Lakeside sales on 03/02/2026 (DD/MM/YYYY = 3 Feb)", "$36,836"),
        card(f"m{p}v", 16, 88, 360, 200, proj(SU, "Lakeside Revenue", True),
             filters=[f_cat("mq8d", "c_dim_date", "date_key", "20260203L")]),
    ]))

    # Q9 — Lakeside revenue since acquisition
    p = P(9)
    pages.append((p, "Q9 — Lakeside revenue since acquisition", [
        title(p, 9, "Lakeside revenue since the acquisition (from 2026-02-01)", "$4.324M"),
        card(f"m{p}v", 16, 88, 360, 200, proj(SU, "Lakeside Revenue", True),
             filters=[f_cat("mq9p", "c_dim_date", "is_post_acquisition", "true")]),
    ]))

    # Q10 — share of revenue tied to a known product
    p = P(10)
    pages.append((p, "Q10 — Revenue tied to a known product", [
        title(p, 10, "Share of total revenue that ties to a known product",
              "99.5% attributable; $0.553M (0.48%) unattributable — all stale MegaMart UNMAPPED listings"),
        card(f"m{p}a", 16, 88, 360, 200, proj(SU, "Attributable Revenue %", True)),
        card(f"m{p}b", 392, 88, 360, 200, proj(SU, "Unattributable Revenue", True)),
        card(f"m{p}c", 768, 88, 360, 200, proj(SU, "Revenue Net", True)),
    ]))

    # Q11 — worst after-sale reliability by category
    p = P(11)
    pages.append((p, "Q11 — After-sale reliability by category", [
        title(p, 11, "Product category with the worst after-sale reliability",
              "Hydraulics 88.5 issues/1K (1,420 complaints + 16,156 parts / 198,582 units); ignore tiny 'Unknown' bucket"),
        table(f"m{p}v", 16, 88, 1100, 560,
              [proj("c_dim_product", "category"), proj(SU, "After-Sale Issues per 1K Units", True),
               proj(SU, "Complaints", True), proj(SU, "Service Parts Used", True), proj(SU, "Units Sold", True)],
              sort=sort_desc(SU, "After-Sale Issues per 1K Units")),
    ]))

    # Q12 — most overstocked vs category-average sell-through
    p = P(12)
    pages.append((p, "Q12 — Overstock vs category average", [
        title(p, 12, "Products most overstocked vs their category's average sell-through",
              "Worst: SKU-0029, SKU-0039 (Fasteners), SKU-0081 (Hydraulics) ~0.5x vs ~6x category avg (read bottom rows)"),
        table(f"m{p}v", 16, 88, 1100, 560,
              [proj("c_dim_product", "category"), proj("c_dim_product", "sku"),
               proj("c_dim_product", "product_name"), proj("c_dim_product", "abc_class"),
               proj(SU, "Sell-Through Ratio", True), proj(SU, "Category Avg Sell-Through", True)],
              sort=sort_asc(SU, "Sell-Through Ratio", measure=True)),
    ]))

    pages = [build_modeled_summary()]  # Summary page only; question pages dropped

    order = [pid for pid, _, _ in pages]
    clean_old_pages(MODELED, set(order))
    for pid, disp, vis in pages:
        if pid == MSUMMARY:
            write_page(MODELED, pid, disp, vis, width=1920, height=1080, objects=summary_bg(_bg_image(MODELED)))
        else:
            write_page(MODELED, pid, disp, vis)
    write_pages_json(MODELED, order, order[0])
    brand_report(MODELED)
    return order


# ============================================================================
# LEGACY report — instructed legacy: force an answer on every page using heavy
# report-level DAX (the report analog of the Legacy agent's instructions).
# Connects to the SAME legacy model; re-derives cross-source joins, parses text
# dates, and looks up the xref entirely in the report layer. Like the Legacy
# agent (~9/24), several answers are approximate/wrong because the legacy schema
# fights back (free-text helpdesk refs, mixed-grain inventory) — that is the point.
# ============================================================================
LEGACY = os.path.join(HERE, "legacy", "report_legacy.Report")
RP_LOGICAL_ID = "f7e6d5c4-b3a2-4190-8e7f-0a1b2c3d4e5f"
RP_HOME = "sales_order_lines"  # home table for all RP report-level measures

# DAX re-derivations. Two date columns, two DIFFERENT types — parse each per type:
#   - mm_settlements[settlementDate] is a real DATE in the model (ISO 'YYYY-MM-DD'
#     auto-types to date). Use YEAR()/MONTH(), NOT text slicing: LEFT()/MID() on a
#     date first coerce it to text via the locale short-date format ('M/D/YYYY'),
#     so a single-digit month/day (e.g. Jan 4 -> '1/4/2026') makes VALUE(LEFT(.,4))
#     read '1/4' and throw "Cannot convert '1/4' to Number".
#   - LS_SALES_EXPORT[SALE_DATE] is genuine TEXT 'DD/MM/YYYY' (varchar, zero-padded),
#     so LEFT/MID/RIGHT slicing is correct there and stays.
# Helpdesk productRef is free text (exact-name match only).
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
     "SUMX(FILTER(mm_settlements, YEAR(mm_settlements[settlementDate]) = 2026 "
     "&& MONTH(mm_settlements[settlementDate]) = 5), mm_settlements[payoutAmount])", "#,##0"),
    ("RP LS May",
     "SUMX(FILTER(LS_SALES_EXPORT, VALUE(RIGHT(LS_SALES_EXPORT[SALE_DATE],4)) = 2026 "
     "&& VALUE(MID(LS_SALES_EXPORT[SALE_DATE],4,2)) = 5), LS_SALES_EXPORT[TOTAL_AMT])", "#,##0"),
    ("RP Total May",
     "VAR erp = CALCULATE(SUMX(sales_order_lines, sales_order_lines[qty_sold] * sales_order_lines[unit_price]), "
     "sales_order_lines[date_key] >= 20260501, sales_order_lines[date_key] <= 20260531) "
     "VAR mm = SUMX(FILTER(mm_settlements, YEAR(mm_settlements[settlementDate]) = 2026 "
     "&& MONTH(mm_settlements[settlementDate]) = 5), mm_settlements[payoutAmount]) "
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
     # set-based mapping via TREATAS (no row-by-row LOOKUPVALUE -> no multi-match
     # error from the planted sku_xref_master conflict rows)
     "VAR hydSku = CALCULATETABLE(VALUES(products[sku]), products[category] = \"Hydraulics\") "
     "VAR hydItm = CALCULATETABLE(VALUES(sku_xref_master[itm_code]), TREATAS(hydSku, sku_xref_master[sku])) "
     "VAR parts = CALCULATE(SUM(ServicePartsUsage[QtyUsed]), TREATAS(hydItm, ServicePartsUsage[ItemCode])) "
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
    # Q11 — after-sale per 1K by category: exact-name complaints (under-counts free-text refs)
    # + ITM->SKU parts via xref TREATAS; grouped by products[category] in the visual.
    ("RP After-Sale per 1K",
     "VAR units = SUM(sales_order_lines[qty_sold]) "
     "VAR names = VALUES(products[product_name]) "
     "VAR comp = COUNTROWS(FILTER(hdTickets, hdTickets[categoryId] = 1 && hdTickets[productRef] IN names)) "
     "VAR itm = CALCULATETABLE(VALUES(sku_xref_master[itm_code]), TREATAS(VALUES(products[sku]), sku_xref_master[sku])) "
     "VAR parts = CALCULATE(SUM(ServicePartsUsage[QtyUsed]), TREATAS(itm, ServicePartsUsage[ItemCode])) "
     "RETURN DIVIDE(comp + parts, units) * 1000", "0.0"),
    # Q12 — per-product DC sell-through (ERP daily only; blind to Lakeside weekly grain)
    ("RP Sell-Through",
     "DIVIDE(SUM(sales_order_lines[qty_sold]), CALCULATE(AVERAGE(inventory_daily[on_hand_qty])))", "0.00"),
    # Q12 — category-average benchmark, re-derived in the report layer (approximate)
    ("RP Category Avg Sell-Through",
     "VAR cat = SELECTEDVALUE(products[category]) "
     "RETURN AVERAGEX(FILTER(ALL(products), products[category] = cat), "
     "CALCULATE(DIVIDE(SUM(sales_order_lines[qty_sold]), AVERAGE(inventory_daily[on_hand_qty]))))", "0.00"),
]


# legacy live-connects to the SAME MultiSource_Legacy model the agent's legacy data
# lives in; the report layer re-derives every answer via report-level DAX.
RP_CONN = ('Data Source="powerbi://api.powerbi.com/v1.0/myorg/Microsoft Fabric Demo Stand";'
           'initial catalog=MultiSource_Legacy;access mode=readonly;'
           'integrated security=ClaimsToken;semanticmodelid=85a29e39-bf6e-44ef-8982-561e9b3eba7e')


def _write_if_missing(path, obj):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=2)


def rp_scaffold():
    """Bootstrap the legacy PBIP shell, bound to the MultiSource_Legacy model.
    Self-contained (no dependency on the removed bare-legacy report); the committed
    scaffolding is the source of truth, so each file is written only when absent."""
    _write_if_missing(os.path.join(LEGACY, "definition.pbir"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byConnection": {"connectionString": RP_CONN}}})
    _write_if_missing(os.path.join(LEGACY, "definition", "version.json"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"})
    _write_if_missing(os.path.join(LEGACY, ".platform"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": "report_legacy"},
        "config": {"version": "2.0", "logicalId": RP_LOGICAL_ID}})
    _write_if_missing(os.path.join(HERE, "legacy", "report_legacy.pbip"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": "report_legacy.Report"}}],
        "settings": {"enableAutoRecovery": True}})


def rp_extensions():
    os.makedirs(os.path.join(LEGACY, "definition"), exist_ok=True)
    # Match exactly what Power BI Desktop writes for a report-level measure:
    # name, dataType, expression, formatString — and NO "references"/"hidden".
    # Including a hand-authored references block makes Desktop reject the measure
    # with Missing_References (confirmed by diffing a Desktop-created measure).
    measures = [{"name": n, "dataType": "Double", "expression": e, "formatString": f}
                for n, e, f in RP_MEASURES]
    with open(os.path.join(LEGACY, "definition", "reportExtensions.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump({"$schema": EXT, "name": "extension",
                   "entities": [{"name": RP_HOME, "measures": measures}]}, fh, indent=2)


def m(name):
    return proj(RP_HOME, name, True, extension=True)


RP_SUMMARY = "xsummarypage00000000"  # "Summary" page (1920x1080) — all 12, forced via DAX


def build_legacy_summary():
    """Summary page mirroring the modeled one, but every tile is forced via the
    report-level RP measures (same legacy model). Some answers are approximate or
    wrong because the legacy schema fights back — that is the instructed-legacy point."""
    SUM = RP_SUMMARY
    visuals = [textbox(f"x{SUM}title", 16, 16, 1888, 60,
                       ["MultiSource Legacy + instructions — all 12 forced via report-level DAX",
                        "Same legacy model; cross-source joins, parsed text dates and xref lookups re-derived in the report layer"])]

    cols = [16, 492, 968, 1444]
    rows = [100, 421, 742]
    W = 460
    HH = 64
    CY = 72
    CH = 229
    CW = 220

    def cell(i):
        return cols[i % 4], rows[i // 4]

    def hdr(n, x, y, q, note):
        return textbox(f"x{SUM}h{n:02d}", x, y, W, HH, [f"Q{n} — {q}", note])

    # Q1
    x, y = cell(0)
    visuals.append(hdr(1, x, y, "Revenue by channel, Q1 2026", "RP Revenue = SUMX(qty x price); correct for ERP channels"))
    visuals.append(column_chart(f"x{SUM}v01", x, y + CY, W, CH,
                                proj("sales_order_lines", "channel"), m("RP Revenue"),
                                filters=[f_range("xsq1d", "sales_order_lines", "date_key", "20260101L", "20260331L")],
                                sort=sort_desc(RP_HOME, "RP Revenue", extension=True)))

    # Q2 — stockout rate May
    x, y = cell(1)
    visuals.append(hdr(2, x, y, "Stockout rate, May 2026", "RP Stockout Rate, filtered to May; close to gold"))
    visuals.append(card(f"x{SUM}v02", x, y + CY, CW, CH, m("RP Stockout Rate"),
                        filters=[f_range("xsq2d", "inventory_daily", "date_key", "20260501L", "20260531L")]))

    # Q3 — total company sales May
    x, y = cell(2)
    visuals.append(hdr(3, x, y, "Total company sales, May 2026", "RP Total May = ERP + MM net + Lakeside (parsed dates)"))
    visuals.append(card(f"x{SUM}v03", x, y + CY, CW, CH, m("RP Total May")))

    # Q4 — tickets per 1K
    x, y = cell(3)
    visuals.append(hdr(4, x, y, "Tickets per 1K units", "Exact name match of free-text refs; under-reports"))
    visuals.append(table(f"x{SUM}v04", x, y + CY, W, CH,
                         [proj("products", "sku"), proj("products", "product_name"), m("RP Tickets per 1K")],
                         sort=sort_desc(RP_HOME, "RP Tickets per 1K", extension=True)))

    # Q5 — parts attach Hydraulics
    x, y = cell(4)
    visuals.append(hdr(5, x, y, "Parts attach rate, Hydraulics", "ITM->SKU via xref TREATAS; targets gold 8.1"))
    visuals.append(card(f"x{SUM}v05", x, y + CY, CW, CH, m("RP Parts per 100 Hydraulics")))

    # Q6 — A-class open complaints + stockout
    x, y = cell(5)
    visuals.append(hdr(6, x, y, "A-class open complaints + stockout", "Exact-name complaints; may miss gold SKUs"))
    visuals.append(table(f"x{SUM}v06", x, y + CY, W, CH,
                         [proj("products", "sku"), proj("products", "product_name"),
                          m("RP Open Complaints Exact"), m("RP At Stockout Risk")],
                         filters=[f_cat("xsq6a", "products", "abc_class", "'A'")],
                         sort=sort_desc(RP_HOME, "RP Open Complaints Exact", extension=True)))

    # Q7 — two cards (Lakeside vs DC)
    x, y = cell(6)
    visuals.append(hdr(7, x, y, "Lakeside vs DC sell-through", "Both re-derived since 2026-02-01; mixed grain"))
    visuals.append(card(f"x{SUM}v07a", x, y + CY, CW, CH, m("RP Lakeside Sell-Through")))
    visuals.append(card(f"x{SUM}v07b", x + CW + 20, y + CY, CW, CH, m("RP DC Sell-Through")))

    # Q8 — Lakeside sales 03/02
    x, y = cell(7)
    visuals.append(hdr(8, x, y, "Lakeside sales 03/02/2026", "Text equality read as DD/MM = 3 Feb; correct"))
    visuals.append(card(f"x{SUM}v08", x, y + CY, CW, CH, m("RP Lakeside Sales 03Feb")))

    # Q9 — Lakeside revenue since acquisition
    x, y = cell(8)
    visuals.append(hdr(9, x, y, "Lakeside revenue since acquisition", "SUM(TOTAL_AMT) where parsed date >= 2026-02-01"))
    visuals.append(card(f"x{SUM}v09", x, y + CY, CW, CH, m("RP Lakeside Since Acq")))

    # Q10 — revenue tied to a known product (legacy is blind to UNMAPPED; best-effort anti-join)
    x, y = cell(9)
    visuals.append(hdr(10, x, y, "Revenue not tied to a product", "Anti-join on missing xref listingId only; misses the real gap"))
    visuals.append(card(f"x{SUM}v10", x, y + CY, CW, CH, m("RP Unmatched MM Gross")))

    # Q11 — after-sale reliability by category
    x, y = cell(10)
    visuals.append(hdr(11, x, y, "After-sale issues per 1K, by category", "Exact-name complaints + xref parts; ranking approximate"))
    visuals.append(table(f"x{SUM}v11", x, y + CY, W, CH,
                         [proj("products", "category"), m("RP After-Sale per 1K")],
                         sort=sort_desc(RP_HOME, "RP After-Sale per 1K", extension=True)))

    # Q12 — overstock vs category-average sell-through
    x, y = cell(11)
    visuals.append(hdr(12, x, y, "Overstock vs category avg sell-through", "DC-only sell-through + re-derived benchmark; misses Lakeside grain"))
    visuals.append(table(f"x{SUM}v12", x, y + CY, W, CH,
                         [proj("products", "category"), proj("products", "sku"),
                          m("RP Sell-Through"), m("RP Category Avg Sell-Through")],
                         sort=sort_asc(RP_HOME, "RP Sell-Through", measure=True, extension=True)))

    return (SUM, "Summary", visuals)


def build_legacy():
    rp_scaffold()
    rp_extensions()
    pages = []

    def P(n):
        return ("xp%02dpage" % n + "0" * 20)[:20]

    def title(pid, n, q, note):
        return textbox(f"x{pid}t", 16, 16, 1248, 72,
                       [f"Q{n} — {q}  [INSTRUCTED LEGACY / forced]", f"Forced via report-level DAX: {note}"])

    # Q1
    p = P(1)
    pages.append((p, "Q1 — Revenue by channel (LEGACY)", [
        title(p, 1, "Revenue in Q1 2026 by channel",
              "RP Revenue = SUMX(qty x price) by channel, date_key 20260101-20260331. Correct for ERP channels (gold)."),
        column_chart(f"x{p}v", 16, 100, 1248, 540,
                     proj("sales_order_lines", "channel"), m("RP Revenue"),
                     filters=[f_range("xq1d", "sales_order_lines", "date_key", "20260101L", "20260331L")],
                     sort=sort_desc(RP_HOME, "RP Revenue", extension=True)),
    ]))

    # Q2
    p = P(2)
    pages.append((p, "Q2 — Top 5 products by revenue (LEGACY)", [
        title(p, 2, "Top 5 products by revenue",
              "RP Revenue by SKU, sorted desc. ERP-only (no marketplace/Lakeside) so ranking can differ from gold."),
        table(f"x{p}v", 16, 100, 900, 540,
              [proj("sales_order_lines", "sku"), proj("products", "product_name"), m("RP Revenue")],
              sort=sort_desc(RP_HOME, "RP Revenue", extension=True)),
    ]))

    # Q3
    p = P(3)
    pages.append((p, "Q3 — Stockout rate May 2026 (LEGACY)", [
        title(p, 3, "Stockout rate in May 2026",
              "RP Stockout Rate = stockout rows / total rows, visual-filtered to May date_key. Close to gold 1.52%."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Stockout Rate"),
             filters=[f_range("xq3d", "inventory_daily", "date_key", "20260501L", "20260531L")]),
    ]))

    # Q4
    p = P(4)
    pages.append((p, "Q4 — Total company sales May 2026 (LEGACY)", [
        title(p, 4, "Total company sales May 2026 incl. Lakeside + marketplace",
              "Cross-source sum re-derived in DAX: ERP (date_key) + marketplace NET (parsed settlementDate) + Lakeside (parsed DD/MM/YYYY). Targets gold $10.054M."),
        card(f"x{p}a", 16, 100, 300, 200, m("RP ERP May")),
        card(f"x{p}b", 328, 100, 300, 200, m("RP MM Net May")),
        card(f"x{p}c", 640, 100, 300, 200, m("RP LS May")),
        card(f"x{p}d", 952, 100, 300, 200, m("RP Total May")),
    ]))

    # Q5
    p = P(5)
    pages.append((p, "Q5 — Net marketplace revenue (LEGACY)", [
        title(p, 5, "Net marketplace revenue after fees, by month",
              "RP Marketplace Net = SUM(payoutAmount). No date dimension to bucket by month, so a single window total is forced (gold net $7.335M)."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Marketplace Net")),
    ]))

    # Q6
    p = P(6)
    pages.append((p, "Q6 — Tickets per 1K units (LEGACY)", [
        title(p, 6, "Products with most helpdesk tickets per 1,000 units sold",
              "EXACT product-name match of free-text productRef to products[product_name]. Misspelled/spaced refs miss, so counts under-report vs gold (SKU-0045/0014)."),
        table(f"x{p}v", 16, 100, 1100, 540,
              [proj("products", "sku"), proj("products", "product_name"),
               m("RP Tickets Exact"), m("RP Units"), m("RP Tickets per 1K")],
              sort=sort_desc(RP_HOME, "RP Tickets per 1K", extension=True)),
    ]))

    # Q7
    p = P(7)
    pages.append((p, "Q7 — Parts attach rate Hydraulics (LEGACY)", [
        title(p, 7, "Service parts attach rate for Hydraulics products",
              "ITM- codes mapped to SKU via sku_xref_master LOOKUPVALUE, restricted to category Hydraulics; parts / units * 100. Targets gold 8.1."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Parts per 100 Hydraulics")),
    ]))

    # Q8
    p = P(8)
    pages.append((p, "Q8 — A-class open complaints + stockout (LEGACY)", [
        title(p, 8, "A-class products with open complaints AND stockout risk",
              "A-class products with exact-match open complaints + latest-snapshot on-hand <= safety stock. Exact-name match may miss the gold SKUs (0014/0045)."),
        table(f"x{p}v", 16, 100, 1100, 540,
              [proj("products", "sku"), proj("products", "product_name"),
               m("RP Open Complaints Exact"), m("RP At Stockout Risk")],
              filters=[f_cat("xq8a", "products", "abc_class", "'A'")],
              sort=sort_desc(RP_HOME, "RP Open Complaints Exact", extension=True)),
    ]))

    # Q9
    p = P(9)
    pages.append((p, "Q9 — Lakeside vs DC sell-through (LEGACY)", [
        title(p, 9, "Lakeside store sell-through vs DCs since acquisition",
              "Both ratios re-derived since 2026-02-01 (Lakeside via parsed DD/MM/YYYY + weekly counts; DC via date_key + daily). Mixed grain makes both approximate (gold 2.85x vs 1.70x)."),
        card(f"x{p}a", 16, 100, 360, 200, m("RP Lakeside Sell-Through")),
        card(f"x{p}b", 392, 100, 360, 200, m("RP DC Sell-Through")),
    ]))

    # Q10
    p = P(10)
    pages.append((p, "Q10 — Lakeside sales 03/02/2026 (LEGACY)", [
        title(p, 10, "Lakeside sales on 03/02/2026",
              "Text-equality on '03/02/2026' read as DD/MM/YYYY = 3 Feb. Forced CORRECTLY because the author knows the format (gold $36,836)."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Lakeside Sales 03Feb")),
    ]))

    # Q11
    p = P(11)
    pages.append((p, "Q11 — Lakeside revenue since acquisition (LEGACY)", [
        title(p, 11, "Lakeside revenue since the acquisition (from 2026-02-01)",
              "SUM(TOTAL_AMT) where parsed DD/MM/YYYY >= 2026-02-01. Targets gold $4.324M."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Lakeside Since Acq")),
    ]))

    # Q12
    p = P(12)
    pages.append((p, "Q12 — Marketplace revenue not tied to a product (LEGACY)", [
        title(p, 12, "Marketplace revenue not tied to one of our products",
              "Anti-join: SUM(mm_orders gross) where listingId has NO sku_xref_master[mm_listing_id] match. Targets gold ~$94K gross."),
        card(f"x{p}v", 16, 100, 360, 200, m("RP Unmatched MM Gross")),
    ]))

    pages = [build_legacy_summary()]  # Summary page only; question pages dropped
    order = [pid for pid, _, _ in pages]
    clean_old_pages(LEGACY, set(order))
    for pid, disp, vis in pages:
        if pid == RP_SUMMARY:
            write_page(LEGACY, pid, disp, vis, width=1920, height=1080, objects=summary_bg(_bg_image(LEGACY)))
        else:
            write_page(LEGACY, pid, disp, vis)
    write_pages_json(LEGACY, order, order[0])
    brand_report(LEGACY)
    return order


if __name__ == "__main__":
    mo = build_modeled()
    rp = build_legacy()
    print("MODELED pages:", len(mo))
    print("LEGACY pages:", len(rp), "| measures:", len(RP_MEASURES))
