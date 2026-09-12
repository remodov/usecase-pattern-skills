# Architecture Consistency — реализация

Свод правил **платформенной согласованности** артефактов в корпусе `architecture/` — реестра сервисов, context map, ubiquitous language, владения данными, бизнес-процессов, контрактов, реестра событий и синхронизации карточек сервисов со спеками, а также формы самих индексных документов корпуса. Каждое правило идентифицируется кодом (`arch/registry-entry-is-complete`, `R-ARCH-BP-X1` — где X-нумерация была бы для антипаттернов, но в этом гайде все правила MUST) — скилл `ucp-arch-consistency-review` цитирует эти коды в findings.

Гайд работает на уровне **корпуса**, не на уровне отдельного сервиса. Внутрисервисные правила покрывают другие гайды (`backend/distributed-patterns/references/java/implementation.md`, `backend/kafka/references/java/implementation.md`, `backend/ddd-tactical/references/java/implementation.md`, …). Здесь — про **связи**: симметрию объявлений, single-publisher событий, owner-edits-only, синхронизацию карточка ↔ спека, и т.д. — плюс про **форму** корпусных перечислений (`R-ARCH-DOC-*`): реестр, который нельзя распарсить, не выполняет свою функцию.

Не покрывает: содержание ADR (это процесс), детализацию sequence-диаграмм в BP (это `ucp-arch-bp-design`), внутреннюю кодовую структуру сервисов.

Связанные стандарты:
- `R-DIST-COMP-*` — semantic compensation, не DELETE (используется в `arch/failure-points-have-compensation`).
- `R-DIST-IDEM-*` — idempotency для money (используется в `arch/failure-points-have-compensation`).
- `R-KFK-EV-*` — обязательные поля события (`eventId`, `eventType`, `version`; используется в `arch/contracts-are-versioned`).
- `ADR-0001` — определение tier-ов сервисов (используется в `arch/registry-entry-is-complete`).
- `ADR-0002` — owner-edits-only (используется в `arch/single-owner-per-entity`).

---

## Содержание

1. [Реестр и владение — `R-ARCH-REG-*`](#1-реестр-и-владение)
2. [Context map — `R-ARCH-CTX-*`](#2-context-map)
3. [Ubiquitous Language — `R-ARCH-UL-*`](#3-ubiquitous-language)
4. [Владение данными — `R-ARCH-DATA-*`](#4-владение-данными)
5. [Бизнес-процессы — `R-ARCH-BP-*`](#5-бизнес-процессы)
6. [Контракты — `R-ARCH-CONTR-*`](#6-контракты)
7. [Синхронизация со спеками — `R-ARCH-SPEC-*`](#7-синхронизация-со-спеками)
8. [Форма индексных документов — `R-ARCH-DOC-*`](#8-форма-индексных-документов)
9. [Применение](#9-применение)
10. [Антипаттерны — сводка](#10-антипаттерны)

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

Каждая сущность в `03-data-ownership.md` имеет ровно одного owner-сервис. Два владельца — consistency-конфликт: write от A и B нельзя сериализовать без распределённой транзакции (которая запрещена `distributed/no-two-phase-commit`).

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

Каждый BP имеет orchestrator-сервис ИЛИ явную пометку «choreography» с обоснованием (см. `distributed/orchestration-versus-choreography`, `distributed/orchestration-versus-choreography`). Без этого читателю неясно, кто отвечает за прогресс саги и где искать saga-state.

Detection: парсинг шапки BP-файла на поле `Saga-orchestrator:` или явный заголовок «Choreography».

### R-ARCH-BP-2

Каждый шаг BP, исполняемый сервисом, имеет соответствующий UC в карточке этого сервиса. Шаги-actor-действия типа «Buyer нажимает Купить» или «Cashier сканирует штрихкод» из правила исключены — для них UC у сервиса нет.

Detection: парсинг таблицы «Шаги» BP, для каждого шага с `actor: <service-name>` — проверка наличия UC с тем же кодом/именем в `services/<name>/README.md` и `services/<name>/spec/`.

### R-ARCH-BP-3

Каждая точка отказа (🔴) в BP имеет компенсацию ИЛИ явную пометку «нет компенсации, пользователь видит ошибку» с обоснованием. Нельзя оставить шаг без стратегии на отказ — это пробел в дизайне, который всплывёт в проде.

Detection: парсинг секции «🔴 Точки отказа» BP-файла, для каждой точки — проверка наличия записи в секции «Компенсации» или явной пометки «no-compensation».

### R-ARCH-BP-4

Компенсация — semantic state-change (UPDATE status), не DELETE (см. `distributed/compensation-is-semantic-and-idempotent`). Если оригинальный шаг был «создан заказ», компенсация — «cancelled order», не `DELETE FROM orders`. Иначе теряется audit и ломаются reference'ы от уже отправленных событий.

Detection: парсинг секции «Компенсации» BP-файла, проверка формулировок на DELETE-семантику.

### R-ARCH-BP-5

Money-шаги в BP имеют idempotency-key — явно в sequence-диаграмме (header `Idempotency-Key`) или в таблице шагов (колонка `idempotency`). Без этого retry → дважды списанные деньги (см. `distributed/money-double-protection`).

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

### R-ARCH-CONTR-4

`contracts/events/_index.md` — **обязательный артефакт корпуса**: единый реестр каналов со стабильным заголовком таблицы. Каждый топик/канал, объявленный в `services/*/contracts/asyncapi.y*ml`, присутствует в реестре ровно одной строкой и имеет ровно одного publisher-сервиса.

Зачем реестр, если есть AsyncAPI: AsyncAPI отвечает на вопрос «что внутри сообщения» и живёт по одному файлу на сервис. Вопрос «какие каналы вообще есть в системе и кто по ним говорит» — перечислительный, и ответ на него нельзя собрать ни по прозе системных доков, ни обходом N контрактов вручную. Реестр — единственное место, где этот список существует целиком (обоснование формы — `arch/index-documents-are-tables`).

Фиксированный формат — шесть обязательных колонок, именно в этом порядке и с этими заголовками:

```markdown
# Реестр событий

| Топик/канал | Publisher (сервис) | Consumers | Брокер | Тип сообщения | Контракт (ссылка на asyncapi) |
|---|---|---|---|---|---|
| `order.placed.v1` | order | payment, notification | Kafka | OrderPlaced.v1 | [asyncapi](../../services/order/contracts/asyncapi.yaml) |
| `payment.captured.v1` | payment | order | Kafka | PaymentCaptured.v1 | [asyncapi](../../services/payment/contracts/asyncapi.yaml) |
| `audit.raw.v1` | audit | not-declared | Kafka | AuditRecorded.v1 | [asyncapi](../../services/audit/contracts/asyncapi.yaml) |
```

Заполнение:
- Ячейка, для которой данных нет, заполняется литералом `not-declared` — пустая ячейка и прочерк запрещены. `not-declared` честно говорит «не объявлено», ищется grep'ом и превращается в backlog; пустая ячейка неотличима от «забыли колонку».
- Дополнительные колонки (`Retention`, `Partition key`, `Статус`) допустимы **справа** от шести обязательных — формат расширяем, уже написанные реестры и detection-инструкции при этом не ломаются.
- Один канал — одна строка. Несколько типов сообщений в одном канале перечисляются в колонке «Тип сообщения» через запятую, строка не дублируется.

Detection:

```bash
# каналы из AsyncAPI сервисов (сторона отправителя; в AsyncAPI 3.x — operations[] с action: send)
yq -r '.channels | to_entries[] | select(.value.publish) | .key' services/*/contracts/asyncapi.y*ml | sort -u
# топики из реестра — первая колонка, без шапки и разделителя
awk -F'|' '/^\|/ && $2 !~ /Топик|---/ {gsub(/[ `]/,"",$2); print $2}' contracts/events/_index.md | sort -u
```

Расхождение в любую сторону — нарушение: топик в AsyncAPI без строки в реестре (реестр отстал от контрактов), строка в реестре без топика в AsyncAPI (канал удалён или переименован — orphan). Дубль в первой колонке или два разных значения в колонке «Publisher (сервис)» для одного топика — тоже нарушение.

```markdown
# Корректно
| Топик/канал | Publisher (сервис) | Consumers | Брокер | Тип сообщения | Контракт (ссылка на asyncapi) |
|---|---|---|---|---|---|
| `order.placed.v1` | order | payment, notification | Kafka | OrderPlaced.v1 | [asyncapi](../../services/order/contracts/asyncapi.yaml) |

# Нарушение R-ARCH-CONTR-4: топик есть в services/payment/contracts/asyncapi.yaml, строки в реестре нет

# Нарушение R-ARCH-CONTR-4 (и R-ARCH-CTX-3): два publisher'а на один топик
| `order.placed.v1` | order | payment | Kafka | OrderPlaced.v1 | [asyncapi](../../services/order/contracts/asyncapi.yaml) |
| `order.placed.v1` | order-legacy | payment | Kafka | OrderPlaced.v1 | [asyncapi](../../services/order-legacy/contracts/asyncapi.yaml) |

# Нарушение R-ARCH-CONTR-4: каналы перечислены прозой вместо таблицы (см. R-ARCH-DOC-1)
Сервис order публикует событие о размещении заказа, его слушают payment и notification.
Ещё есть канал отмены заказа, туда пишет тот же order…
```

Границы с соседями: `arch/one-publisher-per-event` смотрит на реестр изнутри (одно событие — один publisher), `arch/one-publisher-per-event` — на полноту реестра относительно AsyncAPI и на его формат. Если файла `_index.md` нет вовсе — это **один** finding `arch/one-publisher-per-event` на корпус, а не N по числу топиков; fix — прогон `/ucp-arch-sync`, он перестраивает реестр из контрактов.

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

## 8. Форма индексных документов

**Индексный документ корпуса** — документ, содержание которого есть перечисление однотипных сущностей: `contracts/events/_index.md` (каналы), `docs/03-data-ownership.md` (сущность → owner), каталог бизнес-процессов (`docs/business-processes/` — BP → orchestrator → участники), таблица sync-интеграций в `docs/06-integration-patterns.md`, сводная таблица сервисов в `docs/00-overview.md`, реестры типов (`_registry.yaml` — YAML-аналог того же перечисления).

Отличать от **повествовательных** документов: ADR (решение + альтернативы + следствия), BP-файл (сценарий + sequence-диаграмма), карточка сервиса в части «Назначение». Там проза уместна; правило ниже на них не распространяется — но перечислительные секции внутри них (таблица шагов BP, «Домен-агрегаты» карточки) под правило попадают.

### 8.1 Обязательно

### R-ARCH-DOC-1

Каждый индексный документ корпуса — **таблица со стабильным заголовком**. Перечисление тех же сущностей прозой или bullet-списком вместо таблицы — нарушение.

Два обоснования:

1. **Машинная читаемость.** Таблица с фиксированными колонками парсится в одну строку (`awk -F'|'`, `yq`, `pandas.read_html`) — правила `R-ARCH-*` детектируются автоматически, а не «на глаз». Проза требует извлечения сущностей NLP-ом и даёт ложные срабатывания.
2. **Устойчивость к чанкованию.** Корпус индексируется для поиска и RAG: документы режутся на фрагменты. Факт, рассыпанный прозой по нескольким абзацам и секциям, при нарезке разъезжается по разным чанкам — и запрос-перечисление («какие топики есть в системе», «какие сервисы публикуют X») собирает неполный ответ, потому что поиск не может склеить фрагменты обратно. Строка таблицы самодостаточна, а шапка и строки остаются рядом: один чанк отвечает на вопрос целиком.

Требования к таблице:

- **Заголовок стабилен.** Колонки не переименовываются и не переставляются между ревизиями — на них завязаны detection-инструкции скиллов и индексация. Новые колонки добавляются **справа** от обязательных.
- **Одна сущность — одна строка**, и строка самодостаточна: по ней понятно, о чём речь, без чтения вводного абзаца и соседних строк (имя сущности, а не «он же», «там же»).
- **Пустых ячеек нет.** Нет данных — литерал `not-declared`.
- **Проза вокруг таблицы допустима и полезна** (что это за реестр, кто его ведёт, как заполнять), но она **дополняет** таблицу, а не заменяет: ни один элемент перечисления не живёт только в прозе.

Правило **аддитивно**: уже написанные документы не переписываются задним числом ради соответствия. Приведение к таблице происходит при первом изменении документа — новая строка от `ucp-arch-sync`, правка от `ucp-arch-design` / `ucp-arch-bp-design`; недостающие на этот момент данные закрываются `not-declared`, а не блокируют правку.

Detection: для каждого индексного документа — `grep -c '^|' <file>`; ноль markdown-строк таблицы → нарушение. Если таблица есть — проверить, что рядом нет абзаца или bullet-списка, перечисляющего те же сущности (эвристика: bullet-строки с именем сервиса / топика / BP-кода, которого нет в первой колонке таблицы) → нарушение (перечисление раздвоено, таблица неполна).

```markdown
# Корректно — каталог бизнес-процессов
| BP | Название | Orchestrator | Участники | Файл |
|---|---|---|---|---|
| BP-01 | Оформление заказа | order | order, payment, catalog | [BP-01-checkout.md](BP-01-checkout.md) |
| BP-02 | Возврат средств | payment | payment, order, notification | [BP-02-refund.md](BP-02-refund.md) |
| BP-03 | Инвентаризация | choreography | not-declared | [BP-03-stocktaking.md](BP-03-stocktaking.md) |

# Нарушение R-ARCH-DOC-1 — то же прозой: сущности не перечислить, при чанковании разъедется
Основной процесс — оформление заказа (BP-01), его оркеструет order-service, участвуют
также payment и catalog. Отдельно стоит возврат средств, там оркестратор — payment…

# Нарушение R-ARCH-DOC-1 — таблица есть, но часть сущностей вынесена в буллеты под ней
| BP | Название | Orchestrator |
|---|---|---|
| BP-01 | Оформление заказа | order |

Кроме того, есть ещё BP-02 (возврат) и BP-03 (инвентаризация), они пока черновые.

# Нарушение R-ARCH-DOC-1 — пустые ячейки вместо not-declared
| BP-03 | Инвентаризация |  |  | [BP-03-stocktaking.md](BP-03-stocktaking.md) |
```

---

## 9. Применение

Скилл `ucp-arch-consistency-review` запускается:

- **После крупных design-скиллов**: `ucp-arch-design` (правка корпусной структуры), `ucp-arch-bp-design` (новый BP), `ucp-arch-context-design` (новая связь BC).
- **После `ucp-arch-sync`** с большим diff'ом — когда множество карточек / спек были обновлены автоматическим синком, легко получить рассинхрон.
- **Периодически** — раз в спринт или раз в релиз, как health-check корпуса. Дрейф архитектурных артефактов накапливается медленно, и без регулярного ревью замечается только когда уже больно.
- **Перед мажорным релизом сервиса** — выборочно по группам `R-ARCH-CONTR-*` и `R-ARCH-SPEC-*` для конкретного сервиса.
- **После правки любого индексного документа** — точечно `arch/index-documents-are-tables` и `arch/one-publisher-per-event` (реестр событий): именно эти два правила ловят дрейф «факт добавили прозой мимо таблицы».

Findings формируются с цитированием кода правила (`R-ARCH-CTX-1: связь order → catalog не объявлена симметрично в catalog/README.md`) — это даёт читателю быстрый путь к гайду.

---

## 10. Антипаттерны

| Антипаттерн | Правило | Корректно |
|---|---|---|
| Сервис без owner/tier/subdomain | `arch/registry-entry-is-complete` | заполнить три поля в `_registry.yaml` |
| Orphan папка `services/<name>/` без записи в реестре | `arch/registry-entry-is-complete` | добавить запись или удалить папку |
| Архивный сервис фигурирует в активном BP | `arch/archived-service-not-in-live-processes` | обновить BP или снять `archived` |
| Связь BC в одной карточке, в другой — нет | `arch/context-links-are-symmetric` | продублировать связь симметрично |
| `shared-kernel` без ADR | `arch/shared-kernel-needs-adr` | написать ADR или переклассифицировать |
| Событие с двумя publisher'ами | `arch/one-publisher-per-event` | один owner + другой sender как consumer-republish |
| Термин с расходящимися определениями в спеках | `arch/ubiquitous-language-is-consistent` | привести к UL или явный omonym |
| Дубль агрегата без пометки omonym | `arch/ubiquitous-language-is-consistent` | omonym в `02-ubiquitous-language.md` |
| Сущность с двумя owner-ами | `arch/single-owner-per-entity` | выбрать одного, остальные — consumer |
| Два сервиса с одним aggregate-root | `arch/single-owner-per-entity` | пересмотреть границы BC |
| Consumer пишет в чужую сущность | `arch/single-owner-per-entity` | команда к owner-сервису |
| BP без orchestrator и без пометки choreography | `arch/process-has-orchestrator-or-note` | явно объявить тип саги |
| Шаг BP без UC у actor-сервиса | `arch/process-step-matches-service-use-case` | добавить UC в спеку или убрать шаг |
| 🔴 точка отказа без компенсации | `arch/failure-points-have-compensation` | компенсация или явное no-compensation |
| Компенсация через DELETE | `arch/failure-points-have-compensation` | semantic state-change (cancelled, refunded) |
| Money-шаг без idempotency-key | `arch/failure-points-have-compensation` | `Idempotency-Key` header или колонка |
| Sync-вызов между BC не в `06-integration-patterns.md` | `arch/sync-steps-are-declared` | добавить запись в integration-patterns |
| OpenAPI без `info.version` | `arch/contracts-are-versioned` | проставить semver |
| Событие без `eventId/eventType/version` | `arch/contracts-are-versioned` | дополнить payload-схему |
| Breaking change без changelog | `arch/breaking-changes-are-listed` | секция changelog в контракте |
| Агрегат в карточке без файла в `spec/aggregates/` | `arch/service-card-matches-spec` | создать файл агрегата |
| UC в карточке без описания в спеке | `arch/service-card-matches-spec` | добавить UC в спеку |
| BP в карточке без файла `BP-NN-*.md` | `arch/service-card-matches-spec` | создать BP-файл или убрать ссылку |
| Нет `contracts/events/_index.md` / топик из AsyncAPI не попал в реестр | `arch/one-publisher-per-event` | перестроить реестр прогоном `/ucp-arch-sync` |
| Строка реестра без соответствующего канала в AsyncAPI | `arch/one-publisher-per-event` | убрать orphan-строку или вернуть канал в контракт |
| Индексный документ перечисляет сущности прозой / буллетами | `arch/index-documents-are-tables` | таблица со стабильным заголовком |
| Часть сущностей в таблице, часть — абзацем под ней | `arch/index-documents-are-tables` | перенести всё в таблицу |
| Пустая ячейка в реестре | `arch/index-documents-are-tables` | литерал `not-declared` |

Финальная сводка: 25 правил в 8 группах, все MUST. Антипаттерн = нарушение конкретного MUST-правила.
