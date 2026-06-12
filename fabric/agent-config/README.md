# agent-config

The text to paste when creating the three data agents in the portal (Phase 6 — the build's
stop point). Data agents have no CLI/API creation path on this license, so this phase is
portal work; these files are the exact inputs.

- `MultiSource_Modeled_prep_for_ai.md` — model-level Prep-for-AI for MultiSource_Modeled
- `SupplyAgent_Modeled_agent_instructions.md` — agent-level style instructions
- `SupplyAgent_Raw_setup.md` — how to wire the bare Raw agent (no instructions)
- `SupplyAgent_Raw_Plus_instructions.md` — **experiment:** raw data + heavy agent-side
  instructions (table docs, conformance recipe, conventions, example SQL). Tests whether
  instructions alone — no model optimization — can rescue raw-data answers. Best run against
  the `lh_supply_demo` SQL endpoint (T-SQL), not the relationship-less Raw semantic model.

Scope ends when all three agents exist with the above applied. No report, no verified answers,
no Teams, no answering the 12 eval questions — those are the live demo / later.
