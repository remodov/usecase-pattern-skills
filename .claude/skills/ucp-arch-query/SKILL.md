---
name: ucp-arch-query
lang: any
track: any
description: Read-only навигация по архитектурному корпусу architecture/ (коды R-ARCH-*) — кто публикует событие X, какие сервисы трогают Y, через какие BP проходит Z, сервисы по tier, context-map. Ничего не меняет в файлах.
when_to_use: Триггеры — «кто публикует», «какие сервисы», «через какие BP», «найди в архитектуре». Только из корня architecture/.
allowed-tools: Read Glob Grep Bash(yq*) Bash(jq*) Bash(grep*) Bash(ls*) Bash(cat*) Bash(find*)
---

# Архитектурная навигация (read-only)

Ты отвечаешь на структурные вопросы по корпусу архитектурного репо (карточки `services/<name>/`, манифест, системные доки, BP-файлы, контракты). Ничего не пишешь — только читаешь и отвечаешь.

## Гейт: откуда работать

Skill работает **только** из корня архитектурного репо. Проверка:

```bash
test -f services/_registry.yaml || { echo "не корень architecture/ — нет services/_registry.yaml"; exit 1; }
```

Если файла нет — откажись с сообщением: «Запусти из корня архитектурного репо (там, где `services/_registry.yaml`).» Не догадывайся, не ищи альтернативный путь.

## Зависимости

- **`services/_registry.yaml`** — манифест (имя, tier, owner, subdomain, archived).
- **`services/<name>/README.md`** — карточка сервиса (Назначение, Домен-агрегаты, Use Cases, Связи, Технологии, Участие в бизнес-процессах).
- **`services/<name>/spec/`** — синканые спеки (после `ucp-arch-sync`), включая `<service>-spec.md` и `aggregates/<name>.md`.
- **`services/<name>/contracts/`** — синканые контракты (`openapi.yaml`, `asyncapi.yaml`).
- **`docs/01-context-map.md`**, **`02-ubiquitous-language.md`**, **`03-data-ownership.md`**, **`05-failure-domains.md`**, **`06-integration-patterns.md`** — системные доки.
- **`docs/business-processes/_index.md`** + **`BP-NN-*.md`** — бизнес-процессы.
- **`docs/adr/0001..0005-*.md`** — архитектурные решения.
- **`contracts/events/_index.md`** (опционально) — реестр событий, если ведётся.
- **Парные скиллы:**
  - `ucp-arch-impact` — для вопросов «что будет если поменять/удалить».
  - `ucp-arch-consistency-review` — для проверки нарушений `R-ARCH-*`.
  - `ucp-arch-design` / `ucp-arch-bp-design` — для проектирования нового.

## Инструкции

### Шаг 1: Классифицировать вопрос

Категории:

1. **Событие** — «кто публикует X», «кто слушает Y» → искать в `services/*/contracts/asyncapi.y*ml` и `contracts/events/_index.md` (если есть), плюс упоминания listener'ов в спеках.
2. **Эндпоинт** — «кто owner GET /products», «кто вызывает /orders» → `services/*/contracts/openapi.y*ml` + упоминания в спеках consumer'ов.
3. **Агрегат** — «где живёт Order», «какие UC оперируют Refund» → `services/*/spec/aggregates/` + секции «Домен-агрегаты» в README + `03-data-ownership.md`.
4. **Сервис** — «расскажи про catalog», «связи payment'а» → `services/<name>/README.md` + секции BP в `docs/business-processes/` где упомянут.
5. **Бизнес-процесс** — «как происходит покупка», «BP-04» → `docs/business-processes/BP-NN-*.md`.
6. **Фильтр-атрибут** — «сервисы tier=3», «сервисы команды X», «BP с saga-orchestrator», «архивированные сервисы» → парсинг `_registry.yaml` через `yq`, BP-файлов.
7. **Системный документ** — «context map», «ubiquitous language», «ownership», «failure domains», «integration patterns» → читай соответствующий `docs/0N-*.md`.
8. **ADR** — «какие решения по N», «есть ADR про X» → `docs/adr/*.md`.

### Шаг 2: Поиск по соответствующим locations

Для каждой категории — конкретные команды.

**Событие `OrderPlaced`:**

```bash
grep -rn "OrderPlaced" services/*/contracts/asyncapi*.y*ml    # publisher (в schemas/channels)
grep -rln "OrderPlaced" services/*/spec/                       # consumer'ы (упоминания listener'ов)
cat contracts/events/_index.md 2>/dev/null                     # официальный реестр, если есть
```

**Сервис `catalog`:**

```bash
cat services/catalog/README.md
grep -rln "catalog" docs/business-processes/                   # где участвует
grep -n "catalog" docs/03-data-ownership.md                    # что владеет
```

**Tier=3:**

```bash
yq '.services[] | select(.tier == 3) | .name' services/_registry.yaml
```

**По owner-команде:**

```bash
yq '.services[] | select(.owner == "team-payments") | .name' services/_registry.yaml
```

**Архивированные:**

```bash
yq '.services[] | select(.archived == true) | .name' services/_registry.yaml
```

**Агрегат `Refund`:**

```bash
find services/*/spec/aggregates -iname "*efund*"
grep -rln "Refund" services/*/README.md
grep -n "Refund" docs/02-ubiquitous-language.md                # omonym-чек
grep -n "Refund" docs/03-data-ownership.md                     # кто owner
```

**Бизнес-процесс:**

```bash
ls docs/business-processes/BP-*.md
cat docs/business-processes/BP-04-*.md
```

**ADR по теме:**

```bash
grep -rln "<тема>" docs/adr/
```

### Шаг 3: Ответить структурированно

Формат ответа:

- Прямой ответ на вопрос (списком или таблицей).
- Ссылки на конкретные файлы корпуса (с line numbers, если нашёл `grep -n`).
- Cross-references на смежные артефакты (BP, ADR, ownership), если уместно.
- Если ничего не нашёл — честно: «не задекларировано в `architecture/`, возможно стоит запустить `/ucp-arch-sync` или это вне корпуса».

### Шаг 4: Распознать вопрос про эволюцию

Триггеры на переключение: «что будет если», «можно ли удалить», «как изменить», «кого сломает», «безопасно ли поменять» → **НЕ** отвечать самостоятельно, рекомендовать `/ucp-arch-impact` с тем же вопросом. Это разная природа задачи: query = «что есть», impact = «что сломается».

### Шаг 5: Распознать вопрос про новый дизайн

Триггеры: «как мне добавить сервис», «как создать BP», «спроектируй» → рекомендовать `/ucp-arch-design` (новый сервис) или `/ucp-arch-bp-design` (новый процесс).

## Формат вывода

Прямой ответ + источники + опциональные cross-references.

Пример («кто публикует `OrderPlaced`»):

> **Publisher:** order (`services/order/contracts/asyncapi.yaml:42`)
> **Consumers:**
> - notification — `services/notification/spec/notification-spec.md:88` («подписан на order-events»)
> - backoffice — `services/backoffice/README.md:55` (упоминает в Use Cases)
>
> См. также: `BP-01-purchase.md` шаг 7 (OrderPlaced публикуется), `BP-04` шаг 5.

Пример («сервисы tier=3»):

> **Tier 3 (5 сервисов):** order, payment, catalog, inventory, billing.
> Источник: `services/_registry.yaml`.
> Карточки: `services/<name>/README.md` для каждого.

## Read/Write границы

Skill **может**:
- Читать любые файлы корпуса.
- Запускать `yq`, `jq`, `grep`, `find`, `cat`, `ls` для навигации.

Skill **НЕ может**:
- Редактировать ни одного файла (включая README карточек).
- Запускать `scripts/sync.sh` — это `ucp-arch-sync`.
- Делать `git add` / `git commit`.

## Что не входит

- Оценка «что сломается, если поменять X» — это `ucp-arch-impact`.
- Проверка нарушений `R-ARCH-*` (дрейф, ownership-конфликты) — это `ucp-arch-consistency-review`.
- Проектирование нового сервиса / нового BP — это `ucp-arch-design` / `ucp-arch-bp-design`.
- Ответы за пределами корпуса `architecture/` — если факта нет в корпусе, скажи об этом честно, не выдумывай.
- Суждения «правильно ли спроектировано» — это работа review-скиллов.

$ARGUMENTS
