# PLAN.md — build plan for the Claude Code agent

You (Haiku 4.5 / Sonnet 4.6) will build this demo in Microsoft Fabric **from an empty
workspace**, one step at a time. **Read `CLAUDE.md` first** for context, the CLI-vs-portal
split, and the hard rules. Then work this plan top to bottom.

## The loop (non-negotiable)

For **every** step below:
1. State the step number and what you're about to do.
2. Do exactly that one step (run the command, or give the precise portal action).
3. Show the result and check the **done-when**.
4. **⛔ STOP. Post the result and wait for the user to say "next" (or "confirmed").**
   Do not start the next step until they reply.

Never batch steps. Never skip a STOP. If a command errors, show the error, try the stated
fallback **once**, and if it still fails, STOP and ask — do not improvise around Fabric.

## Capability split (see CLAUDE.md for detail)

- **CLI / REST API (you run):** Phases 1–5 — folders (REST API), lakehouse (REST API), upload
  CSVs (OneLake DFS API — `fab cp` does NOT work), table load (`fab table load`), notebook
  (Fabric Items API + `fab import`), both semantic models (`fab import` via REST move).
- **Portal (you prepare, the user clicks):** Phase 6 — both data agents (item creation works
  via API but datasource attachment requires a portal Save/Publish), and Prep-for-AI "Add AI
  instructions" (portal-only — no REST or TMDL API path exists for this preview field).
  You hand the user the exact text from `fabric/agent-config/`.
- **Scope ends when both agents exist with instructions applied.** No report, no verified
  answers, no Teams, no answering the 12 eval questions (that's the live demo).

## Fixed facts

- Workspace **Microsoft Fabric Demo Stand** → folder **data-model-comparison** → subfolder
  **Option B**. Everything lives in *Option B*. Capacity **fabricassesmentcoe** (workspace is
  already on it — no capacity assignment).
- Lakehouse **lh_supply_demo** · models **MultiSource_Raw**, **MultiSource_Modeled** ·
  notebook **build_modeled_layer** · agents **SupplyAgent_Raw**, **SupplyAgent_Modeled**.

---

## Phase 0 — Local prep & auth

**0.1** Confirm tooling: `fab --version`, `python --version`. Then
`pip install -r requirements.txt`.
*Done-when:* `fab` and Python 3 respond; deps install.
⛔ STOP.

**0.1b** Create local config: `cp .env.example .env` (PowerShell `Copy-Item .env.example .env`),
then fill in every value (workspace name + GUID, capacity, folder GUID, lakehouse name + GUID,
SQL endpoint; `FAB_CLIENT_*` only for service-principal auth). `.env` is git-ignored — never commit it.
The scripts (`bootstrap.sh`, `upload_and_load.sh`, `deploy_models.py`, `render_notebook.py`) read it.
*Done-when:* `.env` exists with real values; `bash -c 'source fabric/bootstrap.sh' ` defines `$WS`/`$LH`.
⛔ STOP.

**0.2** Generate local data and prove the gold answers (no Fabric yet):
`python scripts/generate_data.py && python scripts/validate_gold_answers.py`.
*Done-when:* 17 CSVs in `data/`; validator prints Q1–Q12 and exits 0 (Q8 → SKU-0014 + SKU-0045).
⛔ STOP.

**0.3** Generate the model TMDL: `python fabric/generate_model_tmdl.py`.
*Done-when:* `fabric/models/MultiSource_Raw.SemanticModel/` and `…_Modeled.SemanticModel/` exist.
⛔ STOP.

**0.4** Authenticate to Fabric. `source fabric/bootstrap.sh && auth` (set `FAB_CLIENT_ID/SECRET/TENANT_ID`
for a service principal, or run `fab auth login` interactively).
*Done-when:* `fab auth status` shows the identity.
⛔ STOP.

**0.5** Confirm the workspace is reachable: `check_ws` (i.e. `fab ls "Microsoft Fabric Demo Stand.Workspace"`).
*Done-when:* the workspace lists (may be empty).
⛔ STOP.

## Phase 1 — Folders & lakehouse

**1.1** Create folders: `make_folders` (CLI). If they don't appear, run `make_folders_api` once.
*Done-when:* `fab ls ".../data-model-comparison"` shows the **Option B** subfolder.
⛔ STOP.

**1.2** Create the lakehouse: `make_lakehouse`.
*Done-when:* `fab ls ".../Option B"` shows **lh_supply_demo.Lakehouse**.
⛔ STOP.

## Phase 2 — Upload raw CSVs

**2.1** Upload the 17 CSVs to `Files/raw/` using the **OneLake DFS API** (ADLS Gen2).
`fab cp` does **not** work for local→Fabric uploads. Use PowerShell `Invoke-RestMethod` against
`https://onelake.dfs.fabric.microsoft.com/{workspaceId}/{lakehouseId}/Files/raw/` with an
Azure storage token (`az account get-access-token --resource https://storage.azure.com/`).
For each file: PUT `?resource=file`, PATCH `?action=append&position=0`, PATCH `?action=flush&position={size}`.
*Done-when:* `fab ls ".../lh_supply_demo.Lakehouse/Files/raw"` (or API equivalent) lists 17 files.
⛔ STOP.

## Phase 3 — Load CSVs → Delta tables

**3.1** `load` — `fab table load` each CSV into `Tables/`.
*Done-when:* `fab ls ".../lh_supply_demo.Lakehouse/Tables"` lists 17 tables.
⛔ STOP.

**3.2** Verify the date trap survived: `verify_dates`.
*Done-when:* `LS_SALES_EXPORT.SALE_DATE` and `LS_STOCK_COUNT.COUNT_DATE` are **string**, not date.
(If a loader coerced them to date, reload those two with the date columns forced to string,
or note it — the notebook re-parses defensively.)
⛔ STOP.

## Phase 4 — Build the modeled layer (notebook)

**4.1** Create the notebook **build_modeled_layer** in the Option B folder.
- First render an import-ready copy with the lakehouse/workspace IDs injected from `.env`:
  `python fabric/render_notebook.py` → writes the git-ignored
  `fabric/notebooks/.deploy_build_modeled_layer.Notebook/`.
- `fab import` uses the **flat workspace path** (nested folder paths are unsupported):
  `fab import "$FABRIC_WORKSPACE_NAME.Workspace/build_modeled_layer.Notebook" -i fabric/notebooks/.deploy_build_modeled_layer.Notebook -f`
  then move to Option B via REST API: `POST /v1/workspaces/{ws}/items/{id}/move`
- The import folder contains `artifact.content.ipynb` — a valid UTF-8 (no BOM) `.ipynb` JSON file.
  The tracked copy keeps placeholders (`__LAKEHOUSE_ID__`, `__WORKSPACE_ID__`); `render_notebook.py`
  substitutes the real IDs. The metadata carries `default_lakehouse` by ID and workspace ID.
- After import, `fab job run` needs ~3 min cold start on F4; full run ~12 min. If the
  capacity auto-pauses mid-run (`CapacityNotActive`), resume via Fabric Admin portal and rerun.
- If import fails: create in portal (New notebook in Option B), attach **lh_supply_demo**, paste cells.
*Done-when:* the notebook exists in Option B and opens.
⛔ STOP.

**4.2** Run it: `fab job run ".../Option B/build_modeled_layer.Notebook" -C '{"defaultLakehouse":{"name":"lh_supply_demo"}}'`
(or **Run all** in the portal).
*Done-when:* the run succeeds and Cell 9 prints all `c_*` row counts as **OK**
(`c_dim_product` = 115, `c_fact_sales_unified` = 193,500, `c_fact_inventory` = 195,220).
⛔ STOP.

## Phase 5 — Deploy the two semantic models  ⚠ highest-risk phase

**5.1** Resolve the lakehouse SQL endpoint: `python fabric/deploy_models.py --resolve`.
*Done-when:* it prints a non-empty SQL endpoint and lakehouse id. If empty, grab them from the
portal (Lakehouse → Settings → SQL analytics endpoint → Connection string) and note them.
⛔ STOP.

**5.2** Deploy **MultiSource_Raw**: `python fabric/deploy_models.py --model Raw`.
`deploy_models.py` imports to workspace root then moves via REST API (nested paths unsupported).
TMDL constraints enforced automatically by the script: UTF-8 no-BOM, no `ref table` lines,
no inline column `///` descriptions inside column blocks.
*Done-when:* model appears in Option B and opens without a connection error.
**If import fails twice → Phase 5b fallback (Raw):** portal → New semantic model over
`lh_supply_demo` → select the **17 raw tables** → save. Add nothing else.
⛔ STOP.

**5.3** Deploy **MultiSource_Modeled**: `python fabric/deploy_models.py --model Modeled`.
Same constraints as 5.2.
*Done-when:* model appears, opens, shows the 9 `c_*` tables, relationships, and measures.
**If import fails twice → Phase 5b fallback (Modeled):** portal → New semantic model over
`lh_supply_demo` → select the **9 c_ tables** → then add relationships, 14 measures, and
descriptions from `docs/GUIDE_MULTISOURCE_DEMO.md` §"Modeled model".
⛔ STOP.

**5.4** Sanity-check parity (optional but recommended): in each model's web view, sum
`gross_amount` (Raw) vs the `Revenue Gross` measure (Modeled) for the full window — same
underlying data, so totals must agree.
⛔ STOP.

## Phase 6 — Create both data agents (portal; you prepare the inputs)

**6.1** Create **SupplyAgent_Raw** in Option B → add data source **MultiSource_Raw** → **no
instructions**. Follow `fabric/agent-config/SupplyAgent_Raw_setup.md`.
Agent item creation works via `POST /v1/workspaces/{ws}/dataAgents`; BUT datasource attachment
requires a portal Save/Publish step (no public API path). Create the item via API, then open in
the portal, add MultiSource_Raw, and Save.
**SupplyAgent_Raw intentionally has ZERO instructions** — it is the bare baseline.
Adding instructions defeats the demo contrast.
*Done-when:* the agent exists, points at MultiSource_Raw, has zero instructions.
⛔ STOP.

**6.2** Apply Prep-for-AI to **MultiSource_Modeled**: open the model → Prep for AI → in the
**"Add AI instructions (preview)"** box paste the instruction text from
`fabric/agent-config/MultiSource_Modeled_prep_for_ai.md`; confirm AI data schema includes all
9 `c_*` tables + measures.
**This field is portal-only** — no REST API endpoint and no TMDL annotation path exists for it.
*Done-when:* the Prep-for-AI instructions are saved on the model.
⛔ STOP.

**6.3** Create **SupplyAgent_Modeled** in Option B → add data source **MultiSource_Modeled** →
paste the agent instructions from `fabric/agent-config/SupplyAgent_Modeled_agent_instructions.md`.
Same portal publish step as 6.1.
*Done-when:* the agent exists, points at MultiSource_Modeled, has the style instructions.
⛔ STOP.

**✅ DONE.** Both agents exist with instructions. Development scope complete. The 12-question
walkthrough (`eval/MultiSourceAgent_Eval.xlsx`) is for the live demo, not this build.

---

## If something drifts

If you change `scripts/generate_data.py`, re-run `validate_gold_answers.py` and resync the
numbers in `eval/MultiSourceAgent_Eval.xlsx` and `docs/GUIDE_MULTISOURCE_DEMO.md`. If you
change the `c_` schema in the notebook, re-run `fabric/generate_model_tmdl.py` so the Modeled
TMDL still matches.
