# Fabric notebook source


# METADATA ********************

# META {
# META   "kernel_info": { "name": "synapse_pyspark" },
# META   "dependencies": {
# META     "lakehouse": { "default_lakehouse_name": "lh_supply_demo" }
# META   }
# META }


# CELL ********************

# Fabric notebook: build_modeled_layer  (MultiSource_Modeled conformance transform)
# Attach lakehouse lh_supply_demo as DEFAULT, then Run all (or `fab job run`).
# Reads the 17 legacy tables as-landed; writes conformed c_* Delta tables in lh_supply_demo.
# Same data in, governed star out — nothing is invented, only conformed.

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }


# CELL ********************

from pyspark.sql import functions as F

def t(name):
    return spark.read.table(name)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }


# CELL ********************

xref = t("sku_xref_master")
xref_clean = (xref
    .filter(~F.coalesce(F.col("notes"), F.lit("")).contains("retired"))
    .filter(~F.coalesce(F.col("notes"), F.lit("")).contains("CONFLICT")))   # primary listing wins

lsp2sku  = xref_clean.filter("lsp_code  IS NOT NULL AND lsp_code  != ''").select("lsp_code",  "sku")
itm2sku  = xref_clean.filter("itm_code  IS NOT NULL AND itm_code  != ''").select("itm_code",  "sku")
list2sku = xref_clean.filter("mm_listing_id IS NOT NULL AND mm_listing_id != ''") \
                     .select(F.col("mm_listing_id").alias("listingId"), "sku")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }


# CELL ********************

c_dim_date = spark.sql("""
SELECT CAST(date_format(d, 'yyyyMMdd') AS INT)            AS date_key,
       CAST(d AS DATE)                                    AS date,
       year(d) AS year, quarter(d) AS quarter, month(d) AS month,
       date_format(d, 'MMMM') AS month_name,
       CAST(date_format(d, 'yyyyMM') AS INT)              AS month_key,
       day(d) AS day, date_format(d, 'EEEE') AS day_of_week,
       dayofweek(d) IN (1, 7)                             AS is_weekend,
       year(d) AS fiscal_year,
       concat('FY', year(d), '-Q', quarter(d))            AS fiscal_quarter,
       d >= DATE'2026-02-01'                              AS is_post_acquisition
FROM (SELECT explode(sequence(DATE'2025-06-01', DATE'2026-05-31', INTERVAL 1 DAY)) AS d)
""")
c_dim_date.write.format("delta").mode("overwrite").saveAsTable("c_dim_date")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }


# CELL ********************

prod = t("products")
ls_p = t("LS_PRODUCT_LIST")

erp_products = (prod
    .join(t("suppliers").select("supplier_key", "supplier_name"), "supplier_key", "left")
    .join(xref_clean.groupBy("sku").agg(
        F.max("itm_code").alias("itm_code"),
        F.max("lsp_code").alias("lsp_code"),
        F.max("mm_listing_id").alias("mm_listing_id")), "sku", "left")
    .select("sku", "product_name", "category", "subcategory", "brand", "abc_class",
            "standard_unit_cost", "list_price", "supplier_name",
            "itm_code", "lsp_code", "mm_listing_id")
    .withColumn("is_lakeside_only", F.lit(False)))

lakeside_only = (ls_p.join(lsp2sku, on="LSP_CODE", how="left_anti")
    .select(F.concat(F.lit("LSX-"), F.substring("LSP_CODE", 5, 4)).alias("sku"),
            F.initcap("PROD_DESC").alias("product_name"),
            F.lit("Lakeside Store Brand").alias("category"),
            F.lit("Store Brand").alias("subcategory"), F.lit("Lakeside").alias("brand"),
            F.lit("C").alias("abc_class"),
            F.lit(None).cast("double").alias("standard_unit_cost"),
            F.col("UNIT_PRICE").alias("list_price"),
            F.lit("Lakeside Supply Co.").alias("supplier_name"),
            F.lit(None).cast("string").alias("itm_code"),
            F.col("LSP_CODE").alias("lsp_code"),
            F.lit(None).cast("string").alias("mm_listing_id"))
    .withColumn("is_lakeside_only", F.lit(True)))

special = spark.createDataFrame(
    [("UNMAPPED",  "Unmapped marketplace listing", "Unknown"),
     ("UNRESOLVED","Unresolved ticket reference",  "Unknown")],
    "sku string, product_name string, category string") \
    .select("sku", "product_name", "category",
            F.lit("Unknown").alias("subcategory"), F.lit("Unknown").alias("brand"),
            F.lit("C").alias("abc_class"),
            F.lit(None).cast("double").alias("standard_unit_cost"),
            F.lit(None).cast("double").alias("list_price"),
            F.lit(None).cast("string").alias("supplier_name"),
            F.lit(None).cast("string").alias("itm_code"),
            F.lit(None).cast("string").alias("lsp_code"),
            F.lit(None).cast("string").alias("mm_listing_id"),
            F.lit(False).alias("is_lakeside_only"))

erp_products.unionByName(lakeside_only).unionByName(special) \
    .write.format("delta").mode("overwrite").saveAsTable("c_dim_product")

# LSP -> conformed sku (mapped SKUs + LSX fallback), reused below
lsp_full = (ls_p.select("LSP_CODE", "PROD_DESC")
    .join(lsp2sku, on="LSP_CODE", how="left")
    .withColumn("c_sku", F.coalesce("sku",
        F.concat(F.lit("LSX-"), F.substring("LSP_CODE", 5, 4))))
    .select("LSP_CODE", "PROD_DESC", "c_sku"))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }


# CELL ********************

loc = t("locations").select(
    "location_id", "location_name", "region", "location_type", "country",
    F.lit("ERP").alias("source"))
ls_loc = t("LS_STORES").select(
    F.col("STORE_CODE").alias("location_id"),
    F.initcap("STORE_NAME").alias("location_name"),
    F.initcap("REGION").alias("region"),
    F.lit("Retail Store").alias("location_type"),
    F.lit("USA").alias("country"), F.lit("Lakeside").alias("source"))
mm_loc = spark.createDataFrame(
    [("LOC-MM", "MegaMart Marketplace", "Online", "Marketplace", "USA", "MegaMart")],
    loc.schema)
loc.unionByName(ls_loc).unionByName(mm_loc) \
    .write.format("delta").mode("overwrite").saveAsTable("c_dim_location")

spark.createDataFrame(
    [("Online",), ("Retail",), ("Wholesale",), ("Marketplace",), ("Lakeside",)],
    "channel string").write.format("delta").mode("overwrite").saveAsTable("c_dim_channel")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }


# CELL ********************

erp_sales = t("sales_order_lines").select(
    F.lit("ERP").alias("source"), "date_key", "sku", "location_id", "channel",
    F.col("qty_sold").alias("qty"),
    F.round(F.col("qty_sold") * F.col("unit_price"), 2).alias("gross_amount"),
    F.round(F.col("qty_sold") * F.col("unit_price"), 2).alias("net_amount"))

mm_sales = (t("mm_orders").alias("o")
    .join(t("mm_settlements").select("mmOrderId", "payoutAmount"), "mmOrderId")
    .join(list2sku, "listingId", "left")
    .select(F.lit("MegaMart").alias("source"),
            F.date_format("orderDate", "yyyyMMdd").cast("int").alias("date_key"),
            F.coalesce("sku", F.lit("UNMAPPED")).alias("sku"),
            F.lit("LOC-MM").alias("location_id"),
            F.lit("Marketplace").alias("channel"),
            F.col("qty"),
            F.col("grossAmount").alias("gross_amount"),
            F.col("payoutAmount").alias("net_amount")))

ls_sales = (t("LS_SALES_EXPORT")
    .withColumn("d", F.to_date("SALE_DATE", "dd/MM/yyyy"))        # THE date fix
    .join(lsp_full, "PROD_DESC", "left")
    .select(F.lit("Lakeside").alias("source"),
            F.date_format("d", "yyyyMMdd").cast("int").alias("date_key"),
            F.col("c_sku").alias("sku"),
            F.col("STORE_CODE").alias("location_id"),
            F.lit("Lakeside").alias("channel"),
            F.col("QTY").alias("qty"),
            F.col("TOTAL_AMT").alias("gross_amount"),
            F.col("TOTAL_AMT").alias("net_amount")))

erp_sales.unionByName(mm_sales).unionByName(ls_sales) \
    .write.format("delta").mode("overwrite").saveAsTable("c_fact_sales_unified")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }


# CELL ********************

erp_inv = t("inventory_daily").select(
    "date_key", "sku", "location_id", "on_hand_qty", "safety_stock", "is_stockout",
    F.lit("daily").alias("grain"), F.lit("ERP").alias("source"))
ls_inv = (t("LS_STOCK_COUNT")
    .withColumn("d", F.to_date("COUNT_DATE", "dd/MM/yyyy"))
    .join(lsp_full.select("LSP_CODE", "c_sku"), "LSP_CODE")
    .select(F.date_format("d", "yyyyMMdd").cast("int").alias("date_key"),
            F.col("c_sku").alias("sku"),
            F.col("STORE_CODE").alias("location_id"),
            F.col("QTY_ON_HAND").alias("on_hand_qty"),
            F.lit(None).cast("long").alias("safety_stock"),
            (F.col("QTY_ON_HAND") == 0).cast("int").alias("is_stockout"),
            F.lit("weekly").alias("grain"), F.lit("Lakeside").alias("source")))
erp_inv.unionByName(ls_inv) \
    .write.format("delta").mode("overwrite").saveAsTable("c_fact_inventory")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }


# CELL ********************

(t("ServiceWorkOrders")
    .join(itm2sku.withColumnRenamed("itm_code", "ItemCode"), on="ItemCode", how="left")
    .select(F.col("WorkOrderID").alias("work_order_id"),
            F.date_format("OpenedDate", "yyyyMMdd").cast("int").alias("date_key"),
            F.coalesce("sku", F.lit("UNRESOLVED")).alias("sku"),
            F.col("WorkType").alias("work_type"), F.col("Status").alias("status"),
            F.col("LaborHours").alias("labor_hours"))
    .write.format("delta").mode("overwrite").saveAsTable("c_fact_service"))

(t("ServicePartsUsage")
    .join(itm2sku.withColumnRenamed("itm_code", "ItemCode"), on="ItemCode", how="left")
    .select(F.col("UsageID").alias("usage_id"),
            F.date_format("UsageDate", "yyyyMMdd").cast("int").alias("date_key"),
            F.coalesce("sku", F.lit("UNRESOLVED")).alias("sku"),
            F.col("QtyUsed").alias("qty_used"))
    .write.format("delta").mode("overwrite").saveAsTable("c_fact_service_parts"))

prod_names = t("products").select(
    F.upper(F.trim("product_name")).alias("ref_norm"), F.col("sku").alias("p_sku"))
(t("hdTickets")
    .withColumn("ref_norm", F.upper(F.trim(F.coalesce("productRef", F.lit("")))))
    .join(prod_names, "ref_norm", "left")
    .join(t("hdCategories"), "categoryId", "left")
    .select(F.col("ticketId").alias("ticket_id"),
            F.date_format(F.to_timestamp("createdAt"), "yyyyMMdd").cast("int").alias("date_key"),
            F.coalesce("p_sku", F.lit("UNRESOLVED")).alias("sku"),
            F.col("categoryName").alias("category"),
            (F.col("categoryId") == 1).alias("is_complaint"),
            (F.col("status") == "open").alias("is_open"),
            "priority")
    .write.format("delta").mode("overwrite").saveAsTable("c_fact_helpdesk"))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }


# CELL ********************

expected = {"c_dim_date": 365, "c_dim_product": 115, "c_dim_location": 10,
            "c_dim_channel": 5, "c_fact_sales_unified": 193500,
            "c_fact_inventory": 195220, "c_fact_service": 6000,
            "c_fact_service_parts": 9000, "c_fact_helpdesk": 12000}
# c_dim_product = 100 ERP SKUs + 13 LSX (10 store-brand + 3 with TODO gaps in the xref —
# the governed transform treats unverified mappings as unmapped, on purpose) + 2 special rows
for tab, exp in expected.items():
    n = spark.read.table(tab).count()
    print(f"{tab:24s} {n:>9,}  (expected {exp:,}) {'OK' if n == exp else '<<< CHECK'}")

print("\nConformance coverage:")
s = spark.read.table("c_fact_sales_unified")
print("  MM rows unmapped:", s.filter("source='MegaMart' AND sku='UNMAPPED'").count())
h = spark.read.table("c_fact_helpdesk")
print("  Tickets unresolved:", h.filter("sku='UNRESOLVED'").count(), "of", h.count())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

