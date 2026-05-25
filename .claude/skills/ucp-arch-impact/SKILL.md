---
name: ucp-arch-impact
description: Pre-flight оценка влияния планируемого изменения в архитектурном корпусе — кого сломает удаление поля, переименование эндпоинта, удаление UC, новая версия события. Классифицирует изменения как breaking/compatible/semantic-break, перечисляет consumer'ов, предлагает миграционную стратегию (expand-contract для API, vN+1 для событий, ADR для UL). Read-only, ничего не меняет. Триггеры: «что сломается если», «можно ли удалить», «кого затронет изменение», «pre-flight», «impact analysis».
allowed-tools: Read Glob Grep Bash(yq*) Bash(jq*) Bash(grep*) Bash(ls*) Bash(cat*) Bash(find*) Bash(git log*)
---

# Impact analysis (read-only)

Ты оцениваешь влияние планируемого изменения на сервисы и процессы платформы. На входе — свободно сформулированное намерение пользователя или diff. На выходе — список затронутых consumer'ов, классификация изменения, миграционная стратегия. Файлы не меняешь.

## Гейт: откуда работать

Skill работает **только** из корня архитектурного репо. Проверка:

```bash
test -f services/_registry.yaml || { echo "не корень architecture/ — нет services/_registry.yaml"; exit 1; }
```

Если файла нет — откажись с сообщением: «Запусти из корня архитектурного репо (там, где `services/_registry.yaml`).» Не догадывайся, не ищи альтернативный путь.

## Гейт: корпус актуален

Проверь свежесть синканого корпуса:

```bash
git log -1 --format=%ar services/
```

Если последний коммит по `services/` старше нескольких недель / месяцев — выведи warning: «Корпус `services/` возможно устарел (последний коммит: <ago>). Рекомендуется запустить `/ucp-arch-sync` перед impact-анализом, иначе оценка может быть неполной.» Продолжай анализ, но пометь это в отчёте.

## Зависимости

- **`services/_registry.yaml`** — манифест (имя, tier, owner, subdomain, archived).
- **`services/<name>/README.md`** — карточка сервиса.
- **`services/<name>/spec/`** — синканые спеки (`<service>-spec.md`, `aggregates/<name>.md`).
- **`services/<name>/contracts/`** — синканые контракты (`openapi.yaml`, `asyncapi.yaml`).
- **`docs/01-context-map.md`**, **`02-ubiquitous-language.md`**, **`03-data-ownership.md`**, **`05-failure-domains.md`**, **`06-integration-patterns.md`** — системные доки.
- **`docs/business-processes/_index.md`** + **`BP-NN-*.md`** — бизнес-процессы.
- **`docs/adr/*.md`** — архитектурные решения.
- **`contracts/events/_index.md`** (опционально) — реестр событий.
- **Cross-references в style guides:**
  - `.claude/docs/distributed-patterns-rules.md` — `R-DIST-EC-*` (eventual consistency, expand-contract).
  - `.claude/docs/kafka-rules.md` — `R-KFK-EV-*` (event versioning, schema evolution).
  - `.claude/docs/rest-api-rules.md` — `R-API-*` (REST contract changes, deprecation).
- **Парные скиллы:**
  - `ucp-arch-query` — read-only «что есть» сейчас.
  - `ucp-arch-consistency-review` — запустить после применения изменения для проверки `R-ARCH-*`.

## Инструкции

### Шаг 1: Распознать изменение

Пользователь описывает планируемое изменение. Возможные форматы:
- Свободный текст: «хочу удалить поле totalAmount из Order OpenAPI»
- Diff: «изменю UC ReserveStock на ReserveInventory»
- Файл-ссылка: «вот новая версия openapi.yaml, что сломается»

Классифицируй:

| Категория | Подтипы |
|---|---|
| **API contract** (REST) | новое поле / удалённое / переименование / изменение типа / новый эндпоинт / удалённый эндпоинт |
| **Event contract** (AsyncAPI) | новое событие / удалённое / новое поле / изменение типа / переименование |
| **Domain change** | новый UC / удалённый UC / переименованный UC / изменение бизнес-правила / изменение статусной модели агрегата |
| **Cross-cutting** | изменение в `02-ubiquitous-language.md` / переход сервиса между tier'ами / смена owner |

### Шаг 2: Найти consumer'ов

Для каждой категории — где искать.

**API contract — изменение `GET /products` в catalog:**

```bash
grep -rn "/products" services/*/README.md          # упоминания в Use Cases / Связи
grep -rln "/products" services/*/spec/              # упоминания в спеках consumer'ов
grep -rln "/products" docs/business-processes/      # sync-вызов в BP-шагах
grep -n "/products" docs/06-integration-patterns.md
```

**Event contract — изменение `OrderPlaced` в order:**

```bash
grep -rn "OrderPlaced" services/*/contracts/asyncapi.y*ml  # publisher (должен быть один — R-ARCH-CTX-3), schemas
grep -rln "OrderPlaced" services/*/spec/                    # listener'ы в спеках
cat contracts/events/_index.md 2>/dev/null                  # официальный реестр
grep -rln "OrderPlaced" docs/business-processes/            # какие BP используют
```

**Domain change — удалить UC `ReserveStock` в catalog:**

```bash
grep -rln "ReserveStock" docs/business-processes/  # какие BP содержат шаг
grep -rln "ReserveStock" services/*/spec/          # упоминания в спеках (connector / saga)
grep -rn "ReserveStock" services/*/README.md       # секция «Use Cases» / «Связи»
```

**Cross-cutting — UL термин:**

```bash
grep -rln "<термин>" services/*/spec/             # частота использования
grep -n "<термин>" docs/02-ubiquitous-language.md  # определение
grep -rln "<термин>" docs/business-processes/
```

### Шаг 3: Классифицировать тип влияния

Для каждого consumer'а:

- **Breaking** — старый код упадёт:
  - Удаление поля, эндпоинта, события, UC.
  - Изменение типа поля (`string → integer`, `optional → required`).
  - Сужение значений (enum: убрали один из существующих).
  - Переименование без alias.
- **Compatible** — старый код продолжит работать:
  - Добавление optional поля.
  - Новый эндпоинт / событие / UC.
  - Расширение enum (новое значение, старые работают).
- **Semantic break** — компилируется и работает, но смысл изменился:
  - Изменение semantics существующего поля (`totalAmount` теперь включает tax вместо excluding).
  - Переход с sync REST на async events для того же flow.
  - Изменение бизнес-правила без сигнатурного изменения (например, «минимальный заказ» поднят с 100 до 1000).

### Шаг 4: Предложить миграционную стратегию

По типу изменения:

**Breaking API contract** → **expand-contract** (`R-DIST-EC-*`, `R-API-*`):
1. Добавить новое поле / эндпоинт параллельно со старым в `v.next`.
2. Дождаться переключения всех consumer'ов.
3. Deprecate старого в OpenAPI (`deprecated: true` + `Sunset`/`Deprecation` headers).
4. Удалить в release N+2.

**Breaking event** → **новая версия события** (`R-KFK-EV-*`):
1. `EventName.v2` параллельно с `EventName.v1` — publisher отправляет оба.
2. Consumer'ы постепенно переключаются на v2.
3. Когда нет slow consumers — deprecation `v1`, удаление через N итераций.

**Удалённый / переименованный UC в BP** → обновление BP-файлов:
- Перечислить какие BP затронуты.
- Для каждого BP — какой шаг должен измениться (номер шага, актор, новое имя UC).

**UL изменение** → cross-context dialogue + ADR:
- Нельзя молча менять термин платформы.
- Предложить ADR в `docs/adr/000N-...`.
- Уведомить владельцев каждого сервиса, где термин используется.

**Cross-cutting tier change** → внутренний rebuild сервиса, не cross-service:
- Пометка «затрагивает только сам сервис, на платформенном уровне нет breaking».

### Шаг 5: Сформировать отчёт

См. формат вывода ниже.

### Шаг 6: Не предлагать применение

Скилл оценивает риски, но изменения **не делает**. После отчёта рекомендовать:
- Дальше: разработчик планирует миграцию и/или открывает ADR.
- После применения: запустить `/ucp-arch-sync` чтобы корпус подхватил изменения.
- Затем: `/ucp-arch-consistency-review` чтобы убедиться, что `R-ARCH-*` выполнены.

## Формат вывода

```
## Impact analysis: <краткое описание изменения>

**Тип изменения:** API contract / Event contract / Domain change / Cross-cutting
**Подтип:** ...
**Классификация:** Breaking / Compatible / Semantic break

### Consumer'ы

| Consumer | Где найдено | Тип влияния | Комментарий |
|---|---|---|---|
| backoffice | services/backoffice/spec/...:42 | Breaking | использует поле в UC DisputeReview |
| notification | services/notification/contracts/asyncapi.yaml:88 | Compatible | слушает событие, поле новое — игнорирует |
| ...

### Миграционная стратегия

1. ...
2. ...

### Затронутые BP

| BP | Шаг | Действие |
|---|---|---|
| BP-01 | step 5 (Order.authorize) | Параметризация под v2 |
| BP-04 | step 3 | Без изменений (sequence не зависит от поля) |

### Рекомендации после применения

- Обнови соответствующие спеки сервисов.
- Запусти `/ucp-arch-sync` для обновления корпуса.
- Запусти `/ucp-arch-consistency-review`.
- Если breaking — открой ADR в `docs/adr/000N-...`.
```

## Read/Write границы

Skill **может**:
- Читать любые файлы корпуса.
- Запускать `yq`, `jq`, `grep`, `find`, `cat`, `ls`, `git log` для навигации и проверки свежести.

Skill **НЕ может**:
- Редактировать ни одного файла (включая README, спеки, контракты).
- Применять предложенное изменение.
- Принимать решений за пользователя — только перечисляет варианты с trade-offs.
- Запускать `scripts/sync.sh` — это `ucp-arch-sync`.
- Делать `git add` / `git commit`.

## Что не входит

- Ответ «что есть сейчас» без оценки изменения — это `ucp-arch-query`.
- Проверка нарушений `R-ARCH-*` (дрейф, ownership-конфликты) — это `ucp-arch-consistency-review`.
- Проектирование нового сервиса / нового BP — это `ucp-arch-design` / `ucp-arch-bp-design`.
- Применение миграции (правки openapi, asyncapi, спек, BP) — делает разработчик вручную или через design-скиллы.
- Суждения «правильно ли спроектировано исходное» — это работа review-скиллов.

$ARGUMENTS
