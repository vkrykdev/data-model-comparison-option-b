#!/usr/bin/env python3
"""
Phase 4 helper — regenerate the build_modeled_layer notebook and render an import-ready copy.

Single source of truth for the conformance logic is `scripts/build_modeled_layer.py`
(cell-delimited, portal-paste friendly). This script first regenerates the tracked
`artifact.content.ipynb` from it (so the CLI-import form and the portal-paste form can never
drift), then renders a deploy copy with real IDs injected.

The tracked notebook (fabric/notebooks/build_modeled_layer.Notebook/) keeps placeholders
(__LAKEHOUSE_ID__, __LAKEHOUSE_NAME__, __WORKSPACE_ID__) so no environment-specific IDs
live in version control. This script copies the folder to a git-ignored sibling
'.deploy_build_modeled_layer.Notebook/' and injects the real IDs from .env, ready for:

    fab import "<workspace>.Workspace/build_modeled_layer.Notebook" \
        -i fabric/notebooks/.deploy_build_modeled_layer.Notebook -f

Usage:
    python fabric/render_notebook.py
"""
import json, os, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "fabric" / "notebooks" / "build_modeled_layer.Notebook"
OUT = ROOT / "fabric" / "notebooks" / ".deploy_build_modeled_layer.Notebook"
NOTEBOOK_SOURCE = ROOT / "scripts" / "build_modeled_layer.py"
IPYNB = SRC / "artifact.content.ipynb"

# Notebook-level metadata kept with placeholders (real IDs are injected into the deploy copy).
NB_METADATA = {
    "kernelspec": {"display_name": "Synapse PySpark", "language": "Python", "name": "synapse_pyspark"},
    "language_info": {"name": "python"},
    "dependencies": {"lakehouse": {
        "default_lakehouse": "__LAKEHOUSE_ID__",
        "default_lakehouse_name": "__LAKEHOUSE_NAME__",
        "default_lakehouse_workspace_id": "__WORKSPACE_ID__",
    }},
}
_CELL_MARKER = re.compile(r"^#\s*=+\s*CELL\b")


def generate_ipynb():
    """Rebuild artifact.content.ipynb from scripts/build_modeled_layer.py.

    Cells are split on the `# ==== CELL N — title` markers (the marker line itself is dropped);
    text before the first marker becomes the header cell. Output matches Fabric's notebook
    definition format (UTF-8, no BOM, indent=1) so `fab import` accepts it unchanged.
    """
    if not NOTEBOOK_SOURCE.exists():
        sys.exit(f"{NOTEBOOK_SOURCE} not found.")
    cells, cur = [], []
    for line in NOTEBOOK_SOURCE.read_text(encoding="utf-8").split("\n"):
        if _CELL_MARKER.match(line):
            cells.append(cur)
            cur = []
        else:
            cur.append(line)
    cells.append(cur)

    def trim(block):
        while block and block[0].strip() == "":
            block.pop(0)
        while block and block[-1].strip() == "":
            block.pop()
        return block

    cells = [c for c in (trim(b) for b in cells) if c]

    def to_source(block):
        return [ln + "\n" for ln in block[:-1]] + [block[-1]]

    nb = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "metadata": NB_METADATA,
        "cells": [
            {"cell_type": "code", "execution_count": None, "metadata": {"language": "python"},
             "outputs": [], "source": to_source(c)}
            for c in cells
        ],
    }
    IPYNB.write_bytes(json.dumps(nb, indent=1, ensure_ascii=False).encode("utf-8"))
    print(f"Regenerated {IPYNB.relative_to(ROOT)} ({len(cells)} cells) from {NOTEBOOK_SOURCE.relative_to(ROOT)}")


def load_env(path: Path = ROOT / ".env"):
    """Minimal .env loader (no external dependency). Existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def require(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"Missing required config '{name}'. Copy .env.example to .env and fill it in.")
    return v


def main():
    generate_ipynb()  # keep the .ipynb in sync with scripts/build_modeled_layer.py
    load_env()
    subs = {
        "__LAKEHOUSE_ID__": require("FABRIC_LAKEHOUSE_ID"),
        "__LAKEHOUSE_NAME__": require("FABRIC_LAKEHOUSE_NAME"),
        "__WORKSPACE_ID__": require("FABRIC_WORKSPACE_ID"),
    }
    if not SRC.exists():
        sys.exit(f"{SRC} not found.")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT)
    for f in OUT.rglob("*"):
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8")
        new = text
        for token, value in subs.items():
            new = new.replace(token, value)
        if new != text:
            f.write_bytes(new.encode("utf-8"))  # UTF-8 without BOM (fab import requirement)
    print(f"Rendered import-ready notebook -> {OUT.relative_to(ROOT)}")
    print("Now import it (flat workspace path), then move to the Option B folder. See PLAN.md 4.1.")


if __name__ == "__main__":
    main()
