# agent-config

The text to paste when creating the two data agents in the portal (Phase 6 — the build's
stop point). Data agents have no CLI/API creation path on this license, so this phase is
portal work; these files are the exact inputs.

- `MultiSource_Modeled_prep_for_ai.md` — model-level Prep-for-AI for MultiSource_Modeled
- `SupplyAgent_Modeled_agent_instructions.md` — agent-level style instructions
- `SupplyAgent_Legacy_instructions.md` — **the experiment:** legacy data + heavy agent-side
  instructions (table docs, conformance recipe, conventions, example SQL) over the
  `lh_supply_demo` SQL endpoint (T-SQL). Tests whether instructions alone — no model
  optimization — can rescue legacy-data answers. The SQL endpoint supports example queries and
  data-source instructions, so the full recipe applies. (Wire it to the SQL endpoint, not the
  `MultiSource_Legacy` semantic model: a semantic-model source generates DAX that agent
  instructions can't steer, and the Legacy model has only four ERP-internal relationships.)

Scope ends when both agents exist with the above applied. No report, no verified answers,
no Teams, no answering the 12 eval questions — those are the live demo / later.
