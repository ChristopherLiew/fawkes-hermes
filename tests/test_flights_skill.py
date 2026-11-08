"""flights: content checks (the skill has no script). No network."""
from __future__ import annotations

import re
import unittest

from support import SKILLS

SKILL = SKILLS / "flights"
TEXT = (SKILL / "SKILL.md").read_text(encoding="utf-8")
FILES = ["references/kiwi-tool.md", "references/scoring.md", "templates/comparison.md", "templates/price-watch-cron.md"]


class Flights(unittest.TestCase):
    def test_never_book_rule(self):
        self.assertRegex(TEXT, r"(?i)never books")
        self.assertRegex(TEXT, r"(?i)never enters traveller or payment details")

    def test_fares_change_disclaimer(self):
        self.assertIn("fares change", TEXT)
        self.assertIn("fares change", (SKILL / "templates" / "comparison.md").read_text(encoding="utf-8"))

    def test_no_scripts_dir(self):
        self.assertFalse((SKILL / "scripts").exists())

    def test_reference_and_template_files_exist(self):
        for rel in FILES:
            with self.subTest(file=rel):
                self.assertTrue((SKILL / rel).is_file())
                self.assertIn(rel, TEXT, f"{rel} is not linked from SKILL.md")

    def test_kiwi_reference_has_parameter_table(self):
        ref = (SKILL / "references" / "kiwi-tool.md").read_text(encoding="utf-8")
        self.assertIn("| Parameter | Type | Default | Notes |", ref)
        for param in ("flyFrom", "flyTo", "departureDate", "departureDateFlexDays", "adults_hold_bags", "currency"):
            self.assertIn(f"`{param}`", ref)

    def test_never_calls_feedback_tool(self):
        self.assertRegex(TEXT, r"never call the server's `feedback-to-devs` tool")

    def test_no_purchase_instructions(self):
        """Any line mentioning buying/paying must be a prohibition, not an instruction."""
        words = re.compile(r"(?i)\b(purchase|checkout|check out|pay|payment|buy)\b")
        negation = re.compile(r"(?i)\b(never|not|don't|no)\b")
        for path in [SKILL / "SKILL.md", *(SKILL / f for f in FILES)]:
            for line in path.read_text(encoding="utf-8").splitlines():
                if words.search(line):
                    with self.subTest(file=path.name, line=line.strip()[:80]):
                        self.assertRegex(line, negation)

    def test_price_watch_uses_silent_marker(self):
        cron = (SKILL / "templates" / "price-watch-cron.md").read_text(encoding="utf-8")
        self.assertIn("[SILENT]", cron)
        self.assertIn("--skill flights", cron)


if __name__ == "__main__":
    unittest.main()
