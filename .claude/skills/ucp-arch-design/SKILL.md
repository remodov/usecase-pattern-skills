---
name: ucp-arch-design
description: Спроектировать новый сервис на платформенном уровне — карточка services/<name>/README.md, запись в _registry.yaml, обновление 01-context-map.md (новый BC + связи), 03-data-ownership.md (новые сущности). НЕ создаёт репо сервиса, НЕ пишет per-service спеку (для этого ucp-spec-design в репо). Проверяет конфликты ownership и UL. Парный к ucp-arch-consistency-review. Триггеры: «новый сервис на платформе», «выделяем BC», «новый домен платформенного уровня», «добавить сервис в архитектуру». Disambiguation: фраза «новый сервис» в директории сервиса запускает /ucp-new-service (per-service цепочка), из architecture/ — этот скилл.
allowed-tools: Read Write Edit Glob Grep Bash(yq*) Bash(jq*) Bash(grep*) Bash(ls*) Bash(cat*) Bash(find*)
---

# Дизайн нового сервиса (платформенный уровень)

Ты проектируешь новый сервис **на уровне платформы**: какой Bounded Context, кто owner данных, какие связи с существующими сервисами, в каких бизнес-процессах участвует. Per-service спеку, код, OpenAPI — НЕ ты (это `ucp-spec-design`, `ucp-bootstrap-design` и далее в репо самого сервиса).

**Disambiguation:** если ты работаешь из директории конкретного сервиса (есть `<service>/docs/spec/`), но не из `architecture/` — запускай `/ucp-new-service` (per-service цепочка). Этот скилл — про **платформенный уровень до** per-service work.

## Гейт: откуда работать

Skill работает **только** из корня архитектурного репо. Проверка:

```bash
test -f services/_registry.yaml && test -f docs/01-context-map.md && test -f docs/03-data-ownership.md || { echo "не корень architecture/ — нет services/_registry.yaml или docs/01-context-map.md или docs/03-data-ownership.md"; exit 1; }
```

Если файлов нет — откажись с сообщением: «Этот скилл работает из корня архитектурного репо. Для per-service создания запусти `/ucp-new-service` из репо сервиса.» Не догадывайся, не ищи альтернативный путь.

## Зависимости

- **`services/_registry.yaml`** — манифест сервисов (новая запись добавляется).
- **Все `services/<name>/README.md`** — для проверки конфликтов имён агрегатов и шаблона формата карточки.
- **`docs/00-overview.md`** — общая карта (опционально обновляется).
- **`docs/01-context-map.md`** — context map (обновляется новой связью).
- **`docs/03-data-ownership.md`** — ownership matrix (новые сущности).
- **ADR:**
  - `docs/adr/0001-tier-per-service.md` — что такое tier 1/2/3.
  - `docs/adr/0002-no-direct-data-edits.md` — owner-edits-only.
- **Стиль-гайды:**
  - `.claude/docs/arch-rules.md` — правила `R-ARCH-CTX-*`, `R-ARCH-UL-*`, `R-ARCH-DATA-*`.
- **Парные скиллы:**
  - `ucp-arch-consistency-review` — запускать после для проверки `R-ARCH-*`.
  - `ucp-arch-bp-design` — если сервис вводит новые BP.
  - `ucp-spec-design` — в репо сервиса, следующий шаг для per-service работы.
  - `ucp-new-service` — полная per-service цепочка после создания карточки.

## Инструкции

### Шаг 1: Прочитать корпус

- `docs/00-overview.md`, `docs/01-context-map.md`, `docs/03-data-ownership.md` — текущая карта.
- `services/_registry.yaml` — список существующих сервисов.
- Все `services/*/README.md` — для контекста чужих агрегатов и связей.

### Шаг 2: Диалог с пользователем

Задавай по одному вопросу:

1. **Имя сервиса** — короткое, kebab-case, единственное число (`catalog`, `order`, `payment`, не `catalogs`).
2. **Субдомен** — Core / Supporting / Generic + обоснование:
   - **Core** — конкурентное преимущество, ядро бизнеса (для marketplace: Order, Payment, Catalog как «качество выдачи»).
   - **Supporting** — поддерживающий (Backoffice, Customer-self-service).
   - **Generic** — общая инфраструктура, может быть SaaS (Notification, Audit).
3. **Tier** — 1/2/3 по ADR-0001:
   - **Tier 1 (Слоёный)** — CRUD, минимум бизнес-логики; Controller → Service → Repository.
   - **Tier 2 (UseCase Pattern)** — есть use cases, UCP-pattern, но без DDD.
   - **Tier 3 (DDD + Hexagonal)** — rich domain, агрегаты, hexagonal архитектура.
4. **Owner-team** — команда-владелец.
5. **Какие данные владеет** — список сущностей. Сверить с `docs/03-data-ownership.md` — не должно пересекаться с уже заявленными у других сервисов (`R-ARCH-DATA-1`).
6. **Связи с существующими сервисами** — для каждой связи:
   - Партнёр-сервис.
   - Тип DDD: customer-supplier / conformist / open-host-service (OHS) / published-language (PL) / shared-kernel.
   - Канал: sync REST / async events / both.
   - Если shared-kernel — требуется ADR (`R-ARCH-CTX-2`).
7. **Участие в существующих BP** — какие из BP-01..BP-NN затрагивают новый сервис; в какой роли (orchestrator / participant / publisher / consumer).
8. **Новые BP, которые этот сервис вводит** — список (детали — потом через `ucp-arch-bp-design`).

Прежде чем переходить дальше — подтверди понимание у пользователя.

### Шаг 3: Проверка конфликтов

- **`R-ARCH-DATA-1`**: сущности из Шага 2.5 — проверить `grep`'ом по `docs/03-data-ownership.md`. Если уже владеет кто-то — ❌, обсудить с пользователем.
- **`R-ARCH-DATA-2`**: имена агрегатов — `grep` по секциям «Домен-агрегаты» во всех существующих карточках. Если коллизия — либо переименовать, либо в `docs/02-ubiquitous-language.md` пометить как omonym.
- **`R-ARCH-UL-2`**: новые термины из спеки сервиса (понадобятся позже) — пока пометка для `ucp-spec-design`.
- **`R-ARCH-CTX-2`**: shared-kernel — требует ADR. Если пользователь выбрал — спросить почему, и оформить рекомендацию открыть `docs/adr/0006-...md`.

Если есть конфликты — остановиться, обсудить с пользователем перед продолжением.

### Шаг 4: Сгенерировать карточку `services/<name>/README.md`

По шаблону существующих карточек (см. `services/order/README.md`):

```markdown
# <Name> Service

| | |
|---|---|
| **Tier** | <tier> (<описание>) |
| **Субдомен** | **<subdomain>** |
| **Владелец** | <team> |
| **Статус** | 🔴 не начат |
| **Репо** | <placeholder локальный путь> |
| **Спека** | _(будет после ucp-spec-design)_ |

## Назначение

<1-3 предложения>

## Домен-агрегаты

| Агрегат | Назначение |
|---|---|
| <Aggregate1> | ... |

## Use Cases

_(детали — после `ucp-spec-design`)_

Ключевые направления:
- ...

## Связи

| Сосед | Тип | Канал |
|---|---|---|
| <partner> | <ddd type> | <sync/async> |

## Технологии

_(детали — после `ucp-bootstrap-design`)_

Целевой стек: <короткий комментарий на основе tier>:
- Tier 1 → Spring Boot, JPA, простой Controller layer
- Tier 2 → Spring Boot, jOOQ, UseCase Pattern
- Tier 3 → Multi-module Hexagonal, DDD, Kafka outbox

## Участие в бизнес-процессах

| BP | Роль |
|---|---|
| ... | ... |

## Скиллы для имплементации

(список UCP-скиллов в порядке использования по tier — см. `services/order/README.md` как пример)
```

### Шаг 5: Обновить `services/_registry.yaml`

Добавить запись **в конец списка** (не пересортировывай существующие):

```yaml
  - name: <name>
    tier: <N>
    owner: <team>
    subdomain: <subdomain>
    git: git@github.com:org/<name>.git
    paths:
      spec: docs/spec/
      contracts: openapi/
```

### Шаг 6: Обновить `docs/01-context-map.md`

Добавить:
- Новый BC в общую диаграмму (или таблицу) контекстов.
- Каждую связь в формате существующих записей.

Если в файле есть `mermaid`-диаграмма — обнови (добавь новый узел и стрелки).

### Шаг 7: Обновить `docs/03-data-ownership.md`

Добавить каждую сущность из Шага 2.5 в таблицу ownership с новым сервисом как owner.

### Шаг 8: Опционально обновить `docs/00-overview.md`

Если есть таблица сервисов — добавить строку.

### Шаг 9: Финал

Покажи пользователю список созданных/обновлённых файлов. Рекомендации:

- **Дальше — per-service work:** переключись в директорию репо сервиса (или создай его), запусти:
  - `/ucp-spec-design` — Use Case спецификация.
  - `/ucp-new-service` — полная цепочка (bootstrap → spec → pattern → tests).
- **После имплементации:** `/ucp-arch-sync` подхватит спеку и контракты.
- **Затем:** `/ucp-arch-consistency-review` проверит `R-ARCH-*` нарушения.
- Если сервис вводит новые BP — `/ucp-arch-bp-design`.

**Коммит не делаешь.** Покажи diff и предложенное сообщение:

```
feat(arch): add <name> service to platform

Tier: <N> (<описание>)
Owner: <team>
Subdomain: <subdomain>
Связи: <список>
Новые сущности (ownership): <список>
Участие в BP: <список>
```

### Шаг 10: Disambiguation reminder

Если в процессе диалога пользователь говорит «давай сразу создам сервис» / «генерим код» — напомни, что этот скилл **только платформенный уровень**, дальше нужны per-service скиллы:
- `/ucp-new-service` — оркестрация всей цепочки в репо сервиса.
- или отдельно `/ucp-spec-design`, `/ucp-bootstrap-design`, etc.

## Что НЕ делает

- НЕ создаёт репо сервиса.
- НЕ пишет per-service спеку (это `ucp-spec-design` в репо сервиса).
- НЕ пишет код, OpenAPI, миграции.
- НЕ редактирует BP-файлы (это `ucp-arch-bp-design`).
- НЕ делает `git commit` — даёт diff пользователю.

$ARGUMENTS
