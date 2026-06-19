# CLAUDE.md — project context for Claude Code

## What this is

A **Microsoft Fabric demo** proving that a properly modeled, AI-described semantic model beats
legacy, undermodeled tables — judged by the answers two Fabric **Data Agents** (instructed-legacy and
modeled) give over the *same data*. Two semantic models, one lakehouse:

- **MultiSource_Legacy** — 17 legacy tables exactly as five source systems exported them (mixed
  naming, almost no relationships, no measures, no descriptions).
- **MultiSource_Modeled** — the same data, conformed by one notebook into a governed star with
  relationships, measures, descriptions, and Prep-for-AI instructions.

This is the **MultiSource Legacy-vs-Modeled** demo.
Honest positioning: legacy query speed is identical and is *not* the pitch — the wins are
accuracy, fewer hallucinations, fewer clarification round-trips, and that v2 is produced from
the customer's own legacy tables by one notebook.

**Narrative:** an industrial-supplies distributor just acquired **Lakeside Supply Co.** (legacy
Access/Excel, weekly stock counts, DD/MM/YYYY text dates, own product codes). It also runs a
service department (`ITM-` codes), a helpdesk SaaS (free-text product names), and sells on the
**MegaMart** marketplace (own listings, settlement fees). Leadership wants combined answers
*now*, before any integration finishes.

## Your job and how to behave

**Build this in Fabric from an EMPTY workspace, one step at a time, confirming after each.**
The ordered steps are in **`PLAN.md`** — follow it top to bottom.

**The loop (non-negotiable):** for every step — (1) say what you'll do, (2) do exactly that one
step, (3) show the result and check its *done-when*, (4) **⛔ STOP and wait for the user to say
"next".** Never batch steps. Never skip a STOP. If a command errors, show it, try the stated
fallback **once**, then STOP and ask — do not improvise around the Fabric portal/API.

Nothing exists in Fabric yet. You are creating all of it.

## Capability split — what you can and can't do

The `fabric-cli` (`fab`) is installed and Fabric credentials are available, so you do real work
via CLI for most of the build. Data Agents have **no CLI/API creation path** on this license, so
that last phase is portal work where you prepare the exact inputs and the user clicks.

- **CLI / REST API (you run):** Phases 1–5.
  - Folders: `fab mkdir` does NOT support nested paths → use Fabric REST API (`POST /v1/workspaces/{id}/folders`). Bootstrap.sh provides `make_folders_api` as the correct fallback.
  - Lakehouse: `POST /v1/workspaces/{id}/lakehouses` (REST API).
  - Upload CSVs: `fab cp` does NOT work for local→Fabric → use OneLake DFS API (ADLS Gen2 endpoint, Azure storage token from `az account get-access-token --resource https://storage.azure.com/`).
  - Table load: `fab table load` works; use flat path `"WS/lakehouse.Lakehouse/Tables/name"`.
  - Notebook: `fab import` to workspace root + REST move to folder; requires `artifact.content.ipynb` (UTF-8, no BOM). Cold start ~3 min on F4; total run ~12 min.
  - Semantic models: `fab import` to workspace root + REST move; TMDL must be UTF-8 no-BOM, no `ref table` lines, no inline column `///` descriptions. `deploy_models.py` handles all of this.
- **Portal (you prepare, user clicks):** Phase 6.
  - Data Agent item creation works via `POST /v1/workspaces/{ws}/dataAgents` but datasource attachment requires portal Save/Publish (no public API). Create via API, open in portal, add datasource, Save.
  - **"Add AI instructions (preview)"** on a semantic model (Prep for AI): portal-only. No REST API endpoint or TMDL annotation works for this field.
  - SupplyAgent_Legacy is legacy data with **heavy agent-side instructions** (`fabric/agent-config/SupplyAgent_Legacy_instructions.md`) — the instructions-only experiment. Point it at the **lakehouse `lh_supply_demo` SQL endpoint** (T-SQL), not the Legacy model, or the instructions can't steer query generation.
- **Phases 1–6 scope = the two agents:** SupplyAgent_Legacy (instructed legacy) and
  SupplyAgent_Modeled (modeled). **Phase 7 (added after the original scope)** =
  two matching Power BI reports in `pbip/` (one per agent, same 12 questions, for a visual
  side-by-side). Still **out of scope:** verified answers, **Teams/Copilot Studio**, and
  **answering the 12 eval questions** (that's the live demo, done by a human).

## Fixed facts (use exactly these)

- Workspace **Microsoft Fabric Demo Stand** → folder **data-model-comparison** → subfolder
  **Option B**. *Every* object lives in **Option B**.
- Capacity **fabricassesmentcoe** — the workspace is already on it; do **not** assign capacity.
- Names: lakehouse **lh_supply_demo** · models **MultiSource_Legacy** / **MultiSource_Modeled** ·
  notebook **build_modeled_layer** · agents **SupplyAgent_Legacy** / **SupplyAgent_Modeled** ·
  conformed tables **c_*** · legacy tables keep their source names.
- Data window **2025-06-01 → 2026-05-31**; Lakeside acquisition **2026-02-01**.

## Repo map

```
.
├── CLAUDE.md                       ← you are here (context + rules)
├── PLAN.md                         ← the ordered, confirm-after-each build plan — follow this
├── README.md                       ← human overview
├── requirements.txt                ← numpy, pandas, openpyxl (local only)
├── .env.example                    ← config template → copy to .env (git-ignored) and fill in
├── data/                           ← the 17 legacy multi-source CSVs — SAMPLE only (see data/README.md)
├── scripts/
│   └── build_modeled_layer.py      ← the conformance notebook as cell-delimited .py (portal paste)
├── fabric/                         ← everything deployed to Fabric
│   ├── bootstrap.sh                ← Phase 0–1: auth, folders, lakehouse (fab, with api fallback)
│   ├── upload_and_load.sh          ← Phase 2–3: upload CSVs (OneLake DFS) + fab table load
│   ├── generate_model_tmdl.py      ← emits the two .SemanticModel TMDL folders
│   ├── deploy_models.py            ← Phase 5: inject lakehouse SQL endpoint (from .env) + fab import
│   ├── render_notebook.py          ← Phase 4: inject lakehouse/workspace IDs (from .env) into a deploy copy
│   ├── models/                     ← MultiSource_Legacy / MultiSource_Modeled .SemanticModel (TMDL)
│   ├── notebooks/build_modeled_layer.Notebook/  ← importable notebook source (placeholders)
│   └── agent-config/               ← Phase 6 paste-text (Prep-for-AI, agent instructions)
├── pbip/                           ← Phase 7: two Power BI reports (PBIR) over the deployed models
│   ├── build_reports.py            ← generator: emits every page/visual for both reports
│   ├── legacy/                   ← report_legacy → MultiSource_Legacy + report-level DAX (forces all 12)
│   └── modeled/                    ← report_modeled → MultiSource_Modeled (governed measures)
├── eval/MultiSourceAgent_Eval.xlsx ← 12-question workbook — BLANK template (.filled.xlsx is git-ignored)
├── build_data_layer.md             ← plain-English explanation of the star-schema grouping
├── history.md / history.uk.md      ← demo narrative (EN / UK) for presenting
└── docs/GUIDE_MULTISOURCE_DEMO.md  ← reference: schema, relationships, measures, instruction rationale
```

Config: all environment-specific values (workspace/folder/lakehouse IDs, SQL endpoint, optional
service-principal creds) live in a git-ignored **`.env`** (copy from `.env.example`). Tracked TMDL
and the notebook artifact keep placeholders (`__SQL_ENDPOINT__`, `__LAKEHOUSE_ID__`, …); the deploy
and render scripts inject the real values into git-ignored `.deploy_*` working copies.

## Environment & licenses (✓ = Viktor has it)

- ✓ Workspace **Microsoft Fabric Demo Stand** on **F4 fabricassesmentcoe** (West Europe — a
  supported Copilot region; no cross-geo toggle)
- ✓ **fabric-cli (`fab`)** installed, **Fabric credentials available** (service principal or
  interactive login)
- ✓ **Capacity admin** on the F4
- ✓ **Free license + Fabric trial** → Direct Lake, item creation in this trial-capacity
  workspace, Data Agent creation, M365 Copilot consumption
- ✗ **XMLA write** (needs Pro/PPU) → linguistic-schema **synonyms unavailable**, and TOM-based
  tools (Tabular Editor, sempy_labs measure edits) won't write. **This is why models are
  deployed via TMDL definition import (REST, not XMLA), and the fallback is portal web
  modeling** — both avoid XMLA. Descriptions live in the TMDL itself, so they don't need XMLA.
- ✗ **Copilot Studio / Teams publishing** — out of scope anyway

Key Fabric behaviour: the Data Agent's DAX generator reads **only the model's
Prep-for-AI instructions**, not agent-level instructions. So **data semantics, period logic,
conformance rules → Prep-for-AI** (`fabric/agent-config/MultiSource_Modeled_prep_for_ai.md`);
**response style → agent instructions** (`…_agent_instructions.md`).

## Known sharp edges

**Phase 2 — CSV upload:** `fab cp` does not support local→Fabric copies. Use the OneLake DFS API
(ADLS Gen2) with a storage token from `az account get-access-token --resource https://storage.azure.com/`.
Three-step per file: create (`PUT ?resource=file`), append (`PATCH ?action=append`), flush (`PATCH ?action=flush`).

**Phase 4 — Notebook bugs fixed (2026-06):** Two Spark analysis errors were in the original notebook:
1. `lsp_full` join used `ls_p.LSP_CODE == lsp2sku.lsp_code` (expression join) → both `LSP_CODE`
   columns kept → ambiguous reference. Fixed: `join(lsp2sku, on="LSP_CODE", how="left/left_anti")`.
2. `ServiceWorkOrders.join(itm2sku, t("ServiceWorkOrders").ItemCode == itm2sku.itm_code)` called
   `t()` twice → two different attribute IDs → `MISSING_ATTRIBUTES` error. Fixed:
   `join(itm2sku.withColumnRenamed("itm_code","ItemCode"), on="ItemCode", how="left")`.
Both fixes are in `scripts/build_modeled_layer.py` and the importable notebook.

**Phase 4 — Capacity:** F4 cold Spark start is ~3 min; total notebook run ~12 min. If the
capacity auto-pauses mid-run (`CapacityNotActive` / `System_Cancelled_Session_Statements_Failed`),
resume via Fabric Admin portal → capacity → Resume, then rerun the notebook.

**Phase 5 — TMDL import:** `fab import` works but the TMDL must be:
- UTF-8 without BOM (use `encode("utf-8")`, not `Set-Content -Encoding UTF8` which adds BOM)
- No `ref table` lines in `model.tmdl` (Fabric's importer rejects `ReferenceObject` line type)
- No inline `///` descriptions inside column blocks (causes `InvalidLineType` parse error)
`deploy_models.py` enforces all three automatically.

**Phase 6 — Data Agents:** Agent item creation works via `POST /v1/workspaces/{ws}/dataAgents`
but `DataAgentNotPublished` blocks datasource configuration until the user opens and Saves in
the portal. No public API publish endpoint exists.

**Phase 6 — Prep-for-AI "Add AI instructions":** Portal-only. `getDefinition`/`updateDefinition`
TMDL annotations do not map to this preview field.

**Phase 7 — PBIR reports (`pbip/`):** Reports use `byConnection` (live connect) to the published
models; `build_reports.py` regenerates every page/visual deterministically. Two sharp edges:
1. **Report-level (extension) measures** (legacy's `reportExtensions.json`) must be referenced
   in every `visual.json` with `SourceRef: {"Schema": "extension", "Entity": <home table>}`.
   Omit `Schema: "extension"` and Power BI resolves the measure against the *model*, fails, and
   raises **`Missing_References`**. `build_reports.py` emits it automatically (its `extension=True`
   path); model measures (modeled report) and plain columns must NOT carry it. The modeled
   report uses no report-level measures (governed model measures only).
2. A paused capacity surfaces as **`CapacityNotActive`** (HTTP 404 on `…/workspaceandmodel`) and
   breaks every live-connected visual — resume the F4 before opening the reports.

## Gold answers (from the full dataset; for the live demo, not this build)

Q4 total May-2026 sales **$10.054M** (ERP 8.382 + MM net 0.622 + Lakeside 1.051) · Q5 marketplace
net **$7.335M** (gross 8.534, 14% fees) · Q8 A-class + open complaints + stockout risk →
**SKU-0014 Titan Rocker Switch 20A + SKU-0045 Titan Solenoid Valve 1in** · Q9 sell-through
Lakeside **2.85×** vs DCs **1.70×** · Q10 03/02/2026 = Feb 3 **$36,836** (misparse Mar 2 = $44,972).
Full set + scoring in `eval/MultiSourceAgent_Eval.xlsx`.

## Planted traps (each = a v1 failure mode)

Stockout rate raised 0.02% → **2.06%** (A/B-concentrated); two quality SKUs (0014, 0045) carry
the multi-hop thread; helpdesk `productRef` free-text (~8% misspelled, ~4% blank); marketplace
gross-vs-net (14% fees) + ~10 stale listings + 2 dual-listing SKUs; Lakeside DD/MM/YYYY text
dates, weekly counts, own LSP codes, 10 store-brand-only items; `sku_xref_master` ~95% complete
with 3 TODO gaps + 1 retired-SKU + 2 conflict rows. The notebook materializes **115 products**
(100 SKUs + 13 LSX + 2 UNMAPPED/UNRESOLVED) — the 3 TODO gaps stay unmapped **on purpose**
(governed conformance surfaces gaps instead of guessing); that's why Lakeside-mapped coverage is
71%, not 100%. Demoable, not a bug.

## Drift rule

Change the `c_` schema in the notebook → re-run `fabric/generate_model_tmdl.py` so the Modeled
TMDL still matches. Change the `c_` schema or measures → resync the numbers in
`eval/MultiSourceAgent_Eval.xlsx` and `docs/GUIDE_MULTISOURCE_DEMO.md`. Change a table/column/
measure either model exposes → re-run `pbip/build_reports.py` so the reports' field bindings stay
valid (it verifies every bound field against the deployed model's columns).
