#!/usr/bin/env python3
"""
Phase 5 — deploy the two semantic models.
Resolves the lakehouse SQL analytics endpoint + id, writes them into each model's
expressions.tmdl (replacing __SQL_ENDPOINT__ / __DATABASE__), then `fab import`.

This is the highest-risk phase (Direct Lake TMDL import). If a model import fails twice,
STOP and use the portal fallback in docs/GUIDE_MULTISOURCE_DEMO.md §Phase 5b.

Usage:
    python fabric/deploy_models.py --resolve        # just print the endpoint/id it found
    python fabric/deploy_models.py --model Legacy       # inject + import MultiSource_Legacy
    python fabric/deploy_models.py --model Modeled    # inject + import MultiSource_Modeled
"""
import argparse, json, os, re, subprocess, sys, shutil, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "fabric" / "models"

def load_env(path: Path = ROOT / ".env"):
    """Minimal .env loader (no external dependency). Existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)

def require(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"Missing required config '{name}'. Copy .env.example to .env and fill it in.")
    return v

load_env()
WS = require("FABRIC_WORKSPACE_NAME")
FOLDER = f'{require("FABRIC_FOLDER_PARENT")}/{require("FABRIC_FOLDER_SUB")}'
LH = require("FABRIC_LAKEHOUSE_NAME")
WS_ID = require("FABRIC_WORKSPACE_ID")
OPTB_FOLDER_ID = require("FABRIC_OPTB_FOLDER_ID")
SQL_ENDPOINT = os.environ.get("FABRIC_SQL_ENDPOINT", "").strip()  # optional; resolved via API if blank
LHP = f"{WS}.Workspace/{LH}.Lakehouse"     # flat path for fab (nested folder paths unsupported)
OBJ = f"{WS}.Workspace"                    # import to WS root, then move via REST API

def fab(cmd):
    r = subprocess.run(["fab", "-c", cmd], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
    return r.stdout.strip(), r.returncode

def get_az_token():
    r = subprocess.run(
        ["az", "account", "get-access-token", "--resource", "https://api.fabric.microsoft.com",
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, shell=True)
    return r.stdout.strip()

def fabric_api(path, method="GET", body=None, token=None):
    token = token or get_az_token()
    req = urllib.request.Request(
        f"https://api.fabric.microsoft.com{path}",
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def resolve():
    """Return (sql_endpoint, database_id) from the Fabric REST API."""
    token = get_az_token()
    items, _ = fabric_api(f"/v1/workspaces/{WS_ID}/items", token=token)
    lh = next((i for i in items["value"] if i["type"] == "Lakehouse" and i["displayName"] == LH), None)
    if not lh:
        if SQL_ENDPOINT:
            print("Lakehouse not found via API. Falling back to FABRIC_SQL_ENDPOINT from .env.")
            return SQL_ENDPOINT, LH
        print("Lakehouse not found via API and FABRIC_SQL_ENDPOINT is unset in .env.")
        return "", LH
    lh_detail, _ = fabric_api(f"/v1/workspaces/{WS_ID}/lakehouses/{lh['id']}", token=token)
    ep = lh_detail.get("properties", {}).get("sqlEndpointProperties", {}).get("connectionString", "")
    if not ep and SQL_ENDPOINT:
        ep = SQL_ENDPOINT  # fall back to the value configured in .env
    print(f"lakehouse id      : {lh['id']}")
    print(f"SQL endpoint      : {ep or '<not found>'}")
    if not ep:
        print("\nCould not resolve. Set FABRIC_SQL_ENDPOINT in .env, or get it from the portal"
              " (Lakehouse > Settings > SQL analytics endpoint).")
    return ep, LH

def inject(model_dir: Path, endpoint: str, database: str):
    """Inject SQL endpoint, remove ref table lines, and ensure UTF-8 no-BOM on all TMDL files."""
    import codecs
    for tmdl in model_dir.rglob("*.tmdl"):
        content = tmdl.read_text(encoding="utf-8-sig")  # strip BOM if present
        content = content.replace("__SQL_ENDPOINT__", endpoint).replace("__DATABASE__", database)
        # Fabric importer rejects 'ref table' lines; tables are auto-discovered
        content = re.sub(r'(?m)^\s*ref table [^\n]+\n', '', content)
        # Fabric importer rejects /// inside column blocks; strip them
        content = re.sub(r'(?m)^\t{2,}///[^\n]*\n', '', content)
        tmdl.write_bytes(content.encode("utf-8"))   # UTF-8 without BOM
    print(f"  injected connection into {model_dir.relative_to(ROOT)} (UTF-8 no-BOM, cleaned)")

def deploy(model_short: str):
    name = f"MultiSource_{model_short}"
    src = MODELS / f"{name}.SemanticModel"
    if not src.exists():
        sys.exit(f"{src} not found — run `python fabric/generate_model_tmdl.py` first.")
    # work on a copy so the repo's placeholders stay clean for re-runs
    work = MODELS / f".deploy_{name}.SemanticModel"
    if work.exists(): shutil.rmtree(work)
    shutil.copytree(src, work)
    ep, db = resolve()
    if not ep:
        sys.exit("No SQL endpoint resolved; fill it manually or use the portal fallback (Phase 5b).")
    inject(work, ep, db)
    # fab import uses flat WS path (nested folder paths unsupported); move via REST API after
    out, rc = fab(f'import "{OBJ}/{name}.SemanticModel" -i "{work}" -f')
    print(out)
    if rc != 0:
        print(f"\nIMPORT FAILED for {name}. Retry once; if it fails again, use Phase 5b portal fallback.")
        return
    # Move to Option B folder
    token = get_az_token()
    items, _ = fabric_api(f"/v1/workspaces/{WS_ID}/items", token=token)
    sm = next((i for i in items["value"] if i["type"] == "SemanticModel"
               and i["displayName"] == name and not i.get("folderId")), None)
    if sm:
        r, code = fabric_api(f"/v1/workspaces/{WS_ID}/items/{sm['id']}/move", "POST",
                              {"targetFolderId": OPTB_FOLDER_ID}, token=token)
        print(f"  moved to Option B folder (folderId={r['value'][0]['folderId'] if code==200 else '?'})")
    else:
        print("  WARNING: could not find model at WS root to move — may already be in the right place.")
    print(f"\nOK: {name} in Option B. Open in portal to verify tables and connection load.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolve", action="store_true")
    ap.add_argument("--model", choices=["Legacy", "Modeled"])
    a = ap.parse_args()
    if a.resolve: resolve()
    elif a.model: deploy(a.model)
    else: ap.print_help()
