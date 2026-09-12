---
name: ucp-arch-consistency-review
lang: any
track: any
description: Ревью платформенной согласованности корпуса architecture/ (требования arch/*) — реестр сервисов, context map, ubiquitous language, владение данными, бизнес-процессы, контракты, реестр событий, синхронизация со спеками.
when_to_use: После крупного ucp-arch-design / ucp-arch-bp-design / ucp-arch-sync или раз в спринт. Триггеры — «ревью архитектуры», «проверь платформу».
allowed-tools: Read Glob Grep Bash(git log*) Bash(yq*) Bash(ls*) Bash(cat*) Bash(find*) Bash(grep*) Bash(awk*) Bash(sort*) Bash(diff*)
---

# Ревью архитектурной согласованности

Ты ревьюишь корпус архитектурного репо (карточки `services/<name>/`, манифест `_registry.yaml`, системные доки `docs/01..06`, бизнес-процессы `docs/business-processes/`, ADR, контракты в `contracts/` и `services/*/contracts/`) на соответствие требованиям `hexagonal/*`. Главное: ни один сервис не остался без owner, ни одна связь не объявлена односторонне, ни одно событие не имеет двух publisher'ов, каждый BP-шаг имеет реальный UC в сервисе, реестр событий сходится с AsyncAPI, а перечисления в корпусе оформлены таблицами, а не прозой.

## Гейт: откуда работать

Skill работает **только** из корня архитектурного репо. Проверка:

```bash
test -f services/_registry.yaml || { echo "не корень architecture/ — нет services/_registry.yaml"; exit 1; }
```

Если файла нет — откажись с сообщением: «Запусти из корня архитектурного репо (там, где `services/_registry.yaml`).» Не догадывайся, не ищи альтернативный путь.

## Гейт: корпус актуален

```bash
git log -1 --format=%ar services/
```

Если последний коммит в `services/` старше 7 дней — **warning** (не failure): корпус может быть устаревшим, рекомендуй `/ucp-arch-sync` перед ревью. Продолжай прогон.

## Зависимости

- **`.claude/docs/shared/arch/spec.md`** — компактный индекс правил (полный текст с примерами и code-блоками — `shared/arch/references/implementation.md`, читать точечно по нужной группе). 8 подгрупп: `R-ARCH-REG-*` (реестр), `R-ARCH-CTX-*` (context map), `R-ARCH-UL-*` (ubiquitous language), `R-ARCH-DATA-*` (владение данными), `R-ARCH-BP-*` (бизнес-процессы), `R-ARCH-CONTR-*` (контракты и реестр событий), `R-ARCH-SPEC-*` (sync со спеками), `R-ARCH-DOC-*` (форма индексных документов).
- **Парные guides:**
  - `backend/distributed-patterns/spec.md` — `R-DIST-COMP-*` для BP-4 (semantic compensation не DELETE), `R-DIST-IDEM-*` для BP-5 (money-idempotency).
  - `backend/kafka/spec.md` — `R-KFK-EV-*` для CONTR-2 (eventId/eventType/version).
  - ADR `docs/adr/0001-tier-per-service.md` — для REG-1 (поле `tier`).
  - ADR `docs/adr/0002-no-direct-data-edits.md` — для DATA-3 (owner-edits-only).

## Инструкции

1. **Прочти `.claude/docs/shared/arch/spec.md`** — компактный индекс. Цитируй коды (`arch/registry-entry-is-complete`, `arch/failure-points-have-compensation` и т.д.) в findings. Полную версию открывай точечно: нужна только секция, чьё правило сомнительно или нужно обоснование.

2. **Определи scope ревью.**
   - Пользователь указал конкретный сервис (например, `services/order/`) или конкретный BP — фокус на нём, прогон только тех правил, что применимы.
   - Иначе — полный прогон по всем 8 группам (25 правил).
   - При запуске создай TodoWrite-задачи по чек-листу в конце файла, чтобы прогон был трассируемым.

3. **Прогон по подгруппам.**

### `R-ARCH-REG-*` — реестр и владение

- **REG-1.** Каждый сервис в манифесте имеет `owner`, `tier`, `subdomain`:
  ```bash
  yq '.services[] | select(.owner == null or .tier == null or .subdomain == null) | .name' services/_registry.yaml
  ```
  Результат должен быть пустым. Любое имя в выводе → ❌ REG-1.

- **REG-2.** Соответствие 1:1 директорий и записей:
  ```bash
  diff <(ls services/ | grep -v '_registry' | sort) <(yq '.services[].name' services/_registry.yaml | sort)
  ```
  Любой diff → ❌ REG-2 (orphan-папка или orphan-запись).

- **REG-3.** Archived-сервисы не упомянуты в активных BP. Для каждого `archived: true`:
  ```bash
  grep -rl "services/<name>/" docs/business-processes/
  ```
  Любой файл в выводе → ❌ REG-3.

### `R-ARCH-CTX-*` — context map

- **CTX-1.** Симметричность связей. Для каждого сервиса прочитай секцию «Связи» в `services/<name>/README.md`. Для каждой связи A → B (customer-supplier, conformist, anti-corruption-layer) проверь упоминание A в карточке партнёра B. Одностороннее объявление → ❌ CTX-1.

- **CTX-2.** Shared-kernel требует ADR:
  ```bash
  grep -rn "shared-kernel" services/*/README.md
  ```
  Для каждого случая — поищи ссылку на ADR (`docs/adr/`) в той же карточке или в `docs/01-context-map.md`. Без ADR → ❌ CTX-2.

- **CTX-3.** Один publisher на событие. Сверь `contracts/events/_index.md` (или `contracts/events/*.y*ml`) с AsyncAPI каждого сервиса:
  ```bash
  yq '.channels.*.publish.message.name' services/*/contracts/asyncapi.y*ml
  ```
  Если событие декларируется как publish в двух AsyncAPI → ❌ CTX-3.

### `R-ARCH-UL-*` — ubiquitous language

- **UL-1.** Согласованность определений. Для каждого термина из `docs/02-ubiquitous-language.md`:
  ```bash
  grep -rn "<term>" services/*/spec/
  ```
  Сверь определения в спеках с UL-файлом. Расхождение без пометки `omonym` → ❌ UL-1.

- **UL-2.** Дубли агрегатов между сервисами. Парсинг секций «Домен-агрегаты» во всех карточках:
  ```bash
  grep -A 20 "Домен-агрегаты" services/*/README.md
  ```
  Одно имя (case-insensitive) в двух сервисах → проверить пометку omonym в UL. Нет пометки → ❌ UL-2.

### `R-ARCH-DATA-*` — владение данными

- **DATA-1.** Один owner на сущность. Прочти таблицу в `docs/03-data-ownership.md` — каждая запись должна иметь ровно одно значение owner. Дубли → ❌ DATA-1.

- **DATA-2.** Aggregate-root уникален. Парсинг «Домен-агрегаты» во всех карточках — дублирующиеся root'ы между сервисами без omonym-пометки → ❌ DATA-2 (пересекается с UL-2, но фокус здесь на root'е).

- **DATA-3.** Owner-edits-only. Для каждого write-UC в спеках (содержит «создаёт», «обновляет», «удаляет», «помечает») проверь, что сервис-владелец спеки совпадает с owner-сервисом сущности в `03-data-ownership.md`. Несовпадение → ❌ DATA-3 (нарушение ADR-0002).

### `R-ARCH-BP-*` — бизнес-процессы

- **BP-1.** Orchestrator или choreography. В шапке каждого `docs/business-processes/BP-NN-*.md` должно быть «Saga-orchestrator: X» ИЛИ «choreography» с обоснованием. Нет ни того, ни другого → ❌ BP-1.

- **BP-2.** Каждый шаг имеет UC. Парсинг таблицы «Шаги» BP → для каждого шага «<сервис>: <действие>» (исключая actor-шаги типа «Buyer нажимает Купить») проверь, что в `services/<сервис>/README.md` или `services/<сервис>/spec/` существует UC с похожим именем/кодом. Не найден → ❌ BP-2.

- **BP-3.** Точки отказа имеют компенсацию. Парсинг секции «🔴 Точки отказа» → каждая точка имеет либо ссылку на компенсацию, либо явную пометку «нет компенсации, пользователь видит ошибку» с обоснованием. Пусто → ❌ BP-3.

- **BP-4.** Компенсация — semantic state-change. Парсинг секций «Компенсации» в BP:
  ```bash
  grep -n -E "(DELETE|удалить запись|drop)" docs/business-processes/BP-*.md
  ```
  Найдено без обоснования → ❌ BP-4 (см. `distributed/compensation-is-semantic-and-idempotent`).

- **BP-5.** Money-idempotency. В BP-файлах с «деньги» / «оплата» / «refund» / «authorize» / «списание» должны быть упоминания `Idempotency-Key`:
  ```bash
  grep -rlE "(оплат|refund|списан|authorize|деньг)" docs/business-processes/
  ```
  Для каждого такого файла:
  ```bash
  grep -c "Idempotency-Key" <file>
  ```
  Ноль → ❌ BP-5 (см. `R-DIST-IDEM-*` и `auth-patterns/money-commands-need-idempotency-key`).

- **BP-6.** Sync-вызовы в integration-patterns. Каждая REST-стрелка между сервисами в sequence-диаграмме BP должна быть упомянута в `docs/06-integration-patterns.md`. Не упомянута → ❌ BP-6.

### `R-ARCH-CONTR-*` — контракты

- **CONTR-1.** Версия в openapi:
  ```bash
  for f in services/*/contracts/openapi.y*ml; do
    v=$(yq '.info.version' "$f")
    [ "$v" = "null" ] && echo "❌ $f"
  done
  ```

- **CONTR-2.** Event-поля в AsyncAPI. Каждое событие должно иметь `eventId`, `eventType`, `version`:
  ```bash
  yq '.components.messages.*.payload.properties | keys' services/*/contracts/asyncapi.y*ml
  ```
  Отсутствует хотя бы одно — ❌ CONTR-2 (см. `R-KFK-EV-*`).

- **CONTR-3.** Changelog при множественных версиях. Если в `contracts/` есть `openapi-v1.yaml` и `openapi-v2.yaml` (или аналог для AsyncAPI) — должен быть changelog либо в самом файле (`info.description`), либо в `docs/06-integration-patterns.md`. Нет — ❌ CONTR-3.

- **CONTR-4.** Реестр событий полон и однозначен. Реестр `contracts/events/_index.md` — обязательный артефакт корпуса; каждый топик из AsyncAPI сервисов присутствует в нём ровно одной строкой и имеет ровно одного publisher'а.

  Шаг 1 — файл вообще есть:
  ```bash
  test -f contracts/events/_index.md || echo "❌ CONTR-4: реестра событий нет"
  ```
  Файла нет → **один** finding CONTR-4 на корпус (не N по числу топиков), fix — `/ucp-arch-sync`, он перестраивает реестр из контрактов. Дальнейшие проверки CONTR-4 пропусти.

  Шаг 2 — шапка таблицы на месте и в правильном порядке (первые шесть колонок):
  ```bash
  grep -m1 '^| *Топик' contracts/events/_index.md
  ```
  Ожидается `| Топик/канал | Publisher (сервис) | Consumers | Брокер | Тип сообщения | Контракт (ссылка на asyncapi) |`. Переименованная / переставленная / отсутствующая колонка → ❌ CONTR-4 (ломает детект и индексацию, см. `arch/index-documents-are-tables`). Дополнительные колонки **справа** от шести обязательных — норма, не finding.

  Шаг 3 — сверка с контрактами в обе стороны:
  ```bash
  # каналы из AsyncAPI (2.x; в 3.x — operations[] с action: send)
  yq -r '.channels | keys | .[]' services/*/contracts/asyncapi.y*ml 2>/dev/null | sort -u > /tmp/arch-channels-asyncapi.txt
  # топики из реестра — первая колонка
  awk -F'|' '/^\|/ && $2 !~ /Топик|---/ {gsub(/[ `]/,"",$2); print $2}' contracts/events/_index.md | sort -u > /tmp/arch-channels-index.txt
  diff /tmp/arch-channels-asyncapi.txt /tmp/arch-channels-index.txt
  ```
  Строки `<` (топик в AsyncAPI, но не в реестре — реестр отстал) и строки `>` (строка реестра без канала в AsyncAPI — orphan) → ❌ CONTR-4, по одному finding на топик.

  Шаг 4 — единственность publisher'а: дубли в первой колонке или два разных значения во второй для одного топика → ❌ CONTR-4; репортить **одним** finding вместе с `arch/one-publisher-per-event`, не двумя (CTX-3 смотрит на реестр изнутри, CONTR-4 — на его соответствие AsyncAPI).

### `R-ARCH-SPEC-*` — синхронизация со спеками

- **SPEC-1.** Агрегат в карточке = файл в spec. Для каждого агрегата в секции «Домен-агрегаты» карточки:
  ```bash
  ls services/<name>/spec/aggregates/<aggregate>.md
  ```
  Файла нет → ❌ SPEC-1.

- **SPEC-2.** UC в карточке = UC в спеке. Для каждого UC (имя/код) в карточке:
  ```bash
  grep -rl "<UC>" services/<name>/spec/
  ```
  Пусто → ❌ SPEC-2.

- **SPEC-3.** BP-ссылки из карточки существуют. Для каждого BP в секции «Участие в бизнес-процессах» карточки:
  ```bash
  ls docs/business-processes/<BP-file>.md
  ```
  Файла нет → ❌ SPEC-3.

### `R-ARCH-DOC-*` — форма индексных документов

- **DOC-1.** Индексный документ — таблица со стабильным заголовком. Индексные документы корпуса: `contracts/events/_index.md`, `docs/03-data-ownership.md`, `docs/06-integration-patterns.md`, каталог BP в `docs/business-processes/` (`_index.md` или сводная таблица в `docs/00-overview.md`), любые другие `_index.md` реестров и реестры типов.

  Шаг 1 — таблица вообще есть:
  ```bash
  for f in contracts/events/_index.md docs/03-data-ownership.md docs/06-integration-patterns.md docs/00-overview.md; do
    [ -f "$f" ] && echo "$f: $(grep -c '^|' "$f") строк таблицы"
  done
  ```
  Ноль строк таблицы в индексном документе (перечисление ведётся прозой или буллетами) → ⚠️ DOC-1.

  Шаг 2 — перечисление не раздвоено. Если таблица есть, проверь, нет ли рядом абзаца или bullet-списка, перечисляющего те же сущности. Эвристика: собери имена из первой колонки таблицы, затем поищи в тексте вне таблицы упоминания сервисов / топиков / BP-кодов, которых в этой колонке нет:
  ```bash
  grep -nE '^\s*[-*] ' contracts/events/_index.md docs/03-data-ownership.md 2>/dev/null
  ```
  Буллет, называющий сущность, отсутствующую в таблице → ⚠️ DOC-1 (часть перечисления живёт только в прозе — при чанковании индексации она теряется).

  Шаг 3 — пустых ячеек нет:
  ```bash
  grep -nE '\|\s*\|' contracts/events/_index.md docs/03-data-ownership.md 2>/dev/null | grep -v '^.*:.*|---'
  ```
  Пустая ячейка → ⚠️ DOC-1, fix — литерал `not-declared`. Строка-разделитель (`|---|---|`) в счёт не идёт.

  **Правило аддитивно.** Документ, который просто ещё не приводили к табличной форме, — это **⚠ warning с конкретным fix'ом** («перечисление в §N — в таблицу с колонками X/Y/Z»), а не блокер: массового переписывания корпуса ревью не требует. Один finding на документ, не на строку. Исключение — `contracts/events/_index.md`: там формат таблицы обязателен, и нарушение шапки идёт как ❌ по `arch/one-publisher-per-event`.

4. **Финальные напоминания.**
   - Skill **read-only**. Никаких правок файлов, никаких `Edit`/`Write`. При нахождении ошибки — только finding + предложение fix, исправляет пользователь (через `ucp-arch-sync` или вручную через design-скиллы).
   - Для каждого finding: код правила + конкретный файл + строка (если применимо) + конкретное предложение fix.

## Формат вывода

```
## Архитектурное ревью: <YYYY-MM-DD>

Scope: <полный прогон | services/<name> | docs/business-processes/BP-NN>
Корпус: последний коммит в services/ — <N> дней назад

### ✅ Прошли
- R-ARCH-REG-1: все 6 сервисов имеют owner/tier/subdomain
- R-ARCH-REG-2: services/ ↔ _registry.yaml — 1:1
- ...

### ⚠️ Warning
- R-ARCH-CTX-2: связь shared-kernel найдена между order-service и payment-service без ADR. Не блокер, но добавить ADR.
  - Файл: services/order/README.md:42
  - Fix: создать `docs/adr/00NN-shared-kernel-order-payment.md` с обоснованием.

### ❌ Issues
- R-ARCH-DATA-2: агрегат "Refund" заявлен в order-service AND payment-service
  - Файлы: services/order/spec/aggregates/refund.md, services/payment/spec/aggregates/refund.md
  - Fix: либо переименовать один (например, OrderRefund/PaymentRefund), либо в docs/02-ubiquitous-language.md добавить пометку omonym (см. R-ARCH-UL-2).

- R-ARCH-BP-3: точка отказа «оплата не прошла» в BP-02-checkout.md не имеет компенсации
  - Файл: docs/business-processes/BP-02-checkout.md:78
  - Fix: добавить компенсацию (cancel reservation) или явную пометку «нет компенсации, пользователь видит ошибку» с обоснованием.

- R-ARCH-CONTR-4: топик `payment.captured.v1` объявлен в AsyncAPI, но отсутствует в реестре событий
  - Файлы: services/payment/contracts/asyncapi.yaml, contracts/events/_index.md
  - Fix: прогнать `/ucp-arch-sync` — он перестроит реестр из контрактов; неизвестные ячейки закроются `not-declared`.

- R-ARCH-DOC-1 (⚠️): в docs/06-integration-patterns.md sync-вызовы перечислены прозой, таблицы нет
  - Файл: docs/06-integration-patterns.md:12-40
  - Fix: свести в таблицу `| From | To | Endpoint | Протокол | BP |`; пропуски — `not-declared`. Проза остаётся как пояснение к таблице.

### Резюме
- Critical (❌): N
- Warning (⚠️): M
- Прошло (✅): K
- Рекомендации: запустить `/ucp-arch-sync` для авто-fix REG-2 / SPEC-* нарушений; вручную через `/ucp-arch-design` для CTX-* и BP-*.
```

**Серьёзность:**
- **Critical (❌):** REG-1, REG-2, CTX-1, CTX-3, DATA-1, DATA-2, DATA-3, BP-1, BP-2, BP-4, BP-5, CONTR-1, CONTR-2, CONTR-4 — структурные нарушения, ломают consistency корпуса.
- **Warning (⚠️):** REG-3, CTX-2, UL-1, UL-2, BP-3, BP-6, CONTR-3, SPEC-1, SPEC-2, SPEC-3, DOC-1 — дрейф между источниками, требует приведения в порядок но не блокирует работу.
- Исключение по CONTR-4: **отсутствие самого файла** `contracts/events/_index.md` в корпусе, который никогда его не вёл, — один ❌ с fix'ом «прогони `/ucp-arch-sync`», а не N findings по числу топиков.

## Что не входит

- Review саги/idempotency внутри сервиса — `ucp-distributed-review` (`R-DIST-*`).
- Review событий на уровне реализации (outbox, dedup, partition key) — `ucp-kafka-review` (`R-KFK-*`).
- Review спеки конкретного агрегата на качество дизайна — `ucp-spec-review`.
- Review OpenAPI-контракта на REST-стиль — `ucp-api-review`.

## Чек-лист правил (для TodoWrite при запуске)

- [ ] R-ARCH-REG-1: owner/tier/subdomain в каждой записи манифеста
- [ ] R-ARCH-REG-2: соответствие services/ ↔ _registry.yaml
- [ ] R-ARCH-REG-3: archived-сервисы не в активных BP
- [ ] R-ARCH-CTX-1: симметричность связей между карточками
- [ ] R-ARCH-CTX-2: shared-kernel ↔ ADR
- [ ] R-ARCH-CTX-3: один publisher на событие
- [ ] R-ARCH-UL-1: согласованность определений терминов
- [ ] R-ARCH-UL-2: дубли агрегатов помечены как omonym
- [ ] R-ARCH-DATA-1: один owner на сущность
- [ ] R-ARCH-DATA-2: aggregate-root уникален между сервисами
- [ ] R-ARCH-DATA-3: owner-edits-only (ADR-0002)
- [ ] R-ARCH-BP-1: orchestrator или choreography с обоснованием
- [ ] R-ARCH-BP-2: каждый шаг BP имеет UC в сервисе
- [ ] R-ARCH-BP-3: точки отказа имеют компенсацию или пометку
- [ ] R-ARCH-BP-4: компенсация — semantic state-change, не DELETE
- [ ] R-ARCH-BP-5: money-шаги имеют Idempotency-Key
- [ ] R-ARCH-BP-6: sync-вызовы в 06-integration-patterns.md
- [ ] R-ARCH-CONTR-1: info.version в каждом openapi
- [ ] R-ARCH-CONTR-2: eventId/eventType/version в AsyncAPI
- [ ] R-ARCH-CONTR-3: changelog при множественных версиях
- [ ] R-ARCH-CONTR-4: реестр событий есть, полон относительно AsyncAPI, один publisher на топик
- [ ] R-ARCH-SPEC-1: агрегат в карточке = файл в spec/aggregates/
- [ ] R-ARCH-SPEC-2: UC в карточке = UC в спеке
- [ ] R-ARCH-SPEC-3: BP в карточке = файл в docs/business-processes/
- [ ] R-ARCH-DOC-1: индексные документы — таблицы со стабильным заголовком, без пустых ячеек

$ARGUMENTS
