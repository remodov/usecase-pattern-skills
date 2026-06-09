# Hexagonal Architecture — Python Style Guide (пакеты + import-linter)

Реализация язык-нейтрального контракта `../hexagonal-rules.md` (`R-HEX-*`) на Python. Коды общие с Java; меняется
**механизм изоляции**: вместо multi-module Gradle + ArchUnit — единое дерево пакетов с **layered-контрактом
`import-linter`**, проверяемым в CI. В Python нет compile-time изоляции модулей, поэтому import-linter — не
украшение, а единственный enforcement границ.

## 1. Когда переходить (`R-HEX-WHEN-*`)

`R-HEX-WHEN-1` — Hexagonal = Уровень 3 (DDD + ports/adapters + import-linter). Уровень 1–2 — overkill: плоский
`app/` без слоёв. `R-HEX-WHEN-X1` — cargo-cult (сервис из 3 эндпоинтов в полной раскладке) — ceremony.
`R-HEX-WHEN-X2` — частичный Hexagonal (есть `core/`, но роутеры мешают бизнес-логику с HTTP) — либо полностью, либо никак.

## 2. Структура (`R-HEX-MOD-*`)

Вместо gradle-модулей — пакеты с контрактом import-linter. `R-HEX-MOD-1`/`R-HEX-MOD-2` — `core/` не импортирует
ничего инфраструктурного (ни FastAPI, ни SQLAlchemy, ни Pydantic):

```
src/<service>/
  core/<bc>/{aggregate,entity,value_object,event,port,usecase,service}/
  adapters/in/http/            # FastAPI-роутеры (R-HEX-AIN)
  adapters/out/persistence/    # SQLAlchemy (R-HEX-AOUT)
  adapters/out/<system>/       # httpx-клиент к внешней системе (per-system)
  app/                         # composition root: main, container, lifespan, settings
```

```toml
# pyproject.toml — контракт зависимостей слоёв
[tool.importlinter]
root_package = "service"

[[tool.importlinter.contracts]]
name = "layers"
type = "layers"
layers = ["service.app", "service.adapters", "service.core"]
```

`R-HEX-MOD-X1` — отсутствие import-linter-контракта (полагаться на дисциплину) — кто-нибудь импортнёт SQLAlchemy в
`core/` и никто не заметит. `R-HEX-MOD-X2` — `core/` импортирует `adapters/*` — стрелка всегда `app → adapters → core`.
`R-HEX-MOD-X3` — user- и admin-роутеры в одном модуле без разделения — теряется изоляция security (отдельные пакеты
`adapters/in/http/{user,admin}/` + contract).

## 3. Core (`R-HEX-CORE-*`)

`R-HEX-CORE-1` — `core/` зависит только от stdlib + доменных типов. `R-HEX-CORE-4` — rich domain: логика в
агрегате (`order.confirm()`), не в `*Service` (cross-ref `R-AGG-2`, `ucp-py-ddd-tactical-*`).

`R-HEX-CORE-X1` — FastAPI-импорт в `core/` (enforce import-linter). `R-HEX-CORE-X2` — SQLAlchemy-импорт в `core/`
(ORM — деталь persistence; маппинг в `adapters/out/persistence/<x>_mapper.py`, cross-ref `R-SQLA-MAP-1`).
`R-HEX-CORE-X3` — анемичная модель. `R-HEX-CORE-X4` — ORM-модель как доменный тип в `core/`. `R-HEX-CORE-X5` —
Pydantic REST-DTO (`CreateOrderRequest`) в `core/` — деталь in-adapter.

## 4. Ports (`R-HEX-PORT-*`)

`R-HEX-PORT-1` — outbound-порт = `Protocol` в `core/<bc>/port/out/`, описывает что нужно core (cross-ref
`R-REP-1`, `R-HEX-3`). `R-HEX-PORT-2` — методы порта оперируют domain-типами, не DTO внешней системы.
`R-HEX-PORT-3` — port-исключения объявлены в `core/` (`PaymentPortError`); подклассы (`SberError`) — в out-adapter;
handler ловит базовый. `R-HEX-PORT-4` — inbound-порт = UseCase + Handler (вход через `Dispatcher`), отдельный
«InboundPort» не нужен.

`R-HEX-PORT-X1` — порт объявлен в out-adapter (порт — контракт core). `R-HEX-PORT-X2` — DTO внешней системы в
сигнатуре порта (адаптер мапит внутри). `R-HEX-PORT-X3` — `X | None` из порта, где отсутствие = ошибка (брось
доменное `OrderNotFoundError`). `R-HEX-PORT-X4` — порт как класс, не `Protocol`/ABC — убивает подмену в тестах.

## 5. Adapters in (`R-HEX-AIN-*`)

`R-HEX-AIN-1` — пакет `adapters/in/http/` на HTTP-вход (+ отдельные пакеты на другие типы входа: kafka-consumer).
`R-HEX-AIN-2`/`R-HEX-AIN-3` — роутер маппит Pydantic request-DTO → UseCase command, зовёт `Dispatcher`; отдельный
маппер (`order_request_mapper.py`), не возвращай domain-агрегат как HTTP-ответ. `R-HEX-AIN-4` — in-adapter знает
FastAPI/Pydantic, не знает про `adapters/out/*`.

`R-HEX-AIN-X1` — бизнес-логика в роутере (`if req.amount > 100`). `R-HEX-AIN-X2` — роутер зовёт репозиторий
напрямую (только через `Dispatcher` → Handler, cross-ref `R-DSP-1`). `R-HEX-AIN-X3` — роутер возвращает domain-агрегат
наружу (маппи в response-DTO). `R-HEX-AIN-X4` — `adapters/in/*` импортирует `adapters/out/*` — адаптеры зависят от
`core/`, не друг от друга.

## 6. Adapters out (`R-HEX-AOUT-*`)

`R-HEX-AOUT-1` — пакет `adapters/out/<system>/` на каждую внешнюю систему (per-system isolation, cross-ref
`R-RES-ISO-1`). `R-HEX-AOUT-2` — адаптер реализует порт-`Protocol` из `core/`. `R-HEX-AOUT-3` — маппер domain ↔ DTO
внешней системы в адаптере. `R-HEX-AOUT-4` — адаптер знает свою инфраструктуру (`persistence/` — SQLAlchemy;
`sber/` — httpx + Sber-DTO), не знает другие адаптеры.

`R-HEX-AOUT-X1` — адаптер возвращает DTO внешней системы из порт-метода (только domain). `R-HEX-AOUT-X2` —
бизнес-логика в out-adapter (`if sber_response.code == 1`); адаптер мапит, решает handler. `R-HEX-AOUT-X3` — один
адаптер реализует порты разных доменов. `R-HEX-AOUT-X4` — out-adapter инжектит другой out-adapter (координация двух —
это use case в `core/`, handler инжектит оба порта).

## 7. Composition root (`R-HEX-BOOT-*`)

`R-HEX-BOOT-1`/`R-HEX-BOOT-3` — `app/` = composition root: `create_app()` factory, `container` (DI-wiring портов на
адаптеры), `lifespan`, `settings`, `Dockerfile` (cross-ref `PYBOOT-5/8`). Зависит от `core/` + всех адаптеров; от
`app/` не зависит никто.

`R-HEX-BOOT-X1` — бизнес-логика/роутеры в `app/` (только композиция и конфиг). `R-HEX-BOOT-X2` — создание FastAPI-app
или wiring в `core/`/`adapters/*` — только в `app/`.

## 8. Архитектурные тесты (`R-HEX-TEST-*`)

`R-HEX-TEST-1`/`R-HEX-TEST-2` — `import-linter` (контракт layers + при необходимости forbidden/independence) запускается
в CI как required check; PR не мерджится при падении. Это аналог ArchUnit — compile-time-подобный guard на
импортах. `R-HEX-TEST-3` — единый `root_package` в контракте.

`R-HEX-TEST-X1` — только code-review для enforcement границ — человек пропустит импорт; нужен `lint-imports` в CI.

## 9. Чеклист подключения к новому сервису (Python)

1. `core/` без FastAPI/SQLAlchemy/Pydantic (контракт import-linter зелёный).
2. Стрелка зависимостей `app → adapters → core`; адаптеры не зависят друг от друга.
3. Порты — `Protocol` в `core/<bc>/port/out/`, оперируют domain-типами.
4. Роутеры через `Dispatcher`, не репозиторий напрямую; маппинг REST-DTO ↔ command/response.
5. out-adapter реализует порт, мапит domain ↔ DTO, без бизнес-логики; per-system пакеты.
6. `app/` — только композиция; `create_app()`/container/lifespan.
7. `import-linter` в CI как required check.
