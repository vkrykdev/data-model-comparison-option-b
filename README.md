# Fabric Data Agent demo — Raw vs Well-Modeled (Option B)

Two Fabric **Data Agents** over the *same* lakehouse data prove that modeling + an AI layer beats
raw tables. **MultiSource_Raw** = 17 raw source tables as-landed; **MultiSource_Modeled** = the
same data conformed by one notebook into a governed star with measures, descriptions, and
Prep-for-AI. The wins are accuracy, fewer hallucinations, fewer clarification round-trips, and
lower tokens per correct answer — not raw speed.

Built **from an empty Fabric workspace**, mostly via `fabric-cli`, with the two data agents
created in the portal at the end.

## For the build agent (Claude Code)

1. Read **`CLAUDE.md`** — context, the CLI-vs-portal capability split, and the hard rules.
2. Follow **`PLAN.md`** — ordered steps, one at a time, **confirming after each** (`⛔ STOP`
   gates). Scope ends when both data agents exist with instructions.

## Local quickstart (no Fabric needed)

```bash
pip install -r requirements.txt
python fabric/generate_model_tmdl.py     # emits the two .SemanticModel TMDL folders
```

> `data/` ships **sample** raw tables (large fact tables truncated to header + 10 rows) for
> structure illustration — see [`data/README.md`](data/README.md). The full synthetic dataset
> is not committed; supply complete raw tables to the lakehouse for the actual build (PLAN.md
> Phase 2–3).

## Configuration (required before any Fabric step)

All environment-specific values (workspace name + GUID, capacity, folder/lakehouse IDs, SQL
endpoint, optional service-principal credentials) live in a **git-ignored `.env`** file — they
are **never** committed. Copy the template and fill in your own values:

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
# then edit .env
```

The build scripts load `.env` automatically:

| Script | Reads from `.env` |
|---|---|
| `fabric/bootstrap.sh`, `fabric/upload_and_load.sh` | workspace/folder/lakehouse/capacity names, optional `FAB_CLIENT_*` |
| `fabric/deploy_models.py` | workspace name + GUID, folder GUID, lakehouse name, SQL endpoint |
| `fabric/render_notebook.py` | lakehouse ID/name, workspace ID (injected into the notebook copy) |

Required variables (see `.env.example` for descriptions and how to obtain each):

```
FABRIC_WORKSPACE_NAME   FABRIC_WORKSPACE_ID    FABRIC_CAPACITY_NAME
FABRIC_FOLDER_PARENT    FABRIC_FOLDER_SUB      FABRIC_OPTB_FOLDER_ID
FABRIC_LAKEHOUSE_NAME   FABRIC_LAKEHOUSE_ID    FABRIC_SQL_ENDPOINT
FAB_CLIENT_ID           FAB_CLIENT_SECRET      FAB_TENANT_ID   # optional (service principal)
```

Tracked files (TMDL, the notebook artifact) carry placeholders like `__SQL_ENDPOINT__` and
`__LAKEHOUSE_ID__`; the deploy/render scripts inject the real values from `.env` into git-ignored
`.deploy_*` working copies at build time.

## Layout

| Path | What |
|---|---|
| `PLAN.md` | the ordered, confirm-after-each build plan |
| `CLAUDE.md` | full context + rules for the build agent |
| `data/` | the 17 raw multi-source tables — **sample** (see `data/README.md`) |
| `scripts/` | `build_modeled_layer.py` — the conformance notebook as cell-delimited `.py` |
| `fabric/` | bootstrap + upload/load + TMDL generator + deploy/render scripts + model/notebook/agent definitions |
| `eval/MultiSourceAgent_Eval.xlsx` | 12-question gold-answer workbook — **live-demo reference only** |
| `docs/GUIDE_MULTISOURCE_DEMO.md` | reference: schema, relationships, measures, AI-layer rationale, Phase 5b fallback |

## Environment

Workspace **Microsoft Fabric Demo Stand** → folder **data-model-comparison** → subfolder
**Option B**, on **F4 fabricassesmentcoe** (West Europe). Free license + Fabric trial,
`fabric-cli` installed, Fabric credentials available, capacity admin on the F4. Out of scope:
Teams/Copilot Studio, reports, verified answers, and answering the eval questions. See `CLAUDE.md`
for license details (notably: no XMLA → models deploy via TMDL import / portal, no synonyms).

All data is synthetic.
