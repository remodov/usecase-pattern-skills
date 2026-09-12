"""Шаблон домена обязан оставаться валидным документом, а не набором скобок."""

import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude" / "docs" / "_meta"))

import spec_format as sf

TEMPLATES = ROOT / "templates" / "openspec"


class DomainSpecTemplate(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        domain = self.tmp / "example"
        (domain / "references" / "java").mkdir(parents=True)
        (domain / "references" / "python").mkdir(parents=True)
        shutil.copy(TEMPLATES / "domain-spec.md", domain / "spec.md")
        self.spec_path = domain / "spec.md"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _parsed(self):
        return sf.parse_spec(str(self.spec_path), self.spec_path.read_text(encoding="utf-8"))

    def test_structure_is_valid(self):
        self.assertEqual(sf.check_structure(self._parsed()), [])

    def test_addressing_is_valid_after_copy(self):
        self.assertEqual(sf.check_addressing([self._parsed()]), [])

    def test_gates_are_valid(self):
        languages = sf.collect_languages(self.tmp)
        self.assertEqual(sf.check_gates([self._parsed()], languages), [])

    def test_every_field_of_the_contract_is_shown(self):
        text = (TEMPLATES / "domain-spec.md").read_text(encoding="utf-8")
        for field in ("**ID**", "**Код**", "**Гейт**", "**Покрытие**", "**Не ловит**"):
            self.assertIn(field, text)


class RequirementSnippet(unittest.TestCase):
    def test_snippet_carries_all_fields(self):
        text = (TEMPLATES / "requirement.md").read_text(encoding="utf-8")
        for field in ("### Requirement:", "**ID**", "**Гейт**", "**Покрытие**", "#### Scenario:"):
            self.assertIn(field, text)

    def test_scenario_has_when_and_then(self):
        text = (TEMPLATES / "requirement.md").read_text(encoding="utf-8")
        self.assertIn("**WHEN**", text)
        self.assertIn("**THEN**", text)


if __name__ == "__main__":
    unittest.main()
