---
name: ucp-py-style-review
lang: python
description: Ревью Python-исходников по UCP Python Style Guide (коды PY-*) — нейминг, импорты, выражения, тайп-хинты + mypy --strict, Protocol-порты, форматирование ruff. Узкий скилл: только стиль.
when_to_use: Ревью PR, перед коммитом, онбординг модуля; изменённые .py в git diff.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Python-стиля (ruff / black / mypy)

Ты ревьюишь Python-исходники на соответствие `backend/python/python-style/python-style-rules.md` (`PY-*`). Скилл намеренно
узкий — только **стиль** (нейминг, импорты, выражения, тайп-хинты, форматирование, комментарии). Архитектура,
DDD-инварианты, Use Case Pattern, валидация — другие скиллы.

## Зависимости

- **`.claude/docs/backend/python/python-style/python-style-rules.md`** — правила `PY-*` (код-примеры включены).
- `shared/review-finding-format.md` (`RFF-*`). Связанные коды для cross-ref: `R-ERR-1` (голый except), `R-HEX-3` (Protocol-порты), `PYTS-16` (имена тестов).

## Инструкции

1. **Прочти** `python-style-rules.md`. Цитируй конкретные коды (`PY-2.3`, `PY-4.X1`), не префикс. Гайд обязателен, кроме явного `PY-1.1` (нарушение улучшает читаемость) — тогда автор обосновывает в PR.

2. **Скоп.** Если пользователь назвал файлы — бери их. Иначе `git diff` (working tree/staged/last commit) на `.py`. По умолчанию — изменённые строки; нарушения в окружении — как **Замечание**.

3. **Прогон.**
   - **Именование (`PY-2.*`):** модули `snake_case` (`PY-2.1`); классы `PascalCase`, ошибки на `Error` (`PY-2.2`); функции/переменные `snake_case`, функции-глаголы (`PY-2.3`); константы `UPPER_SNAKE` (`PY-2.4`); приватность один `_`, `__` только для mangling (`PY-2.5`); не `l`/`O`/`I` (`PY-2.6`); имена тестов говорящие (`PY-2.7`, cross-ref `PYTS-16`). Тип в имени (`str_name`) → `PY-2.X1`.
   - **Импорты (`PY-3.*`):** абсолютные (relative → `PY-3.1`); без wildcard (`PY-3.2`); без неиспользуемых, группировка stdlib/third-party/local (`PY-3.3`).
   - **Выражения (`PY-4.*`):** guard clause вместо вложенных `if` (`PY-4.1`); comprehension где читаемо (`PY-4.2`); f-string не `%`/`.format()` (`PY-4.4`); `pathlib`/context manager (`PY-4.5`); булева сложность ≤3 (`PY-4.6`). Мутабельный дефолт `def f(x=[])` → `PY-4.X1`. Голый `except`/`except Exception` без обработки → `PY-4.X2` (cross-ref `R-ERR-1`). Мутация коллекции в итерации → `PY-4.X3`.
   - **Форматирование (`PY-5.*`):** `ruff format`, без ручного выравнивания (`PY-5.1`/`5.3`); единая длина строки (`PY-5.2`).
   - **Тайп-хинты (`PY-6.*`):** публичные сигнатуры аннотированы, `mypy --strict` зелёный (`PY-6.1`); `X | None`/`list[X]` (`PY-6.2`); `Protocol` для портов (`PY-6.3`, cross-ref `R-HEX-3`); деньги `Decimal`, время aware (`PY-6.4`). `Any`/`# type: ignore` без justify → `PY-6.X1`. Аннотация расходится с типом → `PY-6.X2`.
   - **Комментарии (`PY-7.*`):** inline `#` — нет (`PY-7.1`); коды правил в коде — нет (`PY-7.2`); «removed because»/«TODO до» — нет (`PY-7.3`); docstring только для неочевидного контракта, не пересказ сигнатуры (`PY-7.4`). Закомментированный код → `PY-7.X1`. `# noqa`/`# type: ignore` без кода и justify → `PY-7.X2`.
   - **Современные фичи (`PY-8.*`):** `match` вместо `isinstance`-цепочек (`PY-8.1`); `@dataclass(frozen=True, slots=True)` для VO/carrier (`PY-8.2`); `Enum`/`StrEnum` вместо строк-литералов (`PY-8.3`); `@override` на переопределениях (`PY-8.4`).
   - **Enforcement (`PY-RUFF-*`):** `ruff` + `mypy --strict` в `pyproject.toml` и CI (`PY-RUFF-1/2/3`); отключение правил без обоснования → `PY-RUFF-X1`.

4. **Не дублируй ruff/mypy.** Если в проекте есть `[tool.ruff]`/`[tool.mypy]` — упомяни в начале отчёта, что механика (нейминг, импорты, формат) ловится ими, и сосредоточься на семантике, требующей человеческого судьи: мутабельные дефолты (`PY-4.X1`), goly except (`PY-4.X2`), комментарии (`PY-7.*`), `Any`-escape (`PY-6.X1`), читаемость comprehension/walrus.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — голый `except`/`except Exception` без обработки (`PY-4.X2`), мутабельный дефолт-аргумент (`PY-4.X1`), `Any`/`# type: ignore` для обхода mypy (`PY-6.X1`), деньги `float` (`PY-6.4`), inline-комментарии (`PY-7.1`).
   - **Предупреждение** — relative-импорты (`PY-3.1`), wildcard (`PY-3.2`), `Optional`/`List` вместо `X|None`/`list` (`PY-6.2`), закомментированный код (`PY-7.X1`), отключение ruff-правил без justify (`PY-RUFF-X1`), строковые литералы вместо `StrEnum` (`PY-8.3`).
   - **Замечание** — тип в имени (`PY-2.X1`), `match` улучшил бы `isinstance`-цепочку (`PY-8.1`), docstring-пересказ сигнатуры (`PY-7.4`), walrus ради краткости (`PY-8.5`).

## Что не входит

- Архитектура/слои — `ucp-py-pattern-review`. DDD-инварианты — `ucp-py-ddd-tactical-review`. Валидация входа — `ucp-py-validation-review`.
- Обработка ошибок (иерархия/handlers) — `ucp-py-error-handling-review`. Persistence — `ucp-py-sqlalchemy-review`.

$ARGUMENTS
