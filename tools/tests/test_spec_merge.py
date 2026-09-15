"""Слияние дельты в спеку — механическое и перезапускаемое.

Пока слияние делалось руками «по таблице, ни одной строки не пропуская»,
проверить его было нечем: пропущенную строку замечали через месяц. Здесь оно
становится кодом, а значит и ошибки в нём становятся видимыми.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MERGE = ROOT / ".claude" / "docs" / "_meta" / "spec_merge.py"

СПЕКА = """# Домен

## Purpose

Учебный домен.

## Requirements

### Requirement: Таймаут блокировки

Миграция SHALL выставлять `lock_timeout`.

**Почему**: без него миграция висит на чужой транзакции
**ID**: pg-migrations/lock-timeout-required
**Гейт**: ревью
**Покрытие**: нет
**Не ловит**: всё

#### Scenario: долгая транзакция рядом

- **WHEN** рядом идёт долгая транзакция
- **THEN** миграция падает по таймауту, а не ждёт вечно

### Requirement: Индекс без блокировки

Индекс SHALL создаваться CONCURRENTLY.

**Почему**: обычный CREATE INDEX держит таблицу
**ID**: pg-migrations/index-concurrently
**Гейт**: ревью
**Покрытие**: нет
**Не ловит**: всё

#### Scenario: большая таблица

- **WHEN** таблица большая
- **THEN** запись не встаёт на время создания индекса
"""


def _run(spec, delta):
    return subprocess.run(
        [sys.executable, str(MERGE), str(spec), str(delta)],
        capture_output=True, text=True,
    )


class SpecMergeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.spec = self.tmp / "spec.md"
        self.spec.write_text(СПЕКА, encoding="utf-8")
        self.delta = self.tmp / "delta.md"

    def _delta(self, body):
        self.delta.write_text(f"# Дельта\n\nМеняем spec.md\n\n{body}", encoding="utf-8")
        return self.delta

    ДОБАВЛЕНИЕ = """## Добавлено

### Requirement: Откат миграции

Миграция SHALL быть обратимой.

**Почему**: иначе откат релиза упирается в схему
**ID**: pg-migrations/reversible
**Гейт**: ревью
**Покрытие**: нет
**Не ловит**: всё

#### Scenario: откат релиза

- **WHEN** релиз откатывают
- **THEN** схема возвращается к прежнему виду
"""

    def test_добавленное_требование_дописывается(self):
        result = _run(self.spec, self._delta(self.ДОБАВЛЕНИЕ))

        self.assertEqual(result.returncode, 0, result.stderr)
        текст = self.spec.read_text(encoding="utf-8")
        self.assertIn("pg-migrations/reversible", текст)

    def test_повторный_прогон_ничего_не_меняет(self):
        """Слияние перезапускаемо: второй прогон — не ошибка и не дубль."""
        self._delta(self.ДОБАВЛЕНИЕ)
        _run(self.spec, self.delta)
        после_первого = self.spec.read_text(encoding="utf-8")

        result = _run(self.spec, self.delta)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.spec.read_text(encoding="utf-8"), после_первого)
        self.assertIn("уже слито", result.stdout)

    def test_добавление_с_тем_же_ID_но_другим_текстом_это_конфликт(self):
        конфликт = self.ДОБАВЛЕНИЕ.replace("Миграция SHALL быть обратимой.",
                                           "Миграция SHALL быть какой-то другой.")
        self._delta(self.ДОБАВЛЕНИЕ)
        _run(self.spec, self.delta)

        result = _run(self.spec, self._delta(конфликт))

        self.assertEqual(result.returncode, 1)
        self.assertIn("конфликт", result.stderr.lower())

    def test_изменение_заменяет_блок_целиком(self):
        delta = self._delta("""## Изменено

### Requirement: Таймаут блокировки

Миграция SHALL выставлять `lock_timeout` не больше пяти секунд.

**Почему**: без него миграция висит на чужой транзакции
**ID**: pg-migrations/lock-timeout-required
**Гейт**: страж миграций
**Покрытие**: полное

#### Scenario: долгая транзакция рядом

- **WHEN** рядом идёт долгая транзакция
- **THEN** миграция падает по таймауту

**Что изменилось:** появился гейт и предел в пять секунд
""")

        result = _run(self.spec, delta)

        self.assertEqual(result.returncode, 0, result.stderr)
        текст = self.spec.read_text(encoding="utf-8")
        self.assertIn("не больше пяти секунд", текст)
        self.assertIn("**Гейт**: страж миграций", текст)
        self.assertNotIn("**Покрытие**: нет\n**Не ловит**: всё\n\n#### Scenario: долгая", текст)
        # строка для ревьюера в спеку не переезжает
        self.assertNotIn("Что изменилось", текст)

    def test_изменение_несуществующего_это_конфликт(self):
        delta = self._delta("""## Изменено

### Requirement: Нет такого

Текст.

**ID**: pg-migrations/нет-такого
**Гейт**: ревью
**Покрытие**: нет
**Не ловит**: всё

#### Scenario: раз

- **WHEN** а
- **THEN** б
""")

        result = _run(self.spec, delta)

        self.assertEqual(result.returncode, 1)
        self.assertIn("нет-такого", result.stderr)

    def test_удаление_вырезает_требование(self):
        delta = self._delta("## Удалено\n\n### pg-migrations/index-concurrently\n\n"
                            "**Причина:** правило ушло в другой домен\n")

        result = _run(self.spec, delta)

        self.assertEqual(result.returncode, 0, result.stderr)
        текст = self.spec.read_text(encoding="utf-8")
        self.assertNotIn("index-concurrently", текст)
        self.assertIn("lock-timeout-required", текст)

    def test_удаление_уже_удалённого_не_ошибка(self):
        delta = self._delta("## Удалено\n\n### pg-migrations/index-concurrently\n\n"
                            "**Причина:** правило ушло в другой домен\n")
        _run(self.spec, delta)

        result = _run(self.spec, delta)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("уже слито", result.stdout)

    def test_переименование_применяется_первым(self):
        delta = self._delta("""## Переименовано

- FROM: `pg-migrations/index-concurrently`
- TO: `pg-migrations/index-without-lock`

## Изменено

### Requirement: Индекс без блокировки

Индекс SHALL создаваться CONCURRENTLY и вне транзакции.

**Почему**: обычный CREATE INDEX держит таблицу
**ID**: pg-migrations/index-without-lock
**Гейт**: ревью
**Покрытие**: нет
**Не ловит**: всё

#### Scenario: большая таблица

- **WHEN** таблица большая
- **THEN** запись не встаёт
""")

        result = _run(self.spec, delta)

        self.assertEqual(result.returncode, 0, result.stderr)
        текст = self.spec.read_text(encoding="utf-8")
        self.assertIn("pg-migrations/index-without-lock", текст)
        self.assertNotIn("pg-migrations/index-concurrently", текст)
        self.assertIn("вне транзакции", текст)


if __name__ == "__main__":
    unittest.main()
