import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "docs" / "_meta"))

import spec_format


SPEC = """# jOOQ

## Purpose

Как читается и пишется persistence-слой.

## Requirements

### Requirement: Nested-выборка через multiset

Вложенные коллекции SHALL читаться одним запросом через `multiset`;
цикл с отдельным запросом на элемент SHALL NOT применяться.

**ID**: jooq/nested-via-multiset
**Код**: R-JOOQ-7
**Гейт**: нет
**Покрытие**: нет
**Не ловит**: N+1 не ловит ничто — ни компилятор, ни тест на одной записи.

#### Scenario: репозиторий тянет позиции циклом

- **WHEN** репозиторий читает заказы, а позиции — запросом на каждый
- **THEN** ни одна проверка не краснеет
"""


class ParseSpecTest(unittest.TestCase):
    def test_разделы_найдены(self):
        spec = spec_format.parse_spec("jooq/spec.md", SPEC)

        self.assertTrue(spec.has_purpose)
        self.assertTrue(spec.has_requirements)
        self.assertFalse(spec.unbalanced_fence)

    def test_требование_разобрано(self):
        spec = spec_format.parse_spec("jooq/spec.md", SPEC)

        self.assertEqual(len(spec.requirements), 1)
        requirement = spec.requirements[0]
        self.assertEqual(requirement.name, "Nested-выборка через multiset")
        self.assertEqual(requirement.meta["ID"], "jooq/nested-via-multiset")
        self.assertEqual(requirement.meta["Код"], "R-JOOQ-7")
        self.assertEqual(requirement.meta["Покрытие"], "нет")
        self.assertIn("SHALL", requirement.body)

    def test_сценарий_разобран(self):
        spec = spec_format.parse_spec("jooq/spec.md", SPEC)
        scenario = spec.requirements[0].scenarios[0]

        self.assertEqual(scenario.name, "Scenario: репозиторий тянет позиции циклом")
        self.assertEqual(len(scenario.steps), 2)

    def test_содержимое_блока_кода_не_читается(self):
        source = SPEC + "\n```\n### Requirement: не настоящее\n```\n"

        spec = spec_format.parse_spec("jooq/spec.md", source)

        self.assertEqual(len(spec.requirements), 1)

    def test_незакрытый_блок_кода_помечен(self):
        source = SPEC + "\n```\nхвост без закрытия\n"

        spec = spec_format.parse_spec("jooq/spec.md", source)

        self.assertTrue(spec.unbalanced_fence)


if __name__ == "__main__":
    unittest.main()


class CheckStructureTest(unittest.TestCase):
    def test_валидная_спека_без_замечаний(self):
        spec = spec_format.parse_spec("jooq/spec.md", SPEC)

        self.assertEqual(spec_format.check_structure(spec), [])

    def test_требование_без_shall(self):
        source = SPEC.replace("SHALL читаться", "читается").replace("SHALL NOT применяться", "не применяется")

        problems = spec_format.check_structure(spec_format.parse_spec("jooq/spec.md", source))

        self.assertEqual(len(problems), 1)
        self.assertIn("SHALL", problems[0])
        self.assertIn("jooq/spec.md:9", problems[0])

    def test_требование_без_сценария(self):
        source = SPEC.split("#### Scenario")[0]

        problems = spec_format.check_structure(spec_format.parse_spec("jooq/spec.md", source))

        self.assertEqual(len(problems), 1)
        self.assertIn("Scenario", problems[0])

    def test_сценарий_без_then(self):
        source = SPEC.replace("- **THEN** ни одна проверка не краснеет", "- проверка не краснеет")

        problems = spec_format.check_structure(spec_format.parse_spec("jooq/spec.md", source))

        self.assertEqual(len(problems), 1)
        self.assertIn("**THEN**", problems[0])

    def test_нет_раздела_purpose(self):
        source = SPEC.replace("## Purpose", "## Про что это")

        problems = spec_format.check_structure(spec_format.parse_spec("jooq/spec.md", source))

        self.assertIn("Purpose", " ".join(problems))


def _spec(file, ident, code="R-JOOQ-7"):
    source = SPEC.replace("**ID**: jooq/nested-via-multiset", f"**ID**: {ident}")
    source = source.replace("**Код**: R-JOOQ-7", f"**Код**: {code}")

    return spec_format.parse_spec(file, source)


class CheckAddressingTest(unittest.TestCase):
    def test_валидная_адресация(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset")]

        self.assertEqual(spec_format.check_addressing(specs), [])

    def test_id_не_в_форме(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "jooq/Nested_Via_Multiset")]

        problems = spec_format.check_addressing(specs)

        self.assertEqual(len(problems), 1)
        self.assertIn("не в форме", problems[0])

    def test_id_не_из_своей_области(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "kafka/nested-via-multiset")]

        problems = spec_format.check_addressing(specs)

        self.assertIn("не начинается с области «jooq»", problems[0])

    def test_дубль_id(self):
        specs = [
            _spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset", "R-JOOQ-7"),
            _spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset", "R-JOOQ-8"),
        ]

        problems = spec_format.check_addressing(specs)

        self.assertIn("уже занят", problems[0])

    def test_дубль_кода(self):
        specs = [
            _spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset", "R-JOOQ-7"),
            _spec(".claude/docs/backend/jooq/spec.md", "jooq/select-mode", "R-JOOQ-7"),
        ]

        problems = spec_format.check_addressing(specs)

        self.assertIn("**Код** «R-JOOQ-7» уже занят", " ".join(problems))

    def test_код_необязателен(self):
        source = SPEC.replace("**Код**: R-JOOQ-7\n", "")
        specs = [spec_format.parse_spec(".claude/docs/backend/jooq/spec.md", source)]

        self.assertEqual(spec_format.check_addressing(specs), [])

    def test_collect_codes_отдаёт_карту(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset")]

        self.assertEqual(spec_format.collect_codes(specs), {"R-JOOQ-7": "jooq/nested-via-multiset"})


def _with_meta(gate, coverage, gap="дыра описана словами и длиннее двадцати символов", file=".claude/docs/backend/jooq/spec.md"):
    source = SPEC.replace("**Гейт**: нет", f"**Гейт**: {gate}")
    source = source.replace("**Покрытие**: нет", f"**Покрытие**: {coverage}")
    source = source.replace(
        "**Не ловит**: N+1 не ловит ничто — ни компилятор, ни тест на одной записи.",
        f"**Не ловит**: {gap}",
    )

    return spec_format.parse_spec(file, source)


class ParseGateTest(unittest.TestCase):
    def test_нет_гейта(self):
        self.assertEqual(spec_format.parse_gate("нет"), {})

    def test_одноязычная_форма(self):
        self.assertEqual(
            spec_format.parse_gate("checkstyle:UnusedImports, archunit:LayersTest"),
            {"*": ["checkstyle:UnusedImports", "archunit:LayersTest"]},
        )

    def test_многоязычная_форма(self):
        self.assertEqual(
            spec_format.parse_gate("java: checkstyle:UnusedImports · python: ruff:F401"),
            {"java": ["checkstyle:UnusedImports"], "python": ["ruff:F401"]},
        )


class CheckGatesTest(unittest.TestCase):
    def test_гейта_нет_покрытия_нет(self):
        specs = [_with_meta("нет", "нет")]

        self.assertEqual(spec_format.check_gates(specs, {"jooq": ["java"]}), [])

    def test_гейт_назван_а_покрытие_нет(self):
        specs = [_with_meta("checkstyle:UnusedImports", "нет")]

        problems = spec_format.check_gates(specs, {"jooq": ["java"]})

        self.assertIn("**Покрытие** «нет» при названном гейте", problems[0])

    def test_неизвестный_вид_гейта(self):
        specs = [_with_meta("pylint:C0301", "частичное")]

        problems = spec_format.check_gates(specs, {"jooq": ["java"]})

        self.assertIn("неизвестный вид гейта «pylint»", problems[0])

    def test_гейт_без_значения(self):
        specs = [_with_meta("checkstyle", "частичное")]

        problems = spec_format.check_gates(specs, {"jooq": ["java"]})

        self.assertIn("без значения", problems[0])

    def test_короткое_не_ловит_при_неполном_покрытии(self):
        specs = [_with_meta("checkstyle:UnusedImports", "частичное", gap="—")]

        problems = spec_format.check_gates(specs, {"jooq": ["java"]})

        self.assertIn("**Не ловит**", problems[0])

    def test_язык_области_не_назван(self):
        specs = [_with_meta("java: checkstyle:UnusedImports", "полное")]

        problems = spec_format.check_gates(specs, {"jooq": ["java", "python"]})

        self.assertIn("язык «python»", problems[0])

    def test_покрытие_по_худшему_языку(self):
        specs = [_with_meta("java: checkstyle:UnusedImports · python: ruff:F401", "полное")]

        self.assertEqual(spec_format.check_gates(specs, {"jooq": ["java", "python"]}), [])

    def test_недопустимое_значение_покрытия(self):
        specs = [_with_meta("нет", "местами")]

        problems = spec_format.check_gates(specs, {"jooq": ["java"]})

        self.assertIn("**Покрытие** обязано быть одним из", problems[0])


class RenderTest(unittest.TestCase):
    def test_таблица_требований(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset")]

        block = spec_format.render_requirements(specs)

        self.assertTrue(block.startswith(spec_format.BLOCK_START))
        self.assertTrue(block.endswith(spec_format.BLOCK_END))
        self.assertIn("| Требование | Гейт | Покрытие |", block)
        self.assertIn("jooq/nested-via-multiset", block)

    def test_таблица_отсортирована_по_id(self):
        specs = [
            _spec(".claude/docs/backend/jooq/spec.md", "jooq/select-mode", "R-JOOQ-9"),
            _spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset", "R-JOOQ-7"),
        ]

        block = spec_format.render_requirements(specs)

        self.assertLess(block.index("jooq/nested-via-multiset"), block.index("jooq/select-mode"))

    def test_карта_кодов(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset")]

        block = spec_format.render_code_map(specs)

        self.assertIn("| Код | Требование | Область |", block)
        self.assertIn("| `R-JOOQ-7` | `jooq/nested-via-multiset` | jooq |", block)

    def test_замена_блока(self):
        source = f"шапка\n{spec_format.BLOCK_START}\nстарое\n{spec_format.BLOCK_END}\nхвост\n"

        updated = spec_format.replace_block(
            source,
            f"{spec_format.BLOCK_START}\nновое\n{spec_format.BLOCK_END}",
            spec_format.BLOCK_START,
            spec_format.BLOCK_END,
        )

        self.assertIn("новое", updated)
        self.assertNotIn("старое", updated)
        self.assertTrue(updated.startswith("шапка"))
        self.assertTrue(updated.endswith("хвост\n"))

    def test_блока_нет_маркеров(self):
        problems = spec_format.check_block(
            "нет маркеров", "любой", spec_format.BLOCK_START, spec_format.BLOCK_END, "запусти spec_sync.py"
        )

        self.assertIn("нет маркеров", problems[0])

    def test_блок_разошёлся(self):
        source = f"{spec_format.BLOCK_START}\nстарое\n{spec_format.BLOCK_END}"

        problems = spec_format.check_block(
            source,
            f"{spec_format.BLOCK_START}\nновое\n{spec_format.BLOCK_END}",
            spec_format.BLOCK_START,
            spec_format.BLOCK_END,
            "запусти spec_sync.py",
        )

        self.assertIn("запусти spec_sync.py", problems[0])


class RegistryTest(unittest.TestCase):
    def test_реестр_разобран(self):
        source = """# Мигрированные домены

Домены, переведённые на openspec-требования. Список ведётся руками.

- `backend/pg-migrations`
- `backend/hexagonal`
"""

        self.assertEqual(
            spec_format.parse_migrated(source),
            ["backend/pg-migrations", "backend/hexagonal"],
        )

    def test_пустой_реестр(self):
        self.assertEqual(spec_format.parse_migrated("# Мигрированные домены\n\nПока ни одного.\n"), [])


class CollectTest(unittest.TestCase):
    def test_сбор_спек_и_языков(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            domain = root / "backend" / "hexagonal"
            (domain / "references" / "java").mkdir(parents=True)
            (domain / "references" / "python").mkdir(parents=True)
            (domain / "spec.md").write_text(SPEC, encoding="utf-8")

            specs = spec_format.collect_specs(root)
            languages = spec_format.collect_languages(root)

            self.assertEqual(len(specs), 1)
            self.assertTrue(specs[0].file.endswith("backend/hexagonal/spec.md"))
            self.assertEqual(languages["hexagonal"], ["java", "python"])


class CodeListTest(unittest.TestCase):
    def test_список_кодов(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset", "R-JOOQ-7, R-JOOQ-70X")]

        self.assertEqual(spec_format.check_addressing(specs), [])
        self.assertEqual(
            spec_format.collect_codes(specs),
            {"R-JOOQ-7": "jooq/nested-via-multiset", "R-JOOQ-70X": "jooq/nested-via-multiset"},
        )

    def test_дубль_внутри_списка_кодов(self):
        specs = [
            _spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset", "R-JOOQ-7, R-JOOQ-70X"),
            _spec(".claude/docs/backend/jooq/spec.md", "jooq/select-mode", "R-JOOQ-70X"),
        ]

        problems = spec_format.check_addressing(specs)

        self.assertIn("**Код** «R-JOOQ-70X» уже занят", " ".join(problems))

    def test_карта_кодов_строка_на_каждый_код(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset", "R-JOOQ-7, R-JOOQ-70X")]

        block = spec_format.render_code_map(specs)

        self.assertIn("| `R-JOOQ-7` | `jooq/nested-via-multiset` | jooq |", block)
        self.assertIn("| `R-JOOQ-70X` | `jooq/nested-via-multiset` | jooq |", block)


class ReviewGateTest(unittest.TestCase):
    def test_ревью_это_отсутствие_машинного_гейта(self):
        specs = [_with_meta("ревью", "нет")]

        self.assertEqual(spec_format.check_gates(specs, {"jooq": ["java"]}), [])

    def test_ревью_не_даёт_частичного_покрытия(self):
        specs = [_with_meta("ревью", "частичное")]

        problems = spec_format.check_gates(specs, {"jooq": ["java"]})

        self.assertIn("машинного гейта нет", problems[0])

    def test_смесь_машинного_и_ревью_по_языкам(self):
        specs = [_with_meta("java: archunit:LayersTest · python: ревью", "частичное")]

        self.assertEqual(spec_format.check_gates(specs, {"jooq": ["java", "python"]}), [])

    def test_смесь_не_может_быть_полной(self):
        specs = [_with_meta("java: archunit:LayersTest · python: ревью", "полное")]

        problems = spec_format.check_gates(specs, {"jooq": ["java", "python"]})

        self.assertIn("покрытие не может быть «полное»", problems[0])


class ArchitectureGateKindsTest(unittest.TestCase):
    def test_import_linter_и_dependency_cruiser_известны(self):
        specs = [_with_meta(
            "java: archunit:CoreTest · python: import-linter:core-independence "
            "· go: golangci-lint:depguard · node: dependency-cruiser:no-core-to-adapter",
            "частичное",
        )]

        self.assertEqual(
            spec_format.check_gates(specs, {"jooq": ["java", "python", "go", "node"]}),
            [],
        )


class DottedCodeShapeTest(unittest.TestCase):
    def test_код_с_точками_допустим(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset", "JS-2.6.1")]

        self.assertEqual(spec_format.check_addressing(specs), [])

    def test_антипаттерн_после_точки_допустим(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset", "JS-6.X1")]

        self.assertEqual(spec_format.check_addressing(specs), [])

    def test_код_в_нижнем_регистре_не_допустим(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset", "js-2.6.1")]

        problems = spec_format.check_addressing(specs)

        self.assertIn("не в форме", problems[0])


class SuffixedCodeShapeTest(unittest.TestCase):
    def test_код_с_буквенным_суффиксом_допустим(self):
        specs = [_spec(".claude/docs/backend/jooq/spec.md", "jooq/nested-via-multiset", "BS-SEC-5a")]

        self.assertEqual(spec_format.check_addressing(specs), [])


class LanguageAgnosticGateTest(unittest.TestCase):
    def test_нейтральный_гейт_покрывает_все_языки(self):
        specs = [_with_meta("script:config-check", "полное")]

        self.assertEqual(
            spec_format.check_gates(specs, {"jooq": ["java", "python", "go", "node"]}),
            [],
        )
