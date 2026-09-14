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


class DeltaTemplate(unittest.TestCase):
    """Дельта — это кусок будущей спеки, а не пересказ словами.

    Раздел «Добавлено» обязан нести требование целиком и в той же форме, что
    в spec.md: при слиянии его переносят как есть. Если форма разойдётся,
    слияние превратится в ручной перенабор, а он теряет поля.
    """

    def setUp(self):
        self.text = (TEMPLATES / "change" / "delta.md").read_text(encoding="utf-8")

    def test_three_sections(self):
        for раздел in ("## Добавлено", "## Изменено", "## Удалено"):
            self.assertIn(раздел, self.text)

    def test_added_carries_full_requirement_form(self):
        добавлено = self.text.split("## Добавлено", 1)[1].split("## Изменено", 1)[0]
        for field in ("### Requirement:", "**Почему**", "**ID**", "**Гейт**",
                      "**Покрытие**", "#### Scenario:", "**WHEN**", "**THEN**"):
            self.assertIn(field, добавлено, f"в «Добавлено» нет {field}")

    def test_modified_shows_before_and_after(self):
        изменено = self.text.split("## Изменено", 1)[1].split("## Удалено", 1)[0]
        self.assertIn("**Было:**", изменено)
        self.assertIn("**Стало:**", изменено)
        self.assertIn("**Почему меняем:**", изменено)

    def test_removed_demands_reason(self):
        удалено = self.text.split("## Удалено", 1)[1]
        self.assertIn("**Причина:**", удалено)

    def test_names_target_file(self):
        self.assertIn("spec.md", self.text.split("## Добавлено", 1)[0])


if __name__ == "__main__":
    unittest.main()
