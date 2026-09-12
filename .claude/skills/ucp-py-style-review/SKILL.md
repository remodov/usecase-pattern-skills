---
name: ucp-py-style-review
lang: python
description: Ревью Python-исходников по требованиям `python-style/*` — нейминг, импорты, выражения, тайп-хинты + mypy --strict, Protocol-порты, форматирование ruff. Узкий скилл: только стиль.
when_to_use: Ревью PR, перед коммитом, онбординг модуля; изменённые .py в git diff.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Python-стиля (ruff / black / mypy)

Ты ревьюишь Python-исходники на соответствие `backend/python/python-style/spec.md` (`PY-*`). Скилл намеренно
узкий — только **стиль** (нейминг, импорты, выражения, тайп-хинты, форматирование, комментарии). Архитектура,
DDD-инварианты, Use Case Pattern, валидация — другие скиллы.

## Зависимости

- **`.claude/docs/backend/python/python-style/spec.md`** — правила `PY-*` (код-примеры включены).
- `shared/review-format/spec.md` (`review-format/*`). Связанные коды для cross-ref: `error-handling/exceptions-are-part-of-contract` (голый except), `hexagonal/outbound-port-interface-in-core` (Protocol-порты), `python-test-strategy/test-name-states-scenario` (имена тестов).

## Инструкции

1. **Прочти** `python-style/spec.md`. Цитируй конкретные коды (`python-style/naming-conventions`, `python-style/no-mutable-default-argument`), не префикс. Гайд обязателен, кроме явного `python-style/deviation-requires-justification` (нарушение улучшает читаемость) — тогда автор обосновывает в PR.

2. **Скоп.** Если пользователь назвал файлы — бери их. Иначе `git diff` (working tree/staged/last commit) на `.py`. По умолчанию — изменённые строки; нарушения в окружении — как **Замечание**.

3. **Прогон.**
   - **Именование (`PY-2.*`):** модули `snake_case` (`python-style/naming-conventions`); классы `PascalCase`, ошибки на `Error` (`python-style/naming-conventions`); функции/переменные `snake_case`, функции-глаголы (`python-style/naming-conventions`); константы `UPPER_SNAKE` (`python-style/naming-conventions`); приватность один `_`, `__` только для mangling (`python-style/privacy-and-short-names`); не `l`/`O`/`I` (`python-style/privacy-and-short-names`); имена тестов говорящие (`python-style/test-naming`, cross-ref `python-test-strategy/test-name-states-scenario`). Тип в имени (`str_name`) → `python-style/no-type-in-name`.
   - **Импорты (`PY-3.*`):** абсолютные (relative → `python-style/imports-are-absolute-and-explicit`); без wildcard (`python-style/imports-are-absolute-and-explicit`); без неиспользуемых, группировка stdlib/third-party/local (`python-style/imports-are-absolute-and-explicit`).
   - **Выражения (`PY-4.*`):** guard clause вместо вложенных `if` (`python-style/expressions-stay-simple`); comprehension где читаемо (`python-style/expressions-stay-simple`); f-string не `%`/`.format()` (`python-style/expressions-stay-simple`); `pathlib`/context manager (`python-style/expressions-stay-simple`); булева сложность ≤3 (`python-style/expressions-stay-simple`). Мутабельный дефолт `def f(x=[])` → `python-style/no-mutable-default-argument`. Голый `except`/`except Exception` без обработки → `python-style/no-bare-except` (cross-ref `error-handling/exceptions-are-part-of-contract`). Мутация коллекции в итерации → `python-style/no-mutation-during-iteration`.
   - **Форматирование (`PY-5.*`):** `ruff format`, без ручного выравнивания (`python-style/formatting-by-tool`/`5.3`); единая длина строки (`python-style/formatting-by-tool`).
   - **Тайп-хинты (`PY-6.*`):** публичные сигнатуры аннотированы, `mypy --strict` зелёный (`python-style/typed-public-signatures`); `X | None`/`list[X]` (`python-style/typed-public-signatures`); `Protocol` для портов (`python-style/ports-via-protocols`, cross-ref `hexagonal/outbound-port-interface-in-core`); деньги `Decimal`, время aware (`python-style/decimal-money-aware-datetime`). `Any`/`# type: ignore` без justify → `python-style/no-silencing-type-checks`. Аннотация расходится с типом → `python-style/no-silencing-type-checks`.
   - **Комментарии (`PY-7.*`):** inline `#` — нет (`python-style/no-comments-in-code`); коды правил в коде — нет (`python-style/no-comments-in-code`); «removed because»/«TODO до» — нет (`python-style/no-comments-in-code`); docstring только для неочевидного контракта, не пересказ сигнатуры (`python-style/docstrings-add-contract`). Закомментированный код → `python-style/no-comments-in-code`. `# noqa`/`# type: ignore` без кода и justify → `python-style/suppressions-are-justified`.
   - **Современные фичи (`PY-8.*`):** `match` вместо `isinstance`-цепочек (`python-style/modern-constructs`); `@dataclass(frozen=True, slots=True)` для VO/carrier (`python-style/modern-constructs`); `Enum`/`StrEnum` вместо строк-литералов (`python-style/modern-constructs`); `@override` на переопределениях (`python-style/modern-constructs`).
   - **Enforcement (`PY-RUFF-*`):** `ruff` + `mypy --strict` в `pyproject.toml` и CI (`PY-RUFF-1/2/3`); отключение правил без обоснования → `python-style/lint-and-types-are-enforced`.

4. **Не дублируй ruff/mypy.** Если в проекте есть `[tool.ruff]`/`[tool.mypy]` — упомяни в начале отчёта, что механика (нейминг, импорты, формат) ловится ими, и сосредоточься на семантике, требующей человеческого судьи: мутабельные дефолты (`python-style/no-mutable-default-argument`), goly except (`python-style/no-bare-except`), комментарии (`PY-7.*`), `Any`-escape (`python-style/no-silencing-type-checks`), читаемость comprehension/walrus.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — голый `except`/`except Exception` без обработки (`python-style/no-bare-except`), мутабельный дефолт-аргумент (`python-style/no-mutable-default-argument`), `Any`/`# type: ignore` для обхода mypy (`python-style/no-silencing-type-checks`), деньги `float` (`python-style/decimal-money-aware-datetime`), inline-комментарии (`python-style/no-comments-in-code`).
   - **Предупреждение** — relative-импорты (`python-style/imports-are-absolute-and-explicit`), wildcard (`python-style/imports-are-absolute-and-explicit`), `Optional`/`List` вместо `X|None`/`list` (`python-style/typed-public-signatures`), закомментированный код (`python-style/no-comments-in-code`), отключение ruff-правил без justify (`python-style/lint-and-types-are-enforced`), строковые литералы вместо `StrEnum` (`python-style/modern-constructs`).
   - **Замечание** — тип в имени (`python-style/no-type-in-name`), `match` улучшил бы `isinstance`-цепочку (`python-style/modern-constructs`), docstring-пересказ сигнатуры (`python-style/docstrings-add-contract`), walrus ради краткости (`python-style/modern-constructs`).

## Что не входит

- Архитектура/слои — `ucp-py-pattern-review`. DDD-инварианты — `ucp-py-ddd-tactical-review`. Валидация входа — `ucp-py-validation-review`.
- Обработка ошибок (иерархия/handlers) — `ucp-py-error-handling-review`. Persistence — `ucp-py-sqlalchemy-review`.

$ARGUMENTS
