#!/usr/bin/env bash
# Phase 0-1 — auth + create the folder path and lakehouse.
# Run from the repo root. Edit the CONFIG block, then run section by section
# (the PLAN.md loop runs ONE step at a time and confirms after each — don't run blind).
set -euo pipefail

# ============================ CONFIG ============================
# All environment-specific values live in .env (git-ignored). Copy .env.example -> .env
# and fill it in. We export every var so child processes (az/fab) see them too.
ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a; # shellcheck disable=SC1090
  source "$ENV_FILE"; set +a
else
  echo "ERROR: $ENV_FILE not found. Copy .env.example to .env and fill it in." >&2
  return 1 2>/dev/null || exit 1
fi

WS="${FABRIC_WORKSPACE_NAME:?set FABRIC_WORKSPACE_NAME in .env}"
FOLDER1="${FABRIC_FOLDER_PARENT:?set FABRIC_FOLDER_PARENT in .env}"   # top folder
FOLDER2="${FABRIC_FOLDER_SUB:?set FABRIC_FOLDER_SUB in .env}"         # subfolder — everything lives here
LH="${FABRIC_LAKEHOUSE_NAME:?set FABRIC_LAKEHOUSE_NAME in .env}"      # lakehouse name
CAPACITY="${FABRIC_CAPACITY_NAME:-}"                                  # for reference; workspace already on it
# Auth: either a service principal (set FAB_CLIENT_* in .env) or interactive `fab auth login`.
: "${FAB_CLIENT_ID:=}"; : "${FAB_CLIENT_SECRET:=}"; : "${FAB_TENANT_ID:=}"

WSP="$WS.Workspace"
OBJ="$WSP/$FOLDER1/$FOLDER2"               # path prefix for all Option B items

# ---------- STEP 0a: authenticate ----------
auth() {
  if [[ -n "$FAB_CLIENT_ID" ]]; then
    fab auth login -u "$FAB_CLIENT_ID" -p "$FAB_CLIENT_SECRET" --tenant "$FAB_TENANT_ID"
  else
    fab auth login           # interactive / device code
  fi
  fab auth status
}

# ---------- STEP 0b: confirm workspace is reachable ----------
check_ws() { fab ls "$WSP"; }   # done-when: command succeeds and lists items

# ---------- STEP 1a: create the two nested folders ----------
# NOTE: `fab mkdir` does NOT support nested folder paths — it always returns [InvalidPath].
# Use make_folders_api directly (the REST API approach always works).
make_folders() {
  echo "WARNING: fab mkdir does not support nested paths. Running make_folders_api instead."
  make_folders_api
}
make_folders_api() {
  WSID=$(fab get "$WSP" -q id)
  # fab api uses lowercase method names: post, not POST
  PID=$(fab api "workspaces/$WSID/folders" --method post -i "{\"displayName\":\"$FOLDER1\"}" -q 'id' 2>/dev/null || \
        fab api "workspaces/$WSID/folders" | python3 -c "import sys,json; d=json.load(sys.stdin); print(next(f['id'] for f in d.get('value',[]) if f['displayName']=='$FOLDER1'))" 2>/dev/null || true)
  fab api "workspaces/$WSID/folders" --method post -i "{\"displayName\":\"$FOLDER2\",\"parentFolderId\":\"$PID\"}" || true
  echo "Folders created (or already exist). Verify in portal."
}

# ---------- STEP 1b: create the lakehouse inside Option B ----------
# NOTE: `fab create` with a nested path fails. Use the Fabric REST API directly.
make_lakehouse() {
  WSID=$(fab get "$WSP" -q id)
  OPTB_ID=$(fab api "workspaces/$WSID/folders" | python3 -c "import sys,json; d=json.load(sys.stdin); print(next(f['id'] for f in d.get('value',[]) if f['displayName']=='$FOLDER2'))")
  TOKEN=$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)
  curl -s -X POST "https://api.fabric.microsoft.com/v1/workspaces/$WSID/lakehouses" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"displayName\":\"$LH\",\"folderId\":\"$OPTB_ID\"}" | python3 -c "import sys,json; r=json.load(sys.stdin); print('Created lakehouse:',r.get('id','ERROR'),r.get('displayName',''))"
}

echo "Functions defined: auth, check_ws, make_folders[/_api], make_lakehouse."
echo "PLAN.md drives these one at a time. To run a single step manually, e.g.:  source fabric/bootstrap.sh && auth"
