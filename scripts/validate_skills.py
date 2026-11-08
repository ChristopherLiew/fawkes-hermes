#!/usr/bin/env python3
"""Validate skills/ against the Hermes Agent SKILL.md conventions. Standard library only.

ERRORS (block the commit or CI run):
  - each skills/<name>/ has SKILL.md with '---' frontmatter: name, description, version
  - name is kebab-case, matches the directory name, and is unique; version is semver
  - description is at most 160 chars and the body is not empty
  - platforms (if set) only uses macos | linux | windows
  - relative files the body links to (references/, templates/, ...) exist, including ${HERMES_SKILL_DIR}/... paths
  - no hardcoded ~/.hermes paths (use ${HERMES_SKILL_DIR}; Hermes expands it at load time)
  - no symlinks, no file over 256 KiB, no loose files in skills/ except README.md, AGENTS.md, CLAUDE.md
WARNINGS (advisory, mirroring the Hermes skill linter):
  - description over 60 chars (keeps the level-0 skills_list index lean)
  - body over ~24k chars (oversized-body) or more than 60 files in references/ (references-sprawl)
  - a recommended section is missing: When to Use / Procedure / Pitfalls / Verification
  - a subdirectory outside references/ templates/ scripts/ examples/ assets/

Usage: python3 scripts/validate_skills.py [skills_dir] [--strict]   (--strict turns warnings into errors)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_BYTES = 256 * 1024
MAX_BODY_CHARS = 24_000
MAX_REFERENCES = 60
DESC_SOFT, DESC_HARD = 60, 160
NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
REQUIRED = ("name", "description", "version")
PLATFORMS = {"macos", "linux", "windows"}
SUBDIRS = {"references", "templates", "scripts", "examples", "assets"}
SECTIONS = ("When to Use", "Procedure", "Pitfalls", "Verification")
TOP_LEVEL_FILES = {"README.md", "AGENTS.md", "CLAUDE.md"}
LINK_RE = re.compile(r"(?<![\w/.-])((?:%s)/[\w./-]+)" % "|".join(sorted(SUBDIRS)))
SKILL_DIR_RE = re.compile(r"\$\{HERMES_SKILL_DIR\}/([\w./-]+)")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    """Return the top-level scalar keys and the body. Nested keys (metadata.hermes...) are skipped."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            meta: dict[str, str] = {}
            for raw in lines[1:i]:
                if not raw.strip() or raw.lstrip().startswith("#") or raw.startswith((" ", "\t", "-")):
                    continue
                key, sep, value = raw.partition(":")
                if sep:
                    meta[key.strip()] = value.split(" #")[0].strip().strip('"').strip("'")
            return meta, "\n".join(lines[i + 1 :])
    return None


def check_skill(d: Path, errors: list[str], warnings: list[str], seen: dict[str, Path]) -> None:
    skill = d / "SKILL.md"
    if not skill.is_file():
        errors.append(f"{d}: missing SKILL.md")
        return
    parsed = parse_frontmatter(skill.read_text(encoding="utf-8"))
    if parsed is None:
        errors.append(f"{skill}: missing or unterminated '---' frontmatter")
        return
    meta, body = parsed

    for key in REQUIRED:
        if not meta.get(key):
            errors.append(f"{skill}: frontmatter missing '{key}'")
    name = meta.get("name", "")
    if name and not NAME_RE.match(name):
        errors.append(f"{skill}: name '{name}' must be kebab-case (^[a-z][a-z0-9-]*$)")
    if name and name != d.name:
        errors.append(f"{skill}: name '{name}' must match directory '{d.name}'")
    if name in seen:
        errors.append(f"{skill}: duplicate name '{name}' (also {seen[name]})")
    seen[name] = skill
    version = meta.get("version", "")
    if version and not SEMVER_RE.match(version):
        errors.append(f"{skill}: version '{version}' must be X.Y.Z")

    desc = meta.get("description", "")
    if len(desc) > DESC_HARD:
        errors.append(f"{skill}: description is {len(desc)} chars (max {DESC_HARD})")
    elif len(desc) > DESC_SOFT:
        warnings.append(f"{skill}: description is {len(desc)} chars (aim for <= {DESC_SOFT})")

    plat = meta.get("platforms", "")
    if plat:
        values = {v.strip() for v in plat.strip("[]").split(",") if v.strip()}
        bad = values - PLATFORMS
        if bad:
            errors.append(f"{skill}: unknown platforms {sorted(bad)} (use {sorted(PLATFORMS)})")

    if not body.strip():
        errors.append(f"{skill}: empty body")
    if len(body) > MAX_BODY_CHARS:
        warnings.append(f"{skill}: body is {len(body)} chars (oversized-body > {MAX_BODY_CHARS}); move detail to references/")
    headings = {h.strip().lower() for h in re.findall(r"^#{2,3}\s+(.+)$", body, flags=re.M)}
    for section in SECTIONS:
        if section.lower() not in headings:
            warnings.append(f"{skill}: missing recommended section '## {section}'")

    if "~/.hermes" in body:
        errors.append(f"{skill}: hardcoded ~/.hermes path; use ${{HERMES_SKILL_DIR}}/...")
    for ref in sorted(set(LINK_RE.findall(body)) | set(SKILL_DIR_RE.findall(body))):
        ref = ref.rstrip(".,);:")
        if not (d / ref).exists():
            errors.append(f"{skill}: references '{ref}' but {d / ref} does not exist")

    for sub in sorted(p for p in d.iterdir() if p.is_dir()):
        if sub.name not in SUBDIRS:
            warnings.append(f"{sub}: non-standard subdirectory (use {', '.join(sorted(SUBDIRS))})")
    refs = d / "references"
    if refs.is_dir() and sum(1 for p in refs.rglob("*") if p.is_file()) > MAX_REFERENCES:
        warnings.append(f"{refs}: more than {MAX_REFERENCES} files (references-sprawl)")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv
    root = Path(args[0] if args else "skills")
    if not root.is_dir():
        print(f"error: {root}/ not found")
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    seen: dict[str, Path] = {}

    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            errors.append(f"{p}: symlinks are not allowed")
        elif p.is_file() and p.stat().st_size > MAX_BYTES:
            errors.append(f"{p}: larger than {MAX_BYTES // 1024} KiB")
    for p in sorted(root.iterdir()):
        if p.is_file() and p.name not in TOP_LEVEL_FILES and not p.name.startswith("."):
            errors.append(f"{p}: put files inside a skill directory (skills/<name>/)")

    skill_dirs = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith((".", "_"))]
    for d in skill_dirs:
        check_skill(d, errors, warnings, seen)

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    print(f"{len(skill_dirs)} skill(s) checked, {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors or (strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
