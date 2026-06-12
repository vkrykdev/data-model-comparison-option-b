#!/usr/bin/env python3
"""
Phase 4 helper — render an import-ready copy of the build_modeled_layer notebook.

The tracked notebook (fabric/notebooks/build_modeled_layer.Notebook/) keeps placeholders
(__LAKEHOUSE_ID__, __LAKEHOUSE_NAME__, __WORKSPACE_ID__) so no environment-specific IDs
live in version control. This script copies the folder to a git-ignored sibling
'.deploy_build_modeled_layer.Notebook/' and injects the real IDs from .env, ready for:

    fab import "<workspace>.Workspace/build_modeled_layer.Notebook" \
        -i fabric/notebooks/.deploy_build_modeled_layer.Notebook -f

Usage:
    python fabric/render_notebook.py
"""
import os, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "fabric" / "notebooks" / "build_modeled_layer.Notebook"
OUT = ROOT / "fabric" / "notebooks" / ".deploy_build_modeled_layer.Notebook"


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
