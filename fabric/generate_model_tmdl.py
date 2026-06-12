"""
Generates importable PBIP/TMDL definitions for the two Direct Lake semantic models:
  fabric/models/MultiSource_Raw.SemanticModel/        (17 raw tables, ~no modeling)
  fabric/models/MultiSource_Modeled.SemanticModel/     (9 c_ tables, measures+desc+relationships)

Raw column lists are derived from data/*.csv dtypes; Modeled from the c_ schemas the
notebook produces — so dataType/sourceColumn match the lakehouse tables by construction.

The Direct Lake connection in expressions.tmdl uses placeholders __SQL_ENDPOINT__ and
__DATABASE__; fabric/deploy_models.py fills them from the live lakehouse before `fab import`.

This is the one phase that may need iteration on first import — see PLAN.md Phase 5 and the
portal fallback in docs/GUIDE_MULTISOURCE_DEMO.md. Re-run anytime: `python fabric/generate_model_tmdl.py`
"""
import pandas as pd, uuid, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "fabric" / "models"

def gid(): return str(uuid.uuid4())

def tmdl_type(dt):
    s = str(dt)
    if s.startswith("int"):     return "int64", "sum"
    if s.startswith("float"):   return "double", "sum"
    if s.startswith("bool"):    return "boolean", "none"
    if s.startswith("datetime"):return "dateTime", "none"
    return "string", "none"

KEYISH = lambda c: c.endswith("_key") or c.endswith("_id") or c in (
    "sku", "itm_code", "lsp_code", "mm_listing_id", "ItemCode", "listingId",
    "sellerSku", "LSP_CODE", "STORE_CODE", "mmOrderId", "settlementId",
    "WorkOrderID", "UsageID", "ticketId", "categoryId", "ReasonKey", "SALE_ID")

def col_block(name, dt, *, hidden=False, summ=None, desc=None, key=False):
    dtype, default_summ = tmdl_type(dt)
    summ = summ or ("none" if (key or KEYISH(name)) else default_summ)
    lines = [f"\tcolumn {q(name)}",
             f"\t\tdataType: {dtype}",
             f"\t\tsummarizeBy: {summ}",
             f"\t\tsourceColumn: {name}",
             f"\t\tlineageTag: {gid()}"]
    if hidden: lines.insert(1, "\t\tisHidden")
    # Note: column-level /// descriptions go BEFORE the column keyword (Fabric importer
    # rejects them when placed inside the column block)
    return "\n".join(lines)

def q(name):  # quote identifiers that aren't simple
    return name if name.replace("_", "").isalnum() and not name[0].isdigit() else f"'{name}'"

def table_file(table, columns, *, measures=None, table_desc=None):
    body = []
    if table_desc: body.append(f"/// {table_desc}")
    body.append(f"table {q(table)}")
    body.append(f"\tlineageTag: {gid()}\n")
    body.append("\n\n".join(columns))
    if measures:
        body.append("")
        body.append("\n\n".join(measures))
    body.append(f"""
\tpartition {q(table)} = entity
\t\tmode: directLake
\t\tsource
\t\t\tentityName: {table}
\t\t\texpressionSource: DatabaseQuery
""")
    return "\n".join(body)

def measure_block(name, dax, fmt=None, desc=None):
    lines = []
    if desc: lines.append(f"\t/// {desc}")
    lines.append(f"\tmeasure {q(name)} = {dax}")
    if fmt: lines.append(f'\t\tformatString: {fmt}')
    lines.append(f"\t\tlineageTag: {gid()}")
    return "\n".join(lines)

def write_model(name, tables_tmdl, refs, relationships_tmdl=""):
    d = OUT / f"{name}.SemanticModel"
    if d.exists(): shutil.rmtree(d)
    (d / "definition" / "tables").mkdir(parents=True)
    (d / ".platform").write_text(
        '{\n  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",\n'
        f'  "metadata": {{ "type": "SemanticModel", "displayName": "{name}" }},\n'
        f'  "config": {{ "version": "2.0", "logicalId": "{gid()}" }}\n}}\n')
    (d / "definition.pbism").write_text('{\n  "version": "4.2",\n  "settings": {}\n}\n')
    (d / "definition" / "expressions.tmdl").write_text(
        "expression DatabaseQuery =\n"
        "\t\tlet\n"
        '\t\t\tdatabase = Sql.Database("__SQL_ENDPOINT__", "__DATABASE__")\n'
        "\t\tin\n"
        "\t\t\tdatabase\n"
        f"\tlineageTag: {gid()}\n"
        "\tannotation PBI_IncludeFutureArtifacts = False\n")
    model = ["model Model",
             "\tculture: en-US",
             "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tdiscourageImplicitMeasures",
             "\tsourceQueryCulture: en-US",
             "",
             '\tannotation PBI_QueryOrder = ["DatabaseQuery"]',
             ""]
    # Fabric's TMDL importer does not support 'ref table' lines;
    # tables are auto-discovered from definition/tables/*.tmdl
    (d / "definition" / "model.tmdl").write_text("\n".join(model) + "\n")
    if relationships_tmdl:
        (d / "definition" / "relationships.tmdl").write_text(relationships_tmdl)
    for tname, content in tables_tmdl.items():
        (d / "definition" / "tables" / f"{tname}.tmdl").write_text(content + "\n")
    print(f"  wrote {name}.SemanticModel  ({len(tables_tmdl)} tables)")

# ============================================================ RAW model (17 tables)
RAW_TABLES = ["products","suppliers","locations","sales_order_lines","inventory_daily",
              "ServiceWorkOrders","ServicePartsUsage","hdTickets","hdCategories",
              "mm_orders","mm_listings","mm_settlements",
              "LS_SALES_EXPORT","LS_PRODUCT_LIST","LS_STORES","LS_STOCK_COUNT",
              "sku_xref_master"]
raw_tmdl = {}
for t in RAW_TABLES:
    df = pd.read_csv(DATA / f"{t}.csv", nrows=200)
    cols = [col_block(c, df[c].dtype) for c in df.columns]
    raw_tmdl[t] = table_file(t, cols)

# the 2-4 within-ERP same-name relationships auto-detect would plausibly create
# (cross-source joins via xref / LS codes / ITM / listings are DELIBERATELY absent)
raw_rels = "\n\n".join(
    f"relationship {gid()}\n\tfromColumn: {f}.{col}\n\ttoColumn: {tb}.{col}"
    for (f, tb, col) in [
        ("sales_order_lines","products","sku"),
        ("inventory_daily","products","sku"),
        ("sales_order_lines","locations","location_id"),
        ("inventory_daily","locations","location_id"),
    ]) + "\n"
write_model("MultiSource_Raw", raw_tmdl, RAW_TABLES, raw_rels)

# ============================================================ MODELED model (9 c_ tables)
# exact schemas the notebook produces (col -> pandas-style dtype)
C = {
 "c_dim_date": {"date_key":"int","date":"datetime","year":"int","quarter":"int","month":"int",
   "month_name":"str","month_key":"int","day":"int","day_of_week":"str","is_weekend":"bool",
   "fiscal_year":"int","fiscal_quarter":"str","is_post_acquisition":"bool"},
 "c_dim_product": {"sku":"str","product_name":"str","category":"str","subcategory":"str",
   "brand":"str","abc_class":"str","standard_unit_cost":"float","list_price":"float",
   "supplier_name":"str","itm_code":"str","lsp_code":"str","mm_listing_id":"str","is_lakeside_only":"bool"},
 "c_dim_location": {"location_id":"str","location_name":"str","region":"str","location_type":"str","country":"str","source":"str"},
 "c_dim_channel": {"channel":"str"},
 "c_fact_sales_unified": {"source":"str","date_key":"int","sku":"str","location_id":"str",
   "channel":"str","qty":"int","gross_amount":"float","net_amount":"float"},
 "c_fact_inventory": {"date_key":"int","sku":"str","location_id":"str","on_hand_qty":"int",
   "safety_stock":"int","is_stockout":"int","grain":"str","source":"str"},
 "c_fact_service": {"work_order_id":"str","date_key":"int","sku":"str","work_type":"str","status":"str","labor_hours":"float"},
 "c_fact_service_parts": {"usage_id":"str","date_key":"int","sku":"str","qty_used":"int"},
 "c_fact_helpdesk": {"ticket_id":"str","date_key":"int","sku":"str","category":"str","is_complaint":"bool","is_open":"bool","priority":"str"},
}
DESC_T = {
 "c_fact_sales_unified":"All sales unified: ERP, MegaMart marketplace (net = payout after ~14% fees; gross = before fees), and Lakeside stores. The source column identifies origin. sku='UNMAPPED' marks stale marketplace listings.",
 "c_fact_inventory":"On-hand snapshots. ERP locations are DAILY; Lakeside stores are WEEKLY (grain column). Stockout metrics use grain='daily' only.",
 "c_fact_helpdesk":"Helpdesk tickets resolved to SKUs by product name (~88% resolved; rest sku='UNRESOLVED'). is_complaint = 'Product complaint' category; is_open = still open.",
 "c_fact_service":"Service work orders; ITM- codes resolved to SKUs via the governed xref.",
 "c_fact_service_parts":"Service parts consumption; ITM- codes resolved to SKUs.",
 "c_dim_product":"One row per product: 100 corporate SKUs (with itm/lsp/listing codes), LSX-* Lakeside-local items, plus UNMAPPED/UNRESOLVED quality members.",
 "c_dim_date":"Marked date table. is_post_acquisition = on/after 2026-02-01 (Lakeside acquisition).",
 "c_dim_location":"DCs (ERP), Lakeside retail stores, and the marketplace pseudo-location.",
 "c_dim_channel":"Online / Retail / Wholesale / Marketplace / Lakeside.",
}
DESC_C = {
 "net_amount":"Net revenue (marketplace = payout after fees; ERP/Lakeside = gross).",
 "gross_amount":"Gross revenue before marketplace fees.",
 "source":"Origin system: ERP / MegaMart / Lakeside.",
 "grain":"Snapshot grain: 'daily' (ERP) or 'weekly' (Lakeside).",
 "is_post_acquisition":"TRUE on/after 2026-02-01 (Lakeside acquisition date).",
 "is_complaint":"TRUE when the ticket category is 'Product complaint'.",
 "is_open":"TRUE when the ticket is still open.",
}
HIDE = {"c_fact_sales_unified":["qty","gross_amount","net_amount"],
        "c_fact_inventory":["on_hand_qty","is_stockout"],
        "c_fact_service_parts":["qty_used"]}

modeled_measures = [
 measure_block("Revenue Gross", "SUM ( c_fact_sales_unified[gross_amount] )", "#,##0", "Gross revenue, all sources."),
 measure_block("Revenue Net", "SUM ( c_fact_sales_unified[net_amount] )", "#,##0", "Net revenue (marketplace net of fees)."),
 measure_block("Units Sold", "SUM ( c_fact_sales_unified[qty] )", "#,##0"),
 measure_block("ERP Revenue", 'CALCULATE ( [Revenue Net], c_fact_sales_unified[source] = "ERP" )', "#,##0"),
 measure_block("Marketplace Net Revenue", 'CALCULATE ( [Revenue Net], c_fact_sales_unified[source] = "MegaMart" )', "#,##0"),
 measure_block("Marketplace Gross Revenue", 'CALCULATE ( [Revenue Gross], c_fact_sales_unified[source] = "MegaMart" )', "#,##0"),
 measure_block("Lakeside Revenue", 'CALCULATE ( [Revenue Net], c_fact_sales_unified[source] = "Lakeside" )', "#,##0"),
 measure_block("Stockout Rate %",
   'DIVIDE ( CALCULATE ( SUM ( c_fact_inventory[is_stockout] ), c_fact_inventory[grain] = "daily" ), '
   'CALCULATE ( COUNTROWS ( c_fact_inventory ), c_fact_inventory[grain] = "daily" ) )', "0.0%",
   "Share of daily ERP snapshot rows in stockout."),
 measure_block("Avg On-Hand Units",
   'AVERAGEX ( VALUES ( c_dim_date[date_key] ), CALCULATE ( SUM ( c_fact_inventory[on_hand_qty] ) ) )', "#,##0"),
 measure_block("Sell-Through Ratio", "DIVIDE ( [Units Sold], [Avg On-Hand Units] )", "0.00"),
 measure_block("Tickets", "COUNTROWS ( c_fact_helpdesk )", "#,##0"),
 measure_block("Open Complaints",
   "CALCULATE ( [Tickets], c_fact_helpdesk[is_complaint] = TRUE, c_fact_helpdesk[is_open] = TRUE )", "#,##0",
   "Open tickets in the Product complaint category."),
 measure_block("Tickets per 1K Units", "DIVIDE ( [Tickets], [Units Sold] ) * 1000", "0.0"),
 measure_block("Parts per 100 Units", "DIVIDE ( SUM ( c_fact_service_parts[qty_used] ), [Units Sold] ) * 100", "0.0"),
]

modeled_tmdl = {}
for t, schema in C.items():
    cols = [col_block(c, dt, hidden=(c in HIDE.get(t, [])), desc=DESC_C.get(c))
            for c, dt in schema.items()]
    meas = modeled_measures if t == "c_fact_sales_unified" else None
    modeled_tmdl[t] = table_file(t, cols, measures=meas, table_desc=DESC_T.get(t))

modeled_rels = []
for fact in ["c_fact_sales_unified","c_fact_inventory","c_fact_service","c_fact_service_parts","c_fact_helpdesk"]:
    modeled_rels.append((fact,"c_dim_date","date_key"))
    modeled_rels.append((fact,"c_dim_product","sku"))
for fact in ["c_fact_sales_unified","c_fact_inventory"]:
    modeled_rels.append((fact,"c_dim_location","location_id"))
modeled_rels.append(("c_fact_sales_unified","c_dim_channel","channel"))
rels_tmdl = "\n\n".join(
    f"relationship {gid()}\n\tfromColumn: {f}.{c}\n\ttoColumn: {tb}.{c}"
    for (f, tb, c) in modeled_rels) + "\n"
write_model("MultiSource_Modeled", modeled_tmdl, list(C.keys()), rels_tmdl)

print("\nTMDL generated. Connection placeholders __SQL_ENDPOINT__ / __DATABASE__ are filled by deploy_models.py.")
