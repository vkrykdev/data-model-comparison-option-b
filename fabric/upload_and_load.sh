#!/usr/bin/env bash
# Phase 2-3 — upload the 17 legacy CSVs to the lakehouse, then load each into a Delta table.
# Source the same CONFIG as bootstrap.sh (or copy the vars). One step per PLAN.md gate.
set -euo pipefail

# Environment-specific values come from .env (git-ignored). Copy .env.example -> .env first.
ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a; # shellcheck disable=SC1090
  source "$ENV_FILE"; set +a
else
  echo "ERROR: $ENV_FILE not found. Copy .env.example to .env and fill it in." >&2
  return 1 2>/dev/null || exit 1
fi
WS="${FABRIC_WORKSPACE_NAME:?set FABRIC_WORKSPACE_NAME in .env}"
FOLDER1="${FABRIC_FOLDER_PARENT:?}"; FOLDER2="${FABRIC_FOLDER_SUB:?}"; LH="${FABRIC_LAKEHOUSE_NAME:?}"
# NOTE: nested folder paths (FOLDER1/FOLDER2) are NOT supported by fab CLI for most commands.
# For fab table load, use the flat lakehouse path: "$WS.Workspace/$LH.Lakehouse"
LHP="$WS.Workspace/$LH.Lakehouse"   # flat path — fab resolves by name across workspace
LHP_NESTED="$WS.Workspace/$FOLDER1/$FOLDER2/$LH.Lakehouse"  # kept for reference only

TABLES=(products suppliers locations sales_order_lines inventory_daily \
        ServiceWorkOrders ServicePartsUsage hdTickets hdCategories \
        mm_orders mm_listings mm_settlements \
        LS_SALES_EXPORT LS_PRODUCT_LIST LS_STORES LS_STOCK_COUNT \
        sku_xref_master)

# ---------- STEP 2: upload CSVs to Files/raw/ ----------
# IMPORTANT: `fab cp` does NOT work for local→Fabric file uploads.
# Use the OneLake DFS API (ADLS Gen2) instead. Run this PowerShell snippet:
#
#   $token = az account get-access-token --resource https://storage.azure.com/ --query accessToken -o tsv
#   $WS_ID = $env:FABRIC_WORKSPACE_ID   # or: fab get "$env:FABRIC_WORKSPACE_NAME.Workspace" -q id
#   $LH_ID = $env:FABRIC_LAKEHOUSE_ID   # or: fab api "workspaces/$WS_ID/lakehouses" (find $env:FABRIC_LAKEHOUSE_NAME)
#   $base  = "https://onelake.dfs.fabric.microsoft.com/$WS_ID/$LH_ID/Files/raw"
#   $stdH  = @{ "Authorization"="Bearer $token"; "x-ms-version"="2023-01-03" }
#   Invoke-RestMethod -Uri "$base`?resource=directory" -Method Put -Headers $stdH | Out-Null
#   foreach ($t in @("products","suppliers",...)) {
#     $bytes = [IO.File]::ReadAllBytes(".\data\$t.csv")
#     $url   = "$base/$t.csv"
#     Invoke-RestMethod -Uri "${url}?resource=file"                          -Method Put   -Headers $stdH | Out-Null
#     $aH = $stdH.Clone(); $aH["Content-Type"] = "application/octet-stream"
#     Invoke-RestMethod -Uri "${url}?action=append&position=0"               -Method Patch -Headers $aH -Body $bytes | Out-Null
#     Invoke-RestMethod -Uri "${url}?action=flush&position=$($bytes.Length)" -Method Patch -Headers $stdH | Out-Null
#     Write-Host "OK $t.csv"
#   }
upload() {
  echo "ERROR: 'fab cp' does not support local->Fabric file uploads."
  echo "Use the OneLake DFS API (PowerShell snippet above). See PLAN.md Phase 2."
  return 1
}

# ---------- STEP 3: load each CSV into a Delta table ----------
# CRITICAL: keep LS_SALES_EXPORT.SALE_DATE and LS_STOCK_COUNT.COUNT_DATE as STRING (the date trap).
# `fab table load` infers types from the CSV header; verify with `fab table schema` after.
load() {
  for t in "${TABLES[@]}"; do
    echo "loading table $t"
    fab table load "$LHP/Tables/$t" --file "Files/raw/$t.csv" --mode overwrite --format csv
  done
  fab ls "$LHP/Tables"         # done-when: 17 tables listed
}

# spot-check the date columns stayed textual
verify_dates() {
  fab table schema "$LHP/Tables/LS_SALES_EXPORT"  | grep -i sale_date
  fab table schema "$LHP/Tables/LS_STOCK_COUNT"   | grep -i count_date
}

echo "Functions: upload, load, verify_dates. Run one at a time per PLAN.md."
