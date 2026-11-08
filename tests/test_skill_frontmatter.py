"""Repo-wide skill checks beyond scripts/validate_skills.py: YAML, generic content, no secrets. No network."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import FIXTURES, ROOT, SKILLS

try:
    import yaml
except ImportError:  # CI installs a pinned PyYAML; locally the YAML check is skipped without it
    yaml = None

SKILL_FILES = sorted(SKILLS.glob("*/SKILL.md"))
CONTENT = sorted(p for p in SKILLS.glob("*/**/*") if p.is_file())
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
SECRETISH = re.compile(r"(?i)(key|token|secret)[\"'\s:=]{1,4}[A-Za-z0-9+/=_:-]{24,}")
# A literal value recorded next to an auth header name (code that passes a variable is fine).
HEADER_VALUE = re.compile(r"(?i)(accountkey|x-api-key)[\"']?\s*[:=]\s*[\"'][^\"'\s]{8,}")


def frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path}: must start with ---"
    return text[4:text.index("\n---\n", 4)]


class Validator(unittest.TestCase):
    def run_validator(self, target: Path) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_skills.py"), str(target)],
                              capture_output=True, text=True)

    def test_repo_skills_pass(self):
        r = self.run_validator(SKILLS)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_missing_script_reference_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "demo"
            d.mkdir()
            (d / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\nversion: 1.0.0\n---\n"
                                        "Run `python3 ${HERMES_SKILL_DIR}/scripts/nope.py`.\n")
            r = self.run_validator(Path(tmp))
            self.assertEqual(r.returncode, 1)
            self.assertIn("scripts/nope.py", r.stdout)

    def test_hardcoded_hermes_path_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "demo"
            d.mkdir()
            (d / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\nversion: 1.0.0\n---\n"
                                        "Run `python3 ~/.hermes/skills/demo/x.py`.\n")
            r = self.run_validator(Path(tmp))
            self.assertEqual(r.returncode, 1)
            self.assertIn("~/.hermes", r.stdout)


class Frontmatter(unittest.TestCase):
    @unittest.skipIf(yaml is None and not os.environ.get("REQUIRE_YAML"), "PyYAML not installed")
    def test_parses_as_yaml_mapping(self):
        self.assertIsNotNone(yaml, "REQUIRE_YAML is set but PyYAML is missing")
        for path in SKILL_FILES:
            with self.subTest(skill=path.parent.name):
                meta = yaml.safe_load(frontmatter(path))
                self.assertIsInstance(meta, dict)
                self.assertEqual(meta["name"], path.parent.name)
                self.assertLessEqual(len(meta["description"]), 60)
                for var in meta.get("required_environment_variables") or []:
                    self.assertTrue({"name", "prompt", "help", "required_for"} <= set(var))

    def test_author_is_role_not_person(self):
        for path in SKILL_FILES:
            with self.subTest(skill=path.parent.name):
                self.assertRegex(frontmatter(path), r"(?m)^author: owner$")


class GenericContent(unittest.TestCase):
    """Skills are shared across instances and the repo may go public: no personal data, no secrets."""

    def test_no_emails_or_handles(self):
        for path in CONTENT:
            with self.subTest(file=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(EMAIL.search(text))
                self.assertNotRegex(text, r"(?<![\w`])@[A-Za-z]\w{3,}")      # @telegram/@github handles

    def test_no_secret_looking_strings(self):
        for path in [*CONTENT, *FIXTURES.glob("*.json")]:
            with self.subTest(file=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                hit = SECRETISH.search(text) or HEADER_VALUE.search(text)
                self.assertIsNone(hit, hit and hit.group(0)[:40])

    def test_no_hardcoded_hermes_home(self):
        for path in CONTENT:
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertNotIn("~/.hermes", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
