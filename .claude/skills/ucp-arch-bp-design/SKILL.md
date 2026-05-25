---
name: ucp-arch-bp-design
description: Спроектировать новый бизнес-процесс (BP-NN) — cross-service сценарий с orchestrator/choreography, sequence-диаграммой, точками отказа и компенсациями. Создаёт файл docs/business-processes/BP-NN-<slug>.md, обновляет _index.md и секцию «Участие в бизнес-процессах» в карточках services/<name>/README.md. Применяется при добавлении нового процесса. Парный к ucp-arch-consistency-review (запускать после для проверки R-ARCH-BP-*). Триггеры: «новый процесс», «BP-NN», «cross-service сценарий», «опиши процесс X», «нужна saga для Y».
allowed-tools: Read Write Edit Glob Grep Bash(yq*) Bash(jq*) Bash(grep*) Bash(ls*) Bash(cat*) Bash(find*)
---

# Дизайн нового бизнес-процесса

Ты проектируешь cross-service бизнес-процесс по шаблону существующих BP-01..BP-07. Создаёшь файл `docs/business-processes/BP-NN-<slug>.md`, обновляешь индекс и back-references в карточках сервисов-участников. Технический код saga-orchestrator'а — НЕ твоя работа (это `ucp-distributed-design` в репо сервиса).

## Гейт: откуда работать

Skill работает **только** из корня архитектурного репо. Проверка:

```bash
test -f services/_registry.yaml && test -f docs/business-processes/_index.md || { echo "не корень architecture/ — нет services/_registry.yaml или docs/business-processes/_index.md"; exit 1; }
```

Если файлов нет — откажись с сообщением: «Запусти из корня архитектурного репо (там, где `services/_registry.yaml` и `docs/business-processes/_index.md`).» Не догадывайся, не ищи альтернативный путь.

## Зависимости

- **Шаблон формата** — один из существующих `docs/business-processes/BP-*.md` (читай `BP-01-purchase.md` для structure reference).
- **`docs/business-processes/_index.md`** — карта (новый BP добавляется строкой).
- **`services/*/README.md`** — карточки сервисов (для проверки доступных UC, обновления back-ref'ов).
- **`docs/01-context-map.md`** — связи между BC.
- **Стиль-гайды:**
  - `.claude/docs/arch-rules.md` — правила `R-ARCH-BP-*`.
  - `.claude/docs/distributed-patterns-rules.md` — `R-DIST-SAGA-*` (orchestration vs choreography), `R-DIST-COMP-*` (compensation), `R-DIST-IDEM-*` (idempotency для money-шагов).
- **Парные скиллы:**
  - `ucp-arch-consistency-review` — запускать после для проверки `R-ARCH-BP-*`.
  - `ucp-arch-impact` — если меняются существующие UC.
  - `ucp-distributed-design` — в репо сервиса для имплементации saga-orchestrator'а.

## Инструкции

### Шаг 1: Прочитать корпус

Загрузи в контекст:
- `docs/business-processes/_index.md` — карта существующих BP.
- Все `docs/business-processes/BP-*.md` — для понимания общего стиля.
- `services/*/README.md` — для списка доступных сервисов и их UC.
- `docs/01-context-map.md` — типы связей между BC.

### Шаг 2: Диалог с пользователем

Задавай по одному вопросу:

1. **Триггер процесса** — кто и при каком событии запускает (актор + действие): «Buyer нажимает Купить», «Seller отгружает товар», «Cron 03:00».
2. **Цель** — что должно быть истинным в конце процесса (без техники): «заказ создан, средства списаны, оба уведомлены».
3. **Участники-сервисы** — выбрать из существующих в `_registry.yaml`. Если нужен новый сервис → останови, рекомендуй `/ucp-arch-design` сначала.
4. **Orchestration vs choreography** — по `R-DIST-SAGA-*`: orchestration рекомендуется для complex (4+ шагов) и при branching; choreography для simple (2-3 шага). Обоснование обязательно.
5. **Идемпотентность money-шагов** — если есть платежи/refund'ы — `Idempotency-Key` обязателен (`R-DIST-IDEM-4`).
6. **Точки отказа** — для каждого шага что может пойти не так и как реагировать.
7. **Компенсации** — для каждой точки отказа: rollback, или явная пометка «нет компенсации, пользователь видит ошибку» с обоснованием.

Прежде чем переходить дальше — подтверди понимание у пользователя.

### Шаг 3: Спроектировать sequence

Сгенерируй mermaid `sequenceDiagram` по аналогии с BP-01:
- participants — short alias'ы (`B` — Buyer, `O` — Order, ...).
- sync-вызовы стрелкой `->>`.
- ответы `-->>`.
- асинхронные события через broker `K` (Kafka) — `->>K`, `K-->>X`.

Если **orchestration** — один сервис-orchestrator принимает все решения и вызывает остальных.
Если **choreography** — каждый сервис реагирует на событие предыдущего без центральной координации.

### Шаг 4: Точки отказа + компенсации

Таблица «🔴 Точки отказа»: где может упасть → что сделать.

Правила компенсаций (`R-ARCH-BP-4` / `R-DIST-COMP-*`):
- Семантическое state-change, **НЕ** `DELETE`.
- Идемпотентны — повторный вызов compensation возвращает тот же результат.
- Audit trail — компенсация фиксируется в БД.
- Если нет компенсации (например, «пользователь видит ошибку, ничего не нужно откатывать») — явная пометка с обоснованием.

### Шаг 5: Mapping шагов на UC сервисов

Для каждого шага BP, исполняемого сервисом (актор-действия как «Buyer нажимает» исключаются — `R-ARCH-BP-2`):
- Прочитай `services/<участник>/README.md` секцию «Use Cases».
- Найди UC, соответствующий шагу.
- Если UC найден — заполни (имя + ссылка на спеку).
- Если UC отсутствует — пометь «нужен новый UC `<name>` в сервисе `<svc>`, рекомендую `ucp-spec-design` в репо сервиса».

### Шаг 6: Сгенерировать BP-файл

Создай `docs/business-processes/BP-NN-<slug>.md` по структуре BP-01:

```markdown
# BP-NN: <название>

**Триггер:** <актор + действие>
**Saga-orchestrator:** <сервис> (или явно «Choreography: <обоснование>»)
**Сервисы:** <список через запятую>
**Цель:** <что истинно в конце>

### Sequence

```mermaid
sequenceDiagram
    autonumber
    ...
```

### Шаги

| # | Сервис | Действие | На отказ |
|---|---|---|---|
| ... |

### 🔴 Точки отказа и компенсации

| Где упало | Что делаем |
|---|---|
| ... |

### Идемпотентность

(только для money-шагов)
- `Idempotency-Key`: <как формируется>

### Eventual consistency

(если применимо)
- ...

---

**Назад:** [Индекс бизнес-процессов](_index.md)
```

### Шаг 7: Обновить `_index.md`

Добавь строку в карту процессов `_index.md` — следующий номер `BP-(существующих+1)`.

### Шаг 8: Обновить back-references в карточках сервисов

Для каждого участника-сервиса открой `services/<name>/README.md`, секцию «Участие в бизнес-процессах», добавь строку:

```
| [BP-NN: <название>](../../docs/business-processes/BP-NN-<slug>.md) | <orchestrator / participant / publisher / consumer> |
```

### Шаг 9: Финал

После генерации:
- Покажи пользователю список созданных/обновлённых файлов.
- Рекомендуй `/ucp-arch-consistency-review` для проверки `R-ARCH-BP-*`.
- Если в Шаге 5 были новые UC — список «новые UC требуют создания в репо сервисов через `ucp-spec-design`».
- Если изменяются существующие UC — рекомендуй `/ucp-arch-impact` для оценки breaking changes.
- **Коммит не делаешь** — оставляешь diff пользователю с предлагаемым сообщением:

  ```
  feat(arch): add BP-NN <название>

  Участники: <список>
  Тип: orchestration / choreography
  Связанные UC (новые): <список>
  ```

## Что НЕ делает

- НЕ пишет saga-orchestrator код (это `ucp-distributed-design` в репо сервиса).
- НЕ правит OpenAPI/AsyncAPI контракты (per-service работа).
- НЕ создаёт новые сервисы (это `ucp-arch-design`).
- НЕ делает `git commit` — даёт diff пользователю.
- НЕ изобретает участников вне `_registry.yaml`.

$ARGUMENTS
