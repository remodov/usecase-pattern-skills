# Python Style Guide — индекс правил (ruff / black / mypy)

> **Что это.** Сжатый индекс правил Python-стиля: код + формулировка, по разделам. Рабочий вход скиллов —
> review цитирует код в findings. Языко-специфичный concern (аналог Java `java-style` / `JS-*`) — **только
> Python**, префикс `PY-*`. Код-примеры включены (отдельного style-guide нет).
> Коды: `PY-<раздел>.<N>` — рекомендация, `PY-<раздел>.X<N>` — антипаттерн (запрещено), `PY-RUFF-*` —
> enforcement через ruff/mypy. То, что ловит ruff/mypy механически, в findings не дублируем — фокус на семантике.

Базовый принцип (`PY-1.1`): **любое нарушение допустимо, если улучшает читаемость** — ревьюер обязан явно
объяснить, чем нарушение лучше. Цель — читаемость и качество, не формальная проверка. PEP 8 + PEP 484 — база.

## 1. Общие рекомендации
- **PY-1.1.** Нарушение допустимо, если улучшает читаемость; ревьюер обязан объяснить, чем именно. Не индульгенция «писать как хочется».

## 2. Именование
- **PY-2.1.** Модули и пакеты — `snake_case`, короткие, без дефисов и заглавных.
- **PY-2.2.** Классы — `PascalCase` (существительные); исключения — оканчиваются на `Error`.
- **PY-2.3.** Функции, методы, переменные, атрибуты — `snake_case`; функции/методы — глагол/действие (`create_order`, не `order`).
- **PY-2.4.** Константы — `UPPER_SNAKE_CASE` на уровне модуля.
- **PY-2.5.** Приватность — один ведущий `_` (`_internal`); два `__` только для name-mangling в иерархиях, не «ради приватности».
- **PY-2.6.** Не использовать `l`/`O`/`I` как однобуквенные имена; короткие имена (`i`, `n`) — только в узком скоупе.
- **PY-2.7.** Имена тестов — `test_<action>_when_<condition>_<expected>`; говорящие, не сокращения (cross-ref `PYTS-16`).
- **PY-2.X1.** Венгерская нотация и тип в имени (`str_name`, `dict_config`) — тип выражается аннотацией.
- **PY-2.X2.** Поля Pydantic-моделей с именами, затеняющими builtins (`id`, `type`), — без суффикса: использовать `id_`/`type_` + `Field(alias="id"/"type")` (`populate_by_name=True`). Исключение — ORM-модели/БД-DTO и domain-агрегаты, где `id` каноничен.

```python
# PREFER
MAX_RETRIES = 3                              # PY-2.4 константа модуля
class OrderNotFoundError(Exception): ...      # PY-2.2 класс PascalCase, исключение на Error
class OrderRepository: ...                    # PY-2.2 без I-префикса
def find_by_id(order_id: UUID) -> Order: ...  # PY-2.3 метод-глагол
self._session = session                       # PY-2.5 один ведущий _

class OrderResponse(BaseModel):              # PY-2.X2 Pydantic: builtin-имена через суффикс + alias
    model_config = ConfigDict(populate_by_name=True)
    id_: UUID = Field(alias="id")            # → JSON "id", в Python без затенения builtin
    type_: str = Field(alias="type")

# AVOID
class IOrderRepo: ...        # PY-2.2 венгерский I-префикс
def order(): ...             # PY-2.3 имя-существительное вместо глагола
str_name = "x"               # PY-2.X1 тип в имени
class OrderResponse(BaseModel):
    id: UUID                 # PY-2.X2 затеняет builtin id (искл.: ORM-модель/domain-агрегат)
    type: str                # PY-2.X2 затеняет builtin type
```

## 3. Импорты
- **PY-3.1.** Только абсолютные импорты; relative (`from ..mod import x`) — запрещены.
- **PY-3.2.** Без wildcard (`from m import *`) — ломает анализ и mypy.
- **PY-3.3.** Без неиспользуемых импортов; группировка stdlib / third-party / local (сортирует ruff/isort).
- **PY-3.4.** `import module` для модулей, `from module import name` для конкретных имён; не мешать стили ради «короче».

```python
# PREFER
import logging                               # PY-3.4 модуль целиком
from app.core.order import Order             # PY-3.1 абсолютный импорт имени

# AVOID
from ..core.order import Order               # PY-3.1 relative
from app.core.order import *                 # PY-3.2 wildcard
```

## 4. Выражения и код
- **PY-4.1.** Guard clause (ранний `raise`/`return`) вместо вложенных `if/else`.
- **PY-4.2.** Comprehension вместо ручного цикла с `append`; но вложенные/многоусловные — обычным циклом (читаемость).
- **PY-4.3.** EAFP (`try/except`) для ожидаемо-редких сбоев; LBYL — где проверка дешевле исключения.
- **PY-4.4.** f-string вместо `%`/`.format()`/конкатенации.
- **PY-4.5.** `pathlib.Path` вместо `os.path`-конкатенации; ресурсы — через `with` (context manager).
- **PY-4.6.** Булево выражение — не более 3 операторов `and`/`or`; сложнее — выделить именованный предикат.
- **PY-4.X1.** Мутабельный аргумент по умолчанию (`def f(x=[])`) — общий между вызовами; использовать `None` + инициализацию в теле.
- **PY-4.X2.** Голый `except:` или `except Exception` без re-raise/обработки (cross-ref `R-ERR-1`).
- **PY-4.X3.** Изменение коллекции во время итерации по ней.

```python
# PY-4.1 guard clause — PREFER
def charge(order: Order) -> None:
    if order.is_paid:
        return
    provider.charge(order)
# AVOID — вложенность
def charge(order: Order) -> None:
    if not order.is_paid:
        if order.amount > 0:
            provider.charge(order)

# PY-4.4  f-string, не %/.format()
message = f"order {order.id} declined"

# PY-4.X1 mutable default — AVOID → PREFER
def collect(items: list[str] = []) -> None: ...        # AVOID: общий список между вызовами
def collect(items: list[str] | None = None) -> None:   # PREFER
    items = items if items is not None else []

# PY-4.X2 — AVOID
try:
    provider.charge(order)
except Exception:        # проглатывание без re-raise/обработки
    pass
```

## 5. Форматирование
- **PY-5.1.** Форматирование — `ruff format` (black-совместимо); руками не выравнивать.
- **PY-5.2.** Длина строки — единая в проекте (`ruff` line-length, дефолт 88 либо командные 120); не «как получилось».
- **PY-5.3.** Без горизонтального выравнивания присваиваний/словарей — шумит в diff.

## 6. Тайп-хинты и mypy
- **PY-6.1.** Все публичные сигнатуры (функции, методы, атрибуты dataclass) аннотированы; `mypy --strict` зелёный.
- **PY-6.2.** `X | None` вместо `Optional[X]`, `list[X]`/`dict[K,V]` вместо `List`/`Dict` (3.10+).
- **PY-6.3.** `Protocol` для структурной типизации портов/интерфейсов (cross-ref `R-HEX-3`); `ABC` — когда нужна реализация/иерархия.
- **PY-6.4.** Деньги — `Decimal`, не `float`; время — aware `datetime` (cross-ref `R-VO`, `PG-T-011/030`).
- **PY-6.X1.** `Any` как способ заглушить mypy; `# type: ignore` без кода правила и justify-комментария (исключение из `PY-7`, см. `PY-RUFF-3`).
- **PY-6.X2.** Аннотации, расходящиеся с реальным типом (формальная типизация ради галочки).

```python
from decimal import Decimal
from datetime import datetime
from typing import Protocol

# PY-6.2 PREFER
def find(order_id: UUID) -> Order | None: ...     # не Optional[Order]
items: list[Order]                                # не List[Order]

# PY-6.3 порт — Protocol (структурная типизация)
class OrderPort(Protocol):
    async def save(self, order: Order) -> None: ...

# PY-6.4 деньги/время
amount: Decimal           # не float
created_at: datetime      # aware (tzinfo=UTC), не naive
```

## 7. Комментарии
- **PY-7.1.** Inline-комментариев (`#`) в коде нет — ни в production, ни в тестах. Неочевидный WHY выражается именем, структурой или спекой (`[[feedback-no-code-comments]]`).
- **PY-7.2.** Не цитировать коды правил/спеки в коде (`R-AGG-1`, `PYTS-9`, `AUTH-15`) — дублирует source-of-truth, шум; коды — в commit/PR.
- **PY-7.3.** Не писать «что тут было»/«removed because»/«TODO до …» — источник изменений `git blame`.
- **PY-7.4.** Docstring — только где добавляет неочевидный контракт (инвариант, единицы, побочный эффект); не пересказ сигнатуры, не для каждой функции.
- **PY-7.X1.** Закомментированный код — удалять, не оставлять.
- **PY-7.X2.** `# type: ignore`/`# noqa` без кода и обоснования (`# noqa: E501  # justify: ...`).

## 8. Современные фичи (Python 3.12+)
- **PY-8.1.** `match`/`case` для разбора структур/sealed-подобных иерархий вместо `isinstance`-цепочек; деструктуризация в паттерне.
- **PY-8.2.** `@dataclass(frozen=True, slots=True)` для иммутабельных carrier'ов/VO вместо ручных `__init__`/`__eq__`.
- **PY-8.3.** `enum.Enum`/`StrEnum` для closed-набора значений, не строковые литералы.
- **PY-8.4.** `type Alias = ...` (3.12) для сложных типов; `@override` (3.12) на переопределённых методах.
- **PY-8.5.** Walrus (`:=`) — только когда сокращает дублирование и читаемо; не ради краткости.

```python
from dataclasses import dataclass
from enum import StrEnum

# PY-8.2 иммутабельный carrier/VO
@dataclass(frozen=True, slots=True)
class CreateOrder:
    order_id: UUID
    amount: Decimal

# PY-8.3 StrEnum для closed-набора, не строковые литералы
class OrderStatus(StrEnum):
    PENDING = "PENDING"
    BOOKED = "BOOKED"
```

## 9. Enforcement через ruff + mypy
- **PY-RUFF-1.** `ruff` (lint + format) обязателен на всех Python-сервисах; конфиг в `pyproject.toml` (`[tool.ruff]`), не разрозненные `.flake8`/`.isort.cfg`.
- **PY-RUFF-2.** `mypy --strict` в CI; ослабление — только per-module override в `pyproject.toml` с обоснованием.
- **PY-RUFF-3.** `ruff check` + `ruff format --check` + `mypy` на каждом CI-прогоне; fail при нарушении. `# noqa`/`# type: ignore` — только с кодом и justify.
- **PY-RUFF-4.** ruff покрывает механику (нейминг `PY-2.*`, импорты `PY-3.*`, формат `PY-5.*`); семантику (`PY-4.*`/`PY-6.*`/`PY-7.*`/`PY-8.*`) — `ucp-py-style-review`.
- **PY-RUFF-X1.** Отключение правил «потому что мешают» без обсуждения — расхождение conventions между сервисами.

---

## Приложение A. PEP 8 — полный справочник

> Свод [PEP 8](https://peps.python.org/pep-0008/) (+ [PEP 257](https://peps.python.org/pep-0257/) для docstring).
> Механику (раскладка, whitespace, импорты, нейминг) ловит **`ruff`** (наборы `E`/`W`/`F`/`I`/`N`, коды в скобках) —
> в findings её не дублируем (`PY-RUFF-4`), это reference. Семантику разбирает `ucp-py-style-review`. Где команда
> **отклоняется** от дефолта PEP 8 — помечено **[override]**.

### A.1 Главный принцип
- Консистентность важнее буквы: единообразие внутри модуля > внутри проекта > PEP 8. Нарушай, только если правило снижает читаемость (cross-ref `PY-1.1`).

### A.2 Раскладка кода (Code Lay-out)
- **Отступ — 4 пробела на уровень**, табы запрещены (mixed tabs/spaces — синтаксическая ошибка в Py3) (`ruff: E101/W191`).
- **Перенос длинных конструкций:** вертикальное выравнивание по открывающей скобке либо «висячий» отступ; продолжения отличимы от тела (`ruff: E12x`).
- **Длина строки — 88** (`ruff format` дефолт) либо командные **120** **[override: PEP 8 = 79/72]**; docstring/комментарии — в ту же ширину (`ruff: E501`, cross-ref `PY-5.2`).
- **Перенос по бинарному оператору — ПЕРЕД оператором** (Knuth-style: `+`/`and` в начале новой строки) (`ruff: W503/W504`).
- **Пустые строки:** 2 между top-level функциями/классами, 1 между методами класса; логические группы внутри функции — скупо (`ruff: E301/E302/E303/E305`).
- **Кодировка — UTF-8**, без декларации `# -*- coding -*-`; идентификаторы по возможности ASCII.
- **Импорты:** каждый на своей строке; порядок групп stdlib → third-party → local, между группами пустая строка; абсолютные; без wildcard; в начале файла после docstring/`__future__` (`ruff: E401/E402/F401/F403`, cross-ref `PY-3.*`).
- **Module-level dunder** (`__all__`, `__version__`) — после docstring, до импортов (кроме `from __future__`).

### A.3 Строковые литералы
- Один стиль кавычек в проекте — **двойные** (`ruff format`); тройные docstring — `"""` (PEP 257). Не выравнивать смену кавычек ради экранирования — выбрать те, что дают меньше `\`.

### A.4 Пробелы в выражениях (Whitespace)
- **Нет пробела** сразу внутри `()`/`[]`/`{}`; перед `,`/`;`/`:`; перед `(` вызова и `[` индекса (`ruff: E201/E202/E203/E211`).
- **Пробелы вокруг** бинарных операторов и `=` в присваивании; **без пробелов** вокруг `=` в kwargs/дефолтах (`f(x=1)`), **но** с пробелами если у аргумента есть аннотация (`def f(x: int = 1)`) (`ruff: E225/E251`).
- Один пробел после `,`; не больше одного пробела для «выравнивания» (cross-ref `PY-5.3`); slice `:` как бинарный оператор с равными отступами.
- Не ставить `;` для нескольких операторов в строке; одно выражение — одна строка (`ruff: E70x`).

### A.5 Trailing commas
- Висячая запятая обязательна в многострочных литералах/сигнатурах (чистый diff, `ruff format` ставит); в однострочном кортеже из 1 элемента — `(x,)`.

### A.6 Комментарии (cross-ref `PY-7.*`, PEP 257)
- Комментарии — полными предложениями, актуальны коду; устаревший комментарий хуже отсутствующего.
- Block-комментарий — на уровне кода, каждая строка с `# `; inline — редко, ≥2 пробела до `#` (`ruff: E261/E262/E265`). В этом проекте inline-комментарии в коде запрещены (`PY-7.1`) — WHY выражается именем/структурой.
- **Docstring** (PEP 257) — для публичных модулей/классов/функций, где добавляет контракт; `"""..."""`, императив («Return…»), закрывающие `"""` на отдельной строке для многострочных (cross-ref `PY-7.4`).

### A.7 Соглашения об именовании (Naming, cross-ref `PY-2.*`, `ruff: N8xx`)
- `lower_case_with_underscores` — модули, пакеты (пакеты — без подчёркиваний по возможности), функции, методы, переменные, аргументы.
- `CapWords`/PascalCase — классы, type-aliases, `TypeVar` (`T`, `OrderT`); исключения — классы на `Error`.
- `UPPER_CASE_WITH_UNDERSCORES` — константы уровня модуля.
- Один ведущий `_` — внутреннее (non-public); два ведущих `__` — name-mangling в иерархии; `trailing_` — обойти конфликт с ключевым словом/builtin (`class_`, `id_`, `type_`, cross-ref `PY-2.X2`).
- `self` — первый аргумент метода, `cls` — classmethod.
- **Избегать** имён `l`, `O`, `I` (неотличимы от цифр); венгерской нотации/типа в имени (`PY-2.X1`).

### A.8 Рекомендации по коду (Programming Recommendations)
- Сравнение с `None` — через `is`/`is not`, не `==` (`ruff: E711`); с булевым — `if flag:`, не `== True`/`is True` (`ruff: E712`).
- «Не пусто/пусто» для последовательностей — по truthiness (`if items:` / `if not items:`), не `len(...) == 0`.
- Отрицание — `if x is not None`, не `if not x is None`.
- Ловить **конкретные** исключения, не голый `except:`/`except Exception` без re-raise (`ruff: E722`, cross-ref `PY-4.X2`); тело `try` — минимально.
- `def`, а не присваивание `lambda` переменной (`ruff: E731`); функция либо всегда возвращает значение, либо всегда `None` — консистентно.
- `str.startswith()`/`.endswith()` вместо срезов; `isinstance(x, T)` вместо сравнения `type(x) == T`.
- Не выполнять flow-control (`return`/`break`) в `finally`, гасящий исключение; контекст-менеджеры (`with`) для ресурсов (cross-ref `PY-4.5`).
- `functools`/comprehension вместо ручных циклов где читаемо (cross-ref `PY-4.2`); f-strings вместо `%`/`.format()` (`PY-4.4`).
