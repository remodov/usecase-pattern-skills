import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / ".claude" / "docs" / "_meta" / "spec_check.py"

SPEC = (ROOT / "tools" / "tests" / "fixtures" / "valid-spec.md").read_text(encoding="utf-8")


def _run(docs_dir):
    return subprocess.run(
        [sys.executable, str(CHECK), str(docs_dir)],
        capture_output=True,
        text=True,
    )


class SpecCheckTest(unittest.TestCase):
    def _corpus(self, tmp, migrated, with_spec=True, with_rules=False):
        docs = Path(tmp) / "docs"
        domain = docs / "backend" / "pg-migrations"
        domain.mkdir(parents=True)
        (docs / "_meta").mkdir(parents=True)
        (docs / "_meta" / "migrated-domains.md").write_text(migrated, encoding="utf-8")

        if with_spec:
            (domain / "spec.md").write_text(SPEC, encoding="utf-8")

        if with_rules:
            (domain / "pg-migrations-rules.md").write_text("# старое\n", encoding="utf-8")

        return docs

    def test_чистый_корпус(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corpus(tmp, "- `backend/pg-migrations`\n")

            result = _run(docs)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("спеки сходятся", result.stdout)

    def test_домен_в_реестре_без_спеки(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corpus(tmp, "- `backend/pg-migrations`\n", with_spec=False)

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("в реестре есть, а spec.md нет", result.stderr)

    def test_спека_вне_реестра(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corpus(tmp, "Пока ни одного.\n")

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("нет в _meta/migrated-domains.md", result.stderr)

    def test_старый_rules_остался(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corpus(tmp, "- `backend/pg-migrations`\n", with_rules=True)

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("два источника правды", result.stderr)



class DocLinksTest(unittest.TestCase):
    """Переименование файла без правки ссылок замечал только читатель, открывший её."""

    def _corpus(self, tmp):
        docs = Path(tmp) / "docs"
        domain = docs / "backend" / "pg-migrations"
        domain.mkdir(parents=True)
        (docs / "_meta").mkdir(parents=True)
        (docs / "_meta" / "migrated-domains.md").write_text(
            "- `backend/pg-migrations`\n", encoding="utf-8"
        )
        (domain / "spec.md").write_text(SPEC, encoding="utf-8")
        return docs, domain

    def test_ссылка_на_несуществующий_файл_корпуса(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs, domain = self._corpus(tmp)
            (domain / "spec.md").write_text(
                SPEC + "\nПодробности — `.claude/docs/backend/pg-migrations/references/java/nope.md`.\n",
                encoding="utf-8",
            )

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("файла нет", result.stderr)

    def test_обещанный_справочник_отсутствует(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs, domain = self._corpus(tmp)
            (domain / "spec.md").write_text(
                SPEC + "\nПолный справочник — `references/implementation.md`.\n",
                encoding="utf-8",
            )

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("обещан справочник", result.stderr)

    def test_существующий_справочник_проходит(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs, domain = self._corpus(tmp)
            (domain / "references").mkdir()
            (domain / "references" / "implementation.md").write_text("# как в коде\n", encoding="utf-8")
            (domain / "spec.md").write_text(
                SPEC + "\nПолный справочник — `references/implementation.md`.\n",
                encoding="utf-8",
            )

            result = _run(docs)

            self.assertEqual(result.returncode, 0, result.stderr)


class EmptyReferencesTest(unittest.TestCase):
    """Пустой references/ — обещание примеров, которых нет."""

    def test_пустой_каталог_справочников(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            domain = docs / "backend" / "pg-migrations"
            (domain / "references").mkdir(parents=True)
            (docs / "_meta").mkdir(parents=True)
            (docs / "_meta" / "migrated-domains.md").write_text(
                "- `backend/pg-migrations`\n", encoding="utf-8"
            )
            (domain / "spec.md").write_text(SPEC, encoding="utf-8")

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("пуст", result.stderr)




class DomainStatsTest(unittest.TestCase):
    """Строка «Чем держится домен» считается генератором; разошлась — гейт краснеет."""

    def _corpus(self, tmp, stats_line):
        docs = Path(tmp) / "docs"
        domain = docs / "backend" / "pg-migrations"
        domain.mkdir(parents=True)
        (docs / "_meta").mkdir(parents=True)
        (docs / "_meta" / "migrated-domains.md").write_text(
            "- `backend/pg-migrations`\n", encoding="utf-8"
        )
        spec = SPEC.replace(
            "**Чем держится домен.** Требований — 1; проверкой закрыто 1, держится ревью 0 (0 %).",
            stats_line,
        )
        (domain / "spec.md").write_text(spec, encoding="utf-8")
        return docs

    def test_расхождение_ловится(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corpus(tmp, "**Чем держится домен.** Требований — 9; проверкой закрыто 9, держится ревью 0 (0 %).")

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("разошёлся с требованиями", result.stderr)

    def test_отсутствие_блока_ловится(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            domain = docs / "backend" / "pg-migrations"
            domain.mkdir(parents=True)
            (docs / "_meta").mkdir(parents=True)
            (docs / "_meta" / "migrated-domains.md").write_text(
                "- `backend/pg-migrations`\n", encoding="utf-8"
            )
            without = "\n".join(
                line for line in SPEC.split("\n")
                if "ucp-domain-stats" not in line and "Чем держится домен" not in line
            )
            (domain / "spec.md").write_text(without, encoding="utf-8")

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("нет блока", result.stderr)




class HumanIntroTest(unittest.TestCase):
    """Домен без врезки «Что здесь главное» читается только целиком."""

    def _corpus(self, tmp, spec_text):
        docs = Path(tmp) / "docs"
        domain = docs / "backend" / "pg-migrations"
        domain.mkdir(parents=True)
        (docs / "_meta").mkdir(parents=True)
        (docs / "_meta" / "migrated-domains.md").write_text(
            "- `backend/pg-migrations`\n", encoding="utf-8"
        )
        (domain / "spec.md").write_text(spec_text, encoding="utf-8")
        return docs

    def test_врезки_нет(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corpus(tmp, SPEC.replace("**Что здесь главное**", "**Про домен**", 1))

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("Что здесь главное", result.stderr)

    def test_врезка_из_одного_пункта(self):
        with tempfile.TemporaryDirectory() as tmp:
            short = SPEC.replace(
                "- Второе правило простым языком.\n- Где чаще всего ошибаются и почему это не видно сразу.\n",
                "",
                1,
            )
            docs = self._corpus(tmp, short)

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("нужно хотя бы три", result.stderr)




class WhyFieldTest(unittest.TestCase):
    """Требование без последствия оспаривают на каждом ревью."""

    def _corpus(self, tmp, spec_text):
        docs = Path(tmp) / "docs"
        domain = docs / "backend" / "pg-migrations"
        domain.mkdir(parents=True)
        (docs / "_meta").mkdir(parents=True)
        (docs / "_meta" / "migrated-domains.md").write_text(
            "- `backend/pg-migrations`\n", encoding="utf-8"
        )
        (domain / "spec.md").write_text(spec_text, encoding="utf-8")
        return docs

    def test_поля_нет(self):
        with tempfile.TemporaryDirectory() as tmp:
            without = "\n".join(
                line for line in SPEC.split("\n") if not line.startswith("**Почему**")
            )
            result = _run(self._corpus(tmp, without))

            self.assertEqual(result.returncode, 1)
            self.assertIn("нет поля **Почему**", result.stderr)

    def test_поле_формальное(self):
        with tempfile.TemporaryDirectory() as tmp:
            short = re.sub(r"^\*\*Почему\*\*: .*$", "**Почему**: так надо.", SPEC, count=1, flags=re.M)
            result = _run(self._corpus(tmp, short))

            self.assertEqual(result.returncode, 1)
            self.assertIn("названо формально", result.stderr)



if __name__ == "__main__":
    unittest.main()


class DanglingReferenceTest(unittest.TestCase):
    def test_ссылка_на_удалённый_rules_индекс(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            domain = docs / "backend" / "pg-migrations"
            domain.mkdir(parents=True)
            (docs / "_meta").mkdir(parents=True)
            (docs / "_meta" / "migrated-domains.md").write_text(
                "- `backend/pg-migrations`\n", encoding="utf-8"
            )
            (domain / "spec.md").write_text(SPEC, encoding="utf-8")
            other = docs / "backend" / "sqlc"
            other.mkdir(parents=True)
            (other / "sqlc-rules.md").write_text(
                "- Безопасность миграций — по `pg-migrations-rules.md`.\n", encoding="utf-8"
            )

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("ссылается на `pg-migrations-rules.md`", result.stderr)


class DanglingReferenceSubstringTest(unittest.TestCase):
    def test_имя_файла_другого_домена_не_считается_ссылкой(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            domain = docs / "backend" / "pg-migrations"
            domain.mkdir(parents=True)
            (docs / "_meta").mkdir(parents=True)
            (docs / "_meta" / "migrated-domains.md").write_text(
                "- `backend/pg-migrations`\n", encoding="utf-8"
            )
            (domain / "spec.md").write_text(SPEC, encoding="utf-8")
            other = docs / "backend" / "legacy-pg-migrations"
            other.mkdir(parents=True)
            (other / "legacy-pg-migrations-rules.md").write_text(
                "Правила устаревшего домена.\n", encoding="utf-8"
            )
            (other / "note.md").write_text(
                "Читай `legacy-pg-migrations-rules.md`.\n", encoding="utf-8"
            )

            result = _run(docs)

            self.assertEqual(result.returncode, 0, result.stderr)


class GateCatalogueTest(unittest.TestCase):
    def _corpus(self, tmp, catalogue):
        docs = Path(tmp) / "docs"
        domain = docs / "backend" / "pg-migrations"
        domain.mkdir(parents=True)
        (docs / "_meta").mkdir(parents=True)
        (docs / "_meta" / "migrated-domains.md").write_text(
            "- `backend/pg-migrations`\n", encoding="utf-8"
        )
        (docs / "_meta" / "project-gates.md").write_text(catalogue, encoding="utf-8")
        spec = SPEC.replace("**Гейт**: squawk:require-lock-timeout", "**Гейт**: script:ddl-check")
        (domain / "spec.md").write_text(spec, encoding="utf-8")
        return docs

    def test_гейт_из_каталога_принимается(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corpus(tmp, "| `lock-timeout` | ... | `script:ddl-check` |\n")

            result = _run(docs)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_гейт_вне_каталога_краснеет(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._corpus(tmp, "каталог без единого упоминания проверки\n")

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("нет в каталоге", result.stderr)


class ChangeFolderTest(unittest.TestCase):
    """Каталог изменения: дельта, сверка «Изменено» со спекой, архив.

    Дельта, которая правит требование, исчезнувшее из спеки, — тихая поломка:
    при слиянии её просто некуда приложить, а заметно это станет через месяц.
    """

    def _repo(self, tmp):
        root = Path(tmp)
        docs = root / ".claude" / "docs"
        domain = docs / "backend" / "pg-migrations"
        domain.mkdir(parents=True)
        (docs / "_meta").mkdir(parents=True)
        (docs / "_meta" / "migrated-domains.md").write_text(
            "- `backend/pg-migrations`\n", encoding="utf-8")
        (domain / "spec.md").write_text(SPEC, encoding="utf-8")
        return root, docs

    def _change(self, root, name, proposal="# Изменение\n", tasks="# Задачи\n", delta=None):
        change = root / "openspec" / "changes" / name
        change.mkdir(parents=True)
        (change / "proposal.md").write_text(proposal, encoding="utf-8")
        (change / "tasks.md").write_text(tasks, encoding="utf-8")

        if delta is not None:
            (change / "delta-pg-migrations.md").write_text(delta, encoding="utf-8")

        return change

    def test_изменение_без_дельты_и_без_причины_не_проходит(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, docs = self._repo(tmp)
            self._change(root, "без-дельты")

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("нет дельты", result.stderr)

    def test_дельты_нет_с_причиной_пропускается(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, docs = self._repo(tmp)
            self._change(root, "инструменты",
                         proposal="# Изменение\n\nДельты нет: правим только сборку, "
                                  "требования не меняются.\n")

            result = _run(docs)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_правка_несуществующего_требования_ловится(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, docs = self._repo(tmp)
            self._change(root, "правка", delta=(
                "# Дельта\n\nМеняем backend/pg-migrations/spec.md\n\n"
                "## Изменено\n\n### Requirement: Чего-то нет\n\n"
                "**ID**: pg-migrations/такого-нет\n\n"
                "#### Scenario: раз\n\n- **WHEN** а\n- **THEN** б\n"))

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("такого-нет", result.stderr)

    def test_изменено_кусками_не_проходит(self):
        """Правка «одного поля» не вливается механически — только руками."""
        with tempfile.TemporaryDirectory() as tmp:
            root, docs = self._repo(tmp)
            self._change(root, "кусками", delta=(
                "# Дельта\n\nМеняем backend/pg-migrations/spec.md\n\n"
                "## Изменено\n\n### pg-migrations/lock-timeout-required\n\n"
                "**Было:**\n\n> старое\n\n**Стало:**\n\n> новое\n"))

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("целиком", result.stderr)

    def test_изменено_целиком_проходит(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, docs = self._repo(tmp)
            self._change(root, "целиком", delta=(
                "# Дельта\n\nМеняем backend/pg-migrations/spec.md\n\n"
                "## Изменено\n\n### Requirement: Таймаут блокировки\n\n"
                "**ID**: pg-migrations/lock-timeout-required\n\n"
                "#### Scenario: раз\n\n- **WHEN** а\n- **THEN** б\n\n"
                "**Что изменилось:** добавлен сценарий\n"))

            result = _run(docs)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_переименование_несуществующего_ловится(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, docs = self._repo(tmp)
            self._change(root, "переименование", delta=(
                "# Дельта\n\nМеняем backend/pg-migrations/spec.md\n\n"
                "## Переименовано\n\n"
                "- FROM: `pg-migrations/такого-не-было`\n"
                "- TO: `pg-migrations/новое-имя`\n"))

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("такого-не-было", result.stderr)

    def test_архив_с_неотмеченными_задачами_ловится(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, docs = self._repo(tmp)
            archive = root / "openspec" / "changes" / "archive" / "старое"
            archive.mkdir(parents=True)
            (archive / "proposal.md").write_text("# Старое\n", encoding="utf-8")
            (archive / "tasks.md").write_text("# Задачи\n\n- [x] сделано\n- [ ] забыли\n",
                                              encoding="utf-8")

            result = _run(docs)

            self.assertEqual(result.returncode, 1)
            self.assertIn("неотмеченные задачи", result.stderr)
