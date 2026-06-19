# DEPLOY.md — enroll this demo in your own Fabric workspace

The one-page checklist for a team standing this demo up from scratch. It's the **what to run, in
what order**; `PLAN.md` has the full per-step detail, done-when checks, and fallbacks (each step
below links to its PLAN.md phase). `CLAUDE.md` explains *why* each step is CLI vs portal.

> The build is **CLI for Phases 0–5 and 7**, **portal for Phase 6** (Data Agents and Prep-for-AI
> have no creation API on this license). Nothing is pre-provisioned — you create all of it.

## 0. Prerequisites

- **fabric-cli** (`fab --version`) and **Azure CLI** (`az version`) installed and on PATH.
- **Python 3** + deps: `pip install -r requirements.txt`.
- A Fabric workspace on a capacity you administer (the reference build uses **F4
  fabricassesmentcoe**, West Europe — a Copilot-supported region).
- The **full** legacy CSVs. `data/` ships *sample* tables (fact tables truncated to ~10 rows) for
  structure only — see [`data/README.md`](data/README.md). Supply complete tables for a real build.

## 1. Configure (once)

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
# then edit .env — fill in every value
```

`.env` is git-ignored and holds all environment-specific values (workspace name + GUID, capacity,
folder GUID, lakehouse name + GUID, SQL endpoint, optional `FAB_CLIENT_*` service-principal creds).
Tracked TMDL/notebook artifacts keep placeholders; the deploy/render scripts inject the real values
into git-ignored `.deploy_*` copies. See the table in [`README.md`](README.md#configuration-required-before-any-fabric-step)
for which script reads which variables.

## 2. Run, in order

| # | Run | What it does | PLAN.md |
|---|-----|--------------|---------|
| 1 | `python fabric/generate_model_tmdl.py` | Emit the two `.SemanticModel` TMDL folders | [0.3](PLAN.md) |
| 2 | `source fabric/bootstrap.sh && auth` | Authenticate `fab` (SP or interactive) | [0.4](PLAN.md) |
| 3 | `make_folders` (then `make_folders_api` if needed) · `make_lakehouse` | Create the **Option B** folder + `lh_supply_demo` lakehouse | [1.1–1.2](PLAN.md) |
| 4 | `source fabric/upload_and_load.sh` → upload + `load` | Upload the 17 CSVs (OneLake DFS API) and `fab table load` them to Delta | [2.1, 3.1](PLAN.md) |
| 5 | `python fabric/render_notebook.py` → `fab import …` | Regenerate the notebook `.ipynb` from `scripts/build_modeled_layer.py`, inject IDs, import to Option B | [4.1](PLAN.md) |
| 6 | `fab job run …` (or **Run all** in portal) | Build the conformed `c_*` star (~12 min; ~3 min cold start) | [4.2](PLAN.md) |
| 7 | `python fabric/deploy_models.py --resolve` then `--model Legacy` / `--model Modeled` | Deploy both semantic models via TMDL import | [5.1–5.3](PLAN.md) |
| 8 | **Portal — Phase 6** (see below) | Create the two Data Agents | [6.1–6.3](PLAN.md) |
| 9 | `python pbip/build_reports.py` | Regenerate the two Power BI reports (resume the F4 first) | [7.1–7.2](PLAN.md) |

## 3. Portal-only steps (Phase 6 — can't be scripted)

These have no public API path on this license; do them by hand in the Fabric portal:

1. **Prep-for-AI** on `MultiSource_Modeled`: open the model → *Prep for AI* → paste
   `fabric/agent-config/MultiSource_Modeled_prep_for_ai.md` into **"Add AI instructions (preview)"** → save.
2. **SupplyAgent_Modeled**: create in Option B → add data source **MultiSource_Modeled** → paste
   `fabric/agent-config/SupplyAgent_Modeled_agent_instructions.md` → **Save**.
3. **SupplyAgent_Legacy**: create in Option B → add data source **`lh_supply_demo` SQL analytics
   endpoint** (T-SQL, *not* the Legacy model) → paste
   `fabric/agent-config/SupplyAgent_Legacy_instructions.md` → **Save**.

(Data Agent items can be created via `POST /v1/workspaces/{ws}/dataAgents`, but datasource
attachment requires the portal Save/Publish — that's why these stay manual.)

## Done

Both agents exist (Legacy instructed, Modeled governed) over the same lakehouse, plus two matching
Power BI reports. The 12-question walkthrough in `eval/MultiSourceAgent_Eval.xlsx` is scored live by
a human during the demo — it is **not** part of enrollment.
