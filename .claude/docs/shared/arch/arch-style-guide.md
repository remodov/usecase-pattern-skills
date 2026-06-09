# Architecture Consistency Style Guide

Свод правил **платформенной согласованности** артефактов в корпусе `architecture/` — реестра сервисов, context map, ubiquitous language, владения данными, бизнес-процессов, контрактов и синхронизации карточек сервисов со спеками. Каждое правило идентифицируется кодом (`R-ARCH-REG-1`, `R-ARCH-BP-X1` — где X-нумерация была бы для антипаттернов, но в этом гайде все правила MUST) — скилл `ucp-arch-consistency-review` цитирует эти коды в findings.

Гайд работает на уровне **корпуса**, не на уровне отдельного сервиса. Внутрисервисные правила покрывают другие гайды (`distributed-patterns-style-guide.md`, `kafka-style-guide.md`, `ddd-tactical-style-guide.md`, …). Здесь — про **связи**: симметрию объявлений, single-publisher событий, owner-edits-only, синхронизацию карточка ↔ спека, и т.д.

Не покрывает: содержание ADR (это процесс), детализацию sequence-диаграмм в BP (это `ucp-arch-bp-design`), внутреннюю кодовую структуру сервисов.

Связанные стандарты:
- `R-DIST-COMP-*` — semantic compensation, не DELETE (используется в `R-ARCH-BP-4`).
- `R-DIST-IDEM-*` — idempotency для money (используется в `R-ARCH-BP-5`).
- `R-KFK-EV-*` — обязательные поля события (`eventId`, `eventType`, `version`; используется в `R-ARCH-CONTR-2`).
- `ADR-0001` — определение tier-ов сервисов (используется в `R-ARCH-REG-1`).
- `ADR-0002` — owner-edits-only (используется в `R-ARCH-DATA-3`).

---

## Содержание

1. [Реестр и владение — `R-ARCH-REG-*`](#1-реестр-и-владение)
2. [Context map — `R-ARCH-CTX-*`](#2-context-map)
3. [Ubiquitous Language — `R-ARCH-UL-*`](#3-ubiquitous-language)
4. [Владение данными — `R-ARCH-DATA-*`](#4-владение-данными)
5. [Бизнес-процессы — `R-ARCH-BP-*`](#5-бизнес-процессы)
6. [Контракты — `R-ARCH-CONTR-*`](#6-контракты)
7. [Синхронизация со спеками — `R-ARCH-SPEC-*`](#7-синхронизация-со-спеками)
8. [Применение](#8-применение)
9. [Антипаттерны — сводка](#9-антипаттерны)

---

## 1. Реестр и владение

`_registry.yaml` — центральный реестр сервисов корпуса. Это единственная точка истины «какие сервисы существуют, кто владелец, какой tier». Все остальные документы (BP, context map, ADR) ссылаются на сервисы по имени из реестра.

### 1.1 Обязательно

### R-ARCH-REG-1

Каждый сервис в `_registry.yaml` имеет поля `owner`, `tier`, `subdomain`. Без `owner` некого позвать при инциденте, без `tier` (см. `ADR-0001`) нельзя понять criticality и применяемые SLO, без `subdomain` сервис вырван из доменной карты.

Detection: парсинг YAML, для каждого элемента `services[]` проверить наличие всех трёх полей.

```yaml
# Корректно
services:
  - name: order-service
    owner: orders-team
    tier: 1
    subdomain: ordering

# Нарушение R-ARCH-REG-1: нет owner и tier
services:
  - name: legacy-service
    subdomain: ordering
```

### R-ARCH-REG-2

Соответствие 1:1 между папкой `services/<name>/` и записью в `_registry.yaml`. Orphan-папка значит сервис уже не support'ится, но карточка осталась → новый разработчик читает мёртвый код как живой. Orphan-запись — карточка обещана, но не создана → ссылки в BP/context map ведут в никуда.

Detection: `ls services/` vs `yq '.services[].name' _registry.yaml`, обе разницы (left-only, right-only) должны быть пустыми.

### R-ARCH-REG-3

Сервис, помеченный `archived: true` в реестре, не упомянут в активных BP-файлах в `docs/business-processes/`. Если архивный сервис фигурирует в шаге BP — это значит BP описывает несуществующий шаг (либо BP устарел, либо архивация ошибочна).

Detection: для каждого сервиса с `archived: true` — `grep -r "<service-name>" docs/business-processes/`. Любое упоминание — нарушение (исключение: явная пометка «historical, см. BP-XX до 2024-Q3»).

---

## 2. Context map

Context map описывает связи между bounded context-ами: customer-supplier, conformist, anti-corruption-layer, shared-kernel. Связи объявляются в карточках сервисов (`services/<name>/README.md`, секция «Связи»).

### 2.1 Обязательно

### R-ARCH-CTX-1

Связь между BC симметрично объявлена в обеих карточках. Если `services/order/README.md` говорит «Catalog — customer-supplier (Catalog supplier для нас)», то `services/catalog/README.md` упоминает Order как customer. Асимметрия = дрейф знаний: одна команда считает связь существующей, другая о ней не знает.

Detection: парсинг секции «Связи» в каждой карточке, построение графа, кросс-чек симметрии (каждое ребро должно встречаться в обоих узлах).

### R-ARCH-CTX-2

Связь типа `shared-kernel` требует существующего ADR с обоснованием. Shared-kernel — антипаттерн в большинстве случаев: общий код = совместный релиз = de facto monolith. Если команда осознанно идёт на shared-kernel — это решение должно быть зафиксировано в ADR с альтернативами и trade-off'ами.

Detection: grep `shared-kernel` в карточках; каждое упоминание должно содержать ссылку на ADR (`см. ADR-XXXX`), и этот ADR существовать в `docs/adr/`.

### R-ARCH-CTX-3

Каждое событие в `contracts/events/_index.md` имеет ровно одного publisher-сервиса. Два publisher'а одного и того же события — confusion (кому верить?), race conditions (порядок событий не определён), нарушение ownership (consumer не знает, чьи инварианты соблюдаются).

Detection: парсинг `contracts/events/_index.md` + сравнение с `services/*/contracts/asyncapi.y*ml`. Для каждого `eventType` собрать множество publisher-ов; mocking|count > 1 — нарушение.

---

## 3. Ubiquitous Language

`docs/architecture/02-ubiquitous-language.md` — глоссарий доменных терминов корпуса. Каждый термин имеет одно определение, либо явно помечен как omonym разных контекстов.

### 3.1 Обязательно

### R-ARCH-UL-1

Термин из `02-ubiquitous-language.md` встречается в спеках сервисов с тем же определением. Расхождение определений без явной пометки omonym → конфликт UL: разработчики говорят разными словами об одном понятии или одним словом о разных понятиях, и это утекает в код и API.

Detection: grep термина по всем `services/*/spec/`, извлечь окружающее определение (заголовок секции «Глоссарий» в спеках), сравнить с центральным UL. Расхождение без пометки `omonym` — нарушение.

```markdown
# 02-ubiquitous-language.md (корпус)
**Refund** — возврат денежных средств покупателю после оплаченной транзакции.

# services/order/spec/order-spec.md
**Refund** — отмена резервации товара (если ещё не оплачено). // Нарушение R-ARCH-UL-1
```

### R-ARCH-UL-2

Дублирующиеся имена агрегатов между сервисами (например `Order.Refund` vs `Payment.Refund`) допустимы только если в `02-ubiquitous-language.md` отмечены как omonym разных контекстов с явной нотацией.

Detection: парсинг секций «Домен-агрегаты» в карточках, поиск дублирующихся имён; для каждого дубля — проверка пометки в UL.

```markdown
# 02-ubiquitous-language.md
**Refund** (omonym):
- В Payment BC — финансовый возврат.
- В Order BC — отмена резерва товара до оплаты.
```

---

## 4. Владение данными

`docs/architecture/03-data-ownership.md` — таблица «сущность → owner-сервис». Это операционализация DDD-границ: кто имеет право писать в эту сущность.

### 4.1 Обязательно

### R-ARCH-DATA-1

Каждая сущность в `03-data-ownership.md` имеет ровно одного owner-сервис. Два владельца — consistency-конфликт: write от A и B нельзя сериализовать без распределённой транзакции (которая запрещена `R-DIST-TX-X1`).

Detection: парсинг таблицы ownership, group by entity, count owners; > 1 — нарушение.

### R-ARCH-DATA-2

Нет двух сервисов, заявляющих один и тот же агрегат как aggregate-root в своих спеках. Это прямое нарушение DDD-границ: aggregate-root инкапсулирует инварианты, и эти инварианты не могут быть распределены.

Detection: парсинг секций «Домен-агрегаты» в карточках, кросс-чек: один и тот же агрегат не должен фигурировать как root у двух сервисов (но может — как reference у consumer, это нормально).

### R-ARCH-DATA-3

Consumer не имеет write-UC на чужие сущности — owner-edits-only (см. `ADR-0002`). Если сервис A читает сущность сервиса B, у A не может быть UC, который изменяет state этой сущности — только через команду к B.

Detection: парсинг таблицы UC в спеках (UC-код + затрагиваемые агрегаты), кросс-чек с `03-data-ownership.md`: для каждого write-UC сервиса S сущность должна иметь `owner = S`.

---

## 5. Бизнес-процессы

`docs/business-processes/BP-NN-<name>.md` — сквозные бизнес-сценарии, охватывающие несколько сервисов. Каждый BP имеет sequence-диаграмму, таблицу шагов, секцию «🔴 Точки отказа» и компенсации.

### 5.1 Обязательно

### R-ARCH-BP-1

Каждый BP имеет orchestrator-сервис ИЛИ явную пометку «choreography» с обоснованием (см. `R-DIST-SAGA-2`, `R-DIST-SAGA-3`). Без этого читателю неясно, кто отвечает за прогресс саги и где искать saga-state.

Detection: парсинг шапки BP-файла на поле `Saga-orchestrator:` или явный заголовок «Choreography».

### R-ARCH-BP-2

Каждый шаг BP, исполняемый сервисом, имеет соответствующий UC в карточке этого сервиса. Шаги-actor-действия типа «Buyer нажимает Купить» или «Cashier сканирует штрихкод» из правила исключены — для них UC у сервиса нет.

Detection: парсинг таблицы «Шаги» BP, для каждого шага с `actor: <service-name>` — проверка наличия UC с тем же кодом/именем в `services/<name>/README.md` и `services/<name>/spec/`.

### R-ARCH-BP-3

Каждая точка отказа (🔴) в BP имеет компенсацию ИЛИ явную пометку «нет компенсации, пользователь видит ошибку» с обоснованием. Нельзя оставить шаг без стратегии на отказ — это пробел в дизайне, который всплывёт в проде.

Detection: парсинг секции «🔴 Точки отказа» BP-файла, для каждой точки — проверка наличия записи в секции «Компенсации» или явной пометки «no-compensation».

### R-ARCH-BP-4

Компенсация — semantic state-change (UPDATE status), не DELETE (см. `R-DIST-COMP-X2`). Если оригинальный шаг был «создан заказ», компенсация — «cancelled order», не `DELETE FROM orders`. Иначе теряется audit и ломаются reference'ы от уже отправленных событий.

Detection: парсинг секции «Компенсации» BP-файла, проверка формулировок на DELETE-семантику.

### R-ARCH-BP-5

Money-шаги в BP имеют idempotency-key — явно в sequence-диаграмме (header `Idempotency-Key`) или в таблице шагов (колонка `idempotency`). Без этого retry → дважды списанные деньги (см. `R-DIST-IDEM-4`).

Detection: для каждого BP-файла с money-шагом (heuristic: упоминание `payment`, `charge`, `refund`, `transfer`, currency) — grep `Idempotency-Key` или `idempotency`.

### R-ARCH-BP-6

Sync-шаги между BC, упомянутые в BP, объявлены в `docs/architecture/06-integration-patterns.md`. Цель — единая интеграционная поверхность: одним документом видно все sync-точки между сервисами.

Detection: парсинг BP-шагов с типом `sync HTTP` (или `gRPC`), извлечение пар (from-service, to-service, endpoint), кросс-чек с таблицей в `06-integration-patterns.md`.

---

## 6. Контракты

Папка `services/<name>/contracts/` содержит OpenAPI (sync) и AsyncAPI (events). Это публичный контракт сервиса.

### 6.1 Обязательно

### R-ARCH-CONTR-1

Каждый `openapi.y*ml` в `services/<name>/contracts/` декларирует `info.version`. Без версии нельзя отслеживать breaking changes и согласовывать миграции consumer'ов.

Detection: `yq '.info.version' services/*/contracts/openapi.y*ml`; пустые/`null` — нарушение.

### R-ARCH-CONTR-2

Каждое событие в AsyncAPI имеет поля `eventId`, `eventType`, `version` (см. `R-KFK-EV-*`). Это минимальный обязательный header для idempotency, routing и версионирования.

Detection: парсинг AsyncAPI каждого события (`components.messages.<X>.payload.properties`), проверка наличия трёх полей.

```yaml
# Корректно
components:
  messages:
    OrderCreated:
      payload:
        type: object
        properties:
          eventId: { type: string, format: uuid }
          eventType: { type: string, const: "OrderCreated.v1" }
          version: { type: integer }
          # ... domain payload
```

### R-ARCH-CONTR-3

Breaking changes между версиями контракта перечислены — changelog в самом контракте (секция `info.description` или отдельный `CHANGELOG.md` рядом) или в `06-integration-patterns.md`. Без changelog consumer не знает, что миграция требуется.

Detection: для каждого сервиса с bumped major-версии (`info.version` поменялась) — проверка наличия changelog-секции.

---

## 7. Синхронизация со спеками

Карточка сервиса `services/<name>/README.md` — краткая навигация, спека `services/<name>/spec/` — содержательная. Они должны быть согласованы.

### 7.1 Обязательно

### R-ARCH-SPEC-1

Каждый агрегат, упомянутый в `services/<name>/README.md` (секция «Домен-агрегаты»), существует как файл в `services/<name>/spec/aggregates/`. Если карточка обещает агрегат, спека должна его описывать.

Detection: парсинг секции «Домен-агрегаты» в карточке + `ls services/<name>/spec/aggregates/`. Каждый агрегат → файл.

### R-ARCH-SPEC-2

Каждый UC, упомянутый в карточке (секция «Use Cases»), существует в спеке — в `<service>-spec.md` или в одном из агрегат-файлов. Карточка не должна обещать функционал, которого нет в спеке.

Detection: парсинг списка UC в карточке (по коду или имени), grep по `services/<name>/spec/`. Не найден — нарушение.

### R-ARCH-SPEC-3

Упомянутые в карточке BP (секция «Участие в бизнес-процессах») существуют как `docs/business-processes/BP-NN-*.md`. Back-reference карточка → BP должен указывать на реальный документ.

Detection: парсинг back-ref'ов из карточки + `ls docs/business-processes/`. Несуществующий BP-NN — нарушение.

---

## 8. Применение

Скилл `ucp-arch-consistency-review` запускается:

- **После крупных design-скиллов**: `ucp-arch-design` (правка корпусной структуры), `ucp-arch-bp-design` (новый BP), `ucp-arch-context-design` (новая связь BC).
- **После `ucp-arch-sync`** с большим diff'ом — когда множество карточек / спек были обновлены автоматическим синком, легко получить рассинхрон.
- **Периодически** — раз в спринт или раз в релиз, как health-check корпуса. Дрейф архитектурных артефактов накапливается медленно, и без регулярного ревью замечается только когда уже больно.
- **Перед мажорным релизом сервиса** — выборочно по группам `R-ARCH-CONTR-*` и `R-ARCH-SPEC-*` для конкретного сервиса.

Findings формируются с цитированием кода правила (`R-ARCH-CTX-1: связь order → catalog не объявлена симметрично в catalog/README.md`) — это даёт читателю быстрый путь к гайду.

---

## 9. Антипаттерны

| Антипаттерн | Правило | Корректно |
|---|---|---|
| Сервис без owner/tier/subdomain | `R-ARCH-REG-1` | заполнить три поля в `_registry.yaml` |
| Orphan папка `services/<name>/` без записи в реестре | `R-ARCH-REG-2` | добавить запись или удалить папку |
| Архивный сервис фигурирует в активном BP | `R-ARCH-REG-3` | обновить BP или снять `archived` |
| Связь BC в одной карточке, в другой — нет | `R-ARCH-CTX-1` | продублировать связь симметрично |
| `shared-kernel` без ADR | `R-ARCH-CTX-2` | написать ADR или переклассифицировать |
| Событие с двумя publisher'ами | `R-ARCH-CTX-3` | один owner + другой sender как consumer-republish |
| Термин с расходящимися определениями в спеках | `R-ARCH-UL-1` | привести к UL или явный omonym |
| Дубль агрегата без пометки omonym | `R-ARCH-UL-2` | omonym в `02-ubiquitous-language.md` |
| Сущность с двумя owner-ами | `R-ARCH-DATA-1` | выбрать одного, остальные — consumer |
| Два сервиса с одним aggregate-root | `R-ARCH-DATA-2` | пересмотреть границы BC |
| Consumer пишет в чужую сущность | `R-ARCH-DATA-3` | команда к owner-сервису |
| BP без orchestrator и без пометки choreography | `R-ARCH-BP-1` | явно объявить тип саги |
| Шаг BP без UC у actor-сервиса | `R-ARCH-BP-2` | добавить UC в спеку или убрать шаг |
| 🔴 точка отказа без компенсации | `R-ARCH-BP-3` | компенсация или явное no-compensation |
| Компенсация через DELETE | `R-ARCH-BP-4` | semantic state-change (cancelled, refunded) |
| Money-шаг без idempotency-key | `R-ARCH-BP-5` | `Idempotency-Key` header или колонка |
| Sync-вызов между BC не в `06-integration-patterns.md` | `R-ARCH-BP-6` | добавить запись в integration-patterns |
| OpenAPI без `info.version` | `R-ARCH-CONTR-1` | проставить semver |
| Событие без `eventId/eventType/version` | `R-ARCH-CONTR-2` | дополнить payload-схему |
| Breaking change без changelog | `R-ARCH-CONTR-3` | секция changelog в контракте |
| Агрегат в карточке без файла в `spec/aggregates/` | `R-ARCH-SPEC-1` | создать файл агрегата |
| UC в карточке без описания в спеке | `R-ARCH-SPEC-2` | добавить UC в спеку |
| BP в карточке без файла `BP-NN-*.md` | `R-ARCH-SPEC-3` | создать BP-файл или убрать ссылку |

Финальная сводка: 23 правила в 7 группах, все MUST. Антипаттерн = нарушение конкретного MUST-правила.
