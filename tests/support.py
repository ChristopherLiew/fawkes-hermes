"""Shared helpers for the skill tests. Standard library only (docs/DEVELOPMENT.md → Python)."""
from __future__ import annotations

import importlib.util
import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE = os.environ.get("SKILLS_LIVE") == "1"


def load_script(skill: str, name: str):
    """Import skills/<skill>/scripts/<name>.py as a module, without writing bytecode into the skill dir."""
    path = SKILLS / skill / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"skill_{name}", path)
    module = importlib.util.module_from_spec(spec)
    import sys
    dont_write, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = dont_write
    return module


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def load_env_local() -> None:
    """Load KEY=value lines from the gitignored .env.local for live tests (never overrides the real env)."""
    path = ROOT / ".env.local"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def live(*env: str):
    """Skip unless SKILLS_LIVE=1 and every named variable is set (CI never sets either)."""
    if LIVE:
        load_env_local()
    missing = [e for e in env if not os.environ.get(e)]
    return unittest.skipUnless(LIVE and not missing, "live test: set SKILLS_LIVE=1 (and " + (", ".join(env) or "no key") + ")")
