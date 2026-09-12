import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import convert_rules_to_spec as convert


RULES = """# PostgreSQL Migrations — индекс правил

> Шапка-blockquote, в разбор не идёт.

## 3. ALTER TABLE — операции и локи
**MUST:**
- **PG-M-022.** `SET LOCAL lock_timeout = '3s'` в каждой миграции с `ALTER TABLE`.

## 9. Антипаттерны
**MUST NOT:**
- **PG-M-150X.** `CREATE INDEX` без `CONCURRENTLY` на живой таблице.
"""


class ConvertTest(unittest.TestCase):
    def test_коды_собраны(self):
        rules = convert.parse_rules(RULES)

        self.assertEqual([rule.code for rule in rules], ["PG-M-022", "PG-M-150X"])

    def test_раздел_запомнен(self):
        rules = convert.parse_rules(RULES)

        self.assertEqual(rules[0].section, "ALTER TABLE — операции и локи")
        self.assertTrue(rules[1].is_antipattern)

    def test_id_транслитерирован(self):
        # односимвольные предлоги в слаг не идут — «с» отбрасывается
        self.assertEqual(
            convert.make_id("pg-migrations", "Каждая миграция с ALTER TABLE"),
            "pg-migrations/kazhdaya-migraciya-alter-table",
        )

    def test_каркас_отрендерен(self):
        output = convert.render(convert.parse_rules(RULES), "pg-migrations")

        self.assertIn("## Purpose", output)
        self.assertIn("### Requirement:", output)
        self.assertIn("**Код**: PG-M-022", output)
        self.assertIn("**Гейт**:", output)
        self.assertIn("**Покрытие**:", output)


if __name__ == "__main__":
    unittest.main()
