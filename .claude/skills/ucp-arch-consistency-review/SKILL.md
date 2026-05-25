---
name: ucp-arch-consistency-review
description: Ревью платформенной согласованности корпуса architecture/ — реестр сервисов, context map, ubiquitous language, владение данными, бизнес-процессы, контракты, синхронизация со спеками. Опирается на коды R-ARCH-*. Применяется после крупного ucp-arch-design / ucp-arch-bp-design / ucp-arch-sync с большим diff'ом или периодически (раз в спринт) для контроля дрейфа. Триггеры: «ревью архитектуры», «проверь платформу», «арх consistency».
allowed-tools: Read Glob Grep Bash(git log*) Bash(yq*) Bash(ls*) Bash(cat*) Bash(find*)
---

# Ревью архитектурной согласованности

Ты ревьюишь корпус архитектурного репо (карточки `services/<name>/`, манифест `_registry.yaml`, системные доки `docs/01..06`, бизнес-процессы `docs/business-processes/`, ADR, контракты в `contracts/` и `services/*/contracts/`) на соответствие Architecture Style Guide. Главное: ни один сервис не остался без owner, ни одна связь не объявлена односторонне, ни одно событие не имеет двух publisher'ов, каждый BP-шаг имеет реальный UC в сервисе.

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

- **`.claude/docs/arch-rules.md`** — компактный индекс правил (полный текст с примерами и code-блоками — `arch-style-guide.md`, читать точечно по нужной группе). 7 подгрупп: `R-ARCH-REG-*` (реестр), `R-ARCH-CTX-*` (context map), `R-ARCH-UL-*` (ubiquitous language), `R-ARCH-DATA-*` (владение данными), `R-ARCH-BP-*` (бизнес-процессы), `R-ARCH-CONTR-*` (контракты), `R-ARCH-SPEC-*` (sync со спеками).
- **Парные guides:**
  - `distributed-patterns-rules.md` — `R-DIST-COMP-*` для BP-4 (semantic compensation не DELETE), `R-DIST-IDEM-*` для BP-5 (money-idempotency).
  - `kafka-rules.md` — `R-KFK-EV-*` для CONTR-2 (eventId/eventType/version).
  - ADR `docs/adr/0001-tier-per-service.md` — для REG-1 (поле `tier`).
  - ADR `docs/adr/0002-no-direct-data-edits.md` — для DATA-3 (owner-edits-only).

## Инструкции

1. **Прочти `.claude/docs/arch-rules.md`** — компактный индекс. Цитируй коды (`R-ARCH-REG-2`, `R-ARCH-BP-3` и т.д.) в findings. Полную версию открывай точечно: нужна только секция, чьё правило сомнительно или нужно обоснование.

2. **Определи scope ревью.**
   - Пользователь указал конкретный сервис (например, `services/order/`) или конкретный BP — фокус на нём, прогон только тех правил, что применимы.
   - Иначе — полный прогон по всем 7 группам (23 правила).
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
  Найдено без обоснования → ❌ BP-4 (см. `R-DIST-COMP-X2`).

- **BP-5.** Money-idempotency. В BP-файлах с «деньги» / «оплата» / «refund» / «authorize» / «списание» должны быть упоминания `Idempotency-Key`:
  ```bash
  grep -rlE "(оплат|refund|списан|authorize|деньг)" docs/business-processes/
  ```
  Для каждого такого файла:
  ```bash
  grep -c "Idempotency-Key" <file>
  ```
  Ноль → ❌ BP-5 (см. `R-DIST-IDEM-*` и `AUTH-19`).

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

### Резюме
- Critical (❌): N
- Warning (⚠️): M
- Прошло (✅): K
- Рекомендации: запустить `/ucp-arch-sync` для авто-fix REG-2 / SPEC-* нарушений; вручную через `/ucp-arch-design` для CTX-* и BP-*.
```

**Серьёзность:**
- **Critical (❌):** REG-1, REG-2, CTX-1, CTX-3, DATA-1, DATA-2, DATA-3, BP-1, BP-2, BP-4, BP-5, CONTR-1, CONTR-2 — структурные нарушения, ломают consistency корпуса.
- **Warning (⚠️):** REG-3, CTX-2, UL-1, UL-2, BP-3, BP-6, CONTR-3, SPEC-1, SPEC-2, SPEC-3 — дрейф между источниками, требует приведения в порядок но не блокирует работу.

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
- [ ] R-ARCH-SPEC-1: агрегат в карточке = файл в spec/aggregates/
- [ ] R-ARCH-SPEC-2: UC в карточке = UC в спеке
- [ ] R-ARCH-SPEC-3: BP в карточке = файл в docs/business-processes/

$ARGUMENTS
