# agent-config

The text to paste when creating the two data agents in the portal (Phase 6 — the build's
stop point). Data agents have no CLI/API creation path on this license, so this phase is
portal work; these files are the exact inputs.

- `MultiSource_Modeled_prep_for_ai.md` — model-level Prep-for-AI for MultiSource_Modeled
- `SupplyAgent_Modeled_agent_instructions.md` — agent-level style instructions
- `SupplyAgent_Legacy_instructions.md` — **experiment (Path A, preferred):** legacy data + heavy
  agent-side instructions (table docs, conformance recipe, conventions, example SQL) over the
  `lh_supply_demo` SQL endpoint (T-SQL). Tests whether instructions alone — no model
  optimization — can rescue legacy-data answers. The SQL endpoint supports example queries and
  data-source instructions, so the full recipe applies.
- `SupplyAgent_Legacy_instructions_semanticmodel.md` — **Path B (semantic-model / DAX variant):**
  use only if the agent is wired to the `MultiSource_Legacy` semantic model instead of the SQL
  endpoint. Deliberately weaker: the Legacy model has just four ERP-internal relationships, so
  cross-source questions can't be joined and must be declined, and a semantic-model source
  exposes no example-queries field. Path A is preferred; this variant is the honest fallback.

Scope ends when both agents exist with the above applied. No report, no verified answers,
no Teams, no answering the 12 eval questions — those are the live demo / later.
