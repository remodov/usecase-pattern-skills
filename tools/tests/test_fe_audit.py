"""Аудит фронта обязан ловить обе бесшумные ошибки: выдуманный ID и незакрытое требование."""

import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
AUDIT = ROOT / "tools" / "fe_audit.py"

SPEC = """# Область

## Purpose

Проверочная область.

## Requirements

### Requirement: Первое

Что-то SHALL быть верно.

**ID**: api/first-rule
**Гейт**: ревью
**Покрытие**: нет
**Не ловит**: ничего не ловит, держится ревью целиком.

#### Scenario: случай

- **WHEN** условие
- **THEN** исход
"""


def _repo(tmp, spec=SPEC):
    repo = pathlib.Path(tmp) / "templates" / "next-ssr" / "openspec" / "specs" / "api"
    repo.mkdir(parents=True)
    (repo / "spec.md").write_text(spec, encoding="utf-8")
    return pathlib.Path(tmp)


def _run(repo, skills_dir):
    return subprocess.run(
        [sys.executable, str(AUDIT), str(repo)],
        capture_output=True,
        text=True,
        cwd=skills_dir,
    )


def _skills(tmp, body):
    skills = pathlib.Path(tmp) / "project" / ".claude" / "skills" / "ucp-fe-check"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(body, encoding="utf-8")
    return skills.parents[2]


class FeAuditTest(unittest.TestCase):
    def test_совпадение(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _repo(tmp)
            project = _skills(tmp, "Правило `api/first-rule` ведёт этот скилл.\n")

            result = _run(repo, project)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("совпадают с шаблоном", result.stdout)

    def test_выдуманный_идентификатор(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _repo(tmp)
            project = _skills(tmp, "Правила `api/first-rule` и `api/invented-rule`.\n")

            result = _run(repo, project)

            self.assertEqual(result.returncode, 1)
            self.assertIn("ведёт в никуда", result.stderr)

    def test_требование_никем_не_ведётся(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _repo(tmp)
            project = _skills(tmp, "Скилл без ссылок на требования.\n")

            result = _run(repo, project)

            self.assertEqual(result.returncode, 1)
            self.assertIn("не ведёт ни один скилл", result.stderr)

    def test_не_тот_каталог(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _skills(tmp, "Пусто.\n")

            result = _run(pathlib.Path(tmp) / "nowhere", project)

            self.assertEqual(result.returncode, 1)
            self.assertIn("не похож на клон", result.stderr)


if __name__ == "__main__":
    unittest.main()
