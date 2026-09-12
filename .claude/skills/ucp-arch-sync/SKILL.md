---
name: ucp-arch-sync
lang: any
track: any
description: Подтянуть спеки и публичные контракты сервисов в architecture/services/<name>/spec и /contracts — scripts/sync.sh, интерпретация JSON diff, обновление зависимых карточек и индексов. Не коммитит — оставляет diff и сообщение.
when_to_use: Триггеры — «синкни», «обнови архитектурный репо», «sync архитектуру». Перед платформенным ревью или периодически.
allowed-tools: Read Write Edit Glob Grep Bash(scripts/sync.sh*) Bash(cat*) Bash(jq*) Bash(yq*) Bash(grep*) Bash(git diff*) Bash(git status*) Bash(git log*) Bash(ls*)
---

# Sync архитектурного репо

Ты запускаешь sync спек и контрактов из сервисов в `architecture/services/<name>/`, интерпретируешь JSON-отчёт по изменениям и обновляешь зависимые артефакты в архитектурном репо (карточки `services/<name>/README.md`, реестр событий `contracts/events/_index.md`, секции системных доков). **Реестр событий перестраивается на каждом прогоне** — он обязательный артефакт корпуса (`arch/one-publisher-per-event`), и расхождения «реестр ↔ AsyncAPI» выносятся в отчёт. Cross-context изменения (UL, ownership) — только предлагаешь в чат, не правишь молча. Коммит не делаешь — даёшь пользователю diff и предлагаемое сообщение.

## Гейт: откуда работать

Skill работает **только** из корня архитектурного репо. Проверка:

```bash
test -f services/_registry.yaml || { echo "не корень architecture/ — нет services/_registry.yaml"; exit 1; }
```

Если файла нет — откажись с сообщением: «Запусти из корня архитектурного репо (там, где `services/_registry.yaml`).» Не догадывайся, не ищи альтернативный путь.

## Зависимости

- **`scripts/sync.sh`** — механика sync (rsync, JSON diff report).
- **`services/_registry.yaml`** — манифест сервисов (источник правды).
- **`services/_registry.local.yaml`** (опционально) — локальные override-пути для итерации без push.
- **`contracts/events/_index.md`** — реестр событий корпуса, обязательный артефакт (`arch/one-publisher-per-event`). Skill его создаёт, если файла нет, и актуализирует на каждом прогоне.
- **`.claude/docs/shared/arch/spec.md`** — формат реестра и правила `arch/one-publisher-per-event` / `arch/index-documents-are-tables` (полный текст с примерами — `shared/arch/references/implementation.md` §6, §8).
- **Парные скиллы:**
  - `ucp-arch-consistency-review` — запускать после большого sync для контроля дрейфа.
  - `ucp-arch-impact` — если diff содержит breaking changes в OpenAPI/AsyncAPI.

## Инструкции

### Шаг 1: Запустить механику sync

```bash
bash scripts/sync.sh > /tmp/arch-sync-output.json
```

Если скрипт упал с missing dependency — сообщи пользователю что нужно установить (`brew install yq` для yq, `brew install jq` для jq), не пытайся обойти.

Если скрипт вернул `exit 1` («no _registry.yaml in cwd») — значит работаем не из архитектурного репо, останови выполнение.

### Шаг 2: Прочитать JSON-отчёт

```bash
cat /tmp/arch-sync-output.json | jq
```

Структура:

```json
{
  "added": ["services/X/spec/foo.md", "services/Y/contracts/asyncapi.yaml"],
  "modified": [...],
  "deleted": [...],
  "renamed": [...]
}
```

Если все массивы пустые — sync ничего не изменил в спеках и контрактах. Шаг 3 пропусти, но **Шаг 4 (реестр событий) выполни всё равно**: реестр мог разъехаться от ручных правок, и это дешёвая проверка. Если и там расхождений нет — отчитайся «корпус актуален, реестр событий сходится» и выйди.

### Шаг 3: Интерпретировать diff и обновить корпус

Для каждой группы изменений примени маппинг.

#### Новый агрегат — добавлен файл `services/<name>/spec/aggregates/<aggregate>.md`

Действие: открой `services/<name>/README.md`, секция «Домен-агрегаты» — добавь строку. Имя агрегата — из заголовка файла `# <name>`. Назначение — из шапки `## Назначение` или первого абзаца.

#### Удалённый агрегат — `services/<name>/spec/aggregates/<x>.md` в `deleted`

Действие: убери строку из секции «Домен-агрегаты» в README. Warning: проверь grep'ом не упоминается ли агрегат в `docs/business-processes/`, если да — флажок в чат.

#### Новый UC в спеке — изменился `<service>-spec.md` или агрегат-файл (новые строки в таблице UC)

Действие: открой README, секция «Use Cases» — добавь bullet. Warning: проверь упоминается ли UC хоть в одном BP-файле (`grep -r "UC-...\|<UC-name>" docs/business-processes/`), если нет — пометка «нужно добавить в BP или явно out-of-flow».

#### Новое событие — добавлен файл в `services/<name>/contracts/asyncapi.yaml` или появились новые definitions

Действие: пометь сервис как затронутый — реестр событий перестраивается целиком на Шаге 4, отдельной ручной вставки строки здесь не нужно. Проверь, что publisher (этот сервис) — owner соответствующего агрегата по `docs/03-data-ownership.md`. Если не owner — флажок в чат (`arch/one-publisher-per-event`).

#### Новый термин в UL спеки — диф в `<service>-spec.md` содержит секцию «Ubiquitous Language» с новой строкой

Действие: **НЕ ВСТАВЛЯЙ** молча в `02-ubiquitous-language.md`. Сформулируй предложение в чат: «В спеке `<service>` появился термин X. Добавить в платформенный UL? Definition: ...» — пользователь сам решает (может быть конфликт с существующим определением).

#### Изменения в OpenAPI

Действие: если изменения только в новых полях/эндпоинтах — пометка «non-breaking, ничего системного обновлять не нужно». Если есть удаления/переименования — рекомендация в чат «запусти `/ucp-arch-impact` для оценки кто сломается».

### Шаг 4: Перестроить реестр событий `contracts/events/_index.md`

Реестр событий — **обязательный артефакт корпуса** (`arch/one-publisher-per-event`), а не опциональный индекс. Выполняй этот шаг на каждом прогоне, даже если в diff'е нет изменений в AsyncAPI: реестр мог разъехаться от ручных правок.

**4.1. Собрать факты из контрактов.**

```bash
ls contracts/events/_index.md 2>/dev/null || echo "реестра нет — будет создан"
# каналы каждого сервиса (AsyncAPI 2.x; в 3.x — operations[] с action: send/receive)
for f in services/*/contracts/asyncapi.y*ml; do echo "== $f"; yq '.channels | keys' "$f"; done
```

Для каждого канала собери шесть фактов: топик/канал, publisher-сервис, consumers, брокер, тип сообщения, путь к asyncapi. Consumers — из subscribe-стороны AsyncAPI других сервисов; если по контрактам потребителей не видно, дополнительно `grep -rl "<топик>" services/*/spec/`.

**4.2. Записать таблицу фиксированного формата.** Заголовок — ровно этот, колонки не переставляй и не переименовывай (на них завязан детект `ucp-arch-consistency-review`); дополнительные колонки, если нужны — только справа от шести обязательных:

```markdown
# Реестр событий

<одна-две строки прозой: что это, что источник правды — AsyncAPI сервисов, что файл перестраивается `/ucp-arch-sync`>

| Топик/канал | Publisher (сервис) | Consumers | Брокер | Тип сообщения | Контракт (ссылка на asyncapi) |
|---|---|---|---|---|---|
| `order.placed.v1` | order | payment, notification | Kafka | OrderPlaced.v1 | [asyncapi](../../services/order/contracts/asyncapi.yaml) |
```

**Пустых ячеек не оставляй** — факт, которого нет в контрактах, закрывается литералом `not-declared` (`arch/index-documents-are-tables`). Это относится и к брокеру, и к consumers, и к типу сообщения. `not-declared` — рабочее состояние, оно не блокирует sync и потом ищется grep'ом.

**4.3. Сохранить ручные данные.** Значения, которых нет в контрактах (комментарии в дополнительных колонках, consumers, известные только из спек), при перестройке **не затирай**: сначала прочитай текущий реестр, потом мержи — контракты выигрывают по шести обязательным колонкам, ручное содержимое остаётся в остальных. Строку, отсутствующую в контрактах, не удаляй молча — помечай как расхождение (см. 4.4).

**4.4. Сверить и вынести расхождения в отчёт.** Расхождения бывают трёх видов:

- **Топик в AsyncAPI, но не было в реестре** → строка добавлена; в отчёт: «+ `<топик>` (publisher `<сервис>`)».
- **Строка в реестре, но топика нет ни в одном AsyncAPI** → строку **не удаляй**, помечай в колонке справа `⚠ orphan` и выноси в отчёт: канал удалён/переименован в контракте, либо реестр описывает то, чего нет. Решает пользователь.
- **Два publisher'а на один топик** → строки обе оставь, в отчёт с кодом `arch/one-publisher-per-event` / `arch/one-publisher-per-event` — это нарушение, чинится в контрактах сервисов, не здесь.

Если реестра не было и он создан с нуля — так и скажи в отчёте («реестр событий создан, N каналов»), это ожидаемое состояние для корпуса, который вёлся без него.

### Шаг 5: Применить безопасные обновления

Применяй автоматически: карточки `services/<name>/README.md` (добавления в таблицы), `contracts/events/_index.md`.

НЕ применяй автоматически: `02-ubiquitous-language.md`, `03-data-ownership.md`, `01-context-map.md` — только предлагай в чат.

### Шаг 6: Сформировать предлагаемое коммит-сообщение

Шаблон:

```
sync: <краткая сводка по сервисам>

- <name>: <что изменилось>
- ...

Cross-context proposals (review needed):
- UL: ...
- Ownership: ...

NOT committing: <причины>
```

### Шаг 7: Показать diff пользователю

```bash
git status --short
git diff --stat
```

Скажи: «Готово. Изменения выше. Предлагаемое сообщение — ниже. Запусти коммит сам когда проверишь.»

**НЕ ВЫПОЛНЯЙ `git commit` или `git add` вообще.** Коммит — ответственность пользователя.

## Формат отчёта в чате

```
## Sync завершён

**Из manifest'а:** 6 сервисов, 0 archived
**Sync статистика:** N added, M modified, K deleted

### Обновлено в архитектурном репо
- services/order/README.md — добавлен Agreement Dispute

### Реестр событий (contracts/events/_index.md)
- Каналов в реестре: N (было M)
- Добавлено: `order.placed.v1` (publisher order), `order.cancelled.v1` (publisher order)
- ⚠ Orphan (строка есть, канала в AsyncAPI нет): `legacy.order.v0` — удалён из контракта или переименован?
- ⚠ not-declared: 3 строки без consumers, 1 без брокера
- ❌ R-ARCH-CTX-3: два publisher'а на `order.placed.v1` — order и order-legacy

### Cross-context предложения (review needed)
- UL: термин "Settlement" в catalog spec, definition отличается от existing — обсудить

### Diff
[git status output]

### Предлагаемое сообщение
[commit message]

**Запусти коммит сам.**
```

## Read/Write границы

Skill **может**:
- Запускать `scripts/sync.sh` (он пишет в `services/<name>/spec` и `/contracts`).
- Редактировать `services/<name>/README.md`.
- Создавать и перестраивать `contracts/events/_index.md` (обязательный артефакт, `arch/one-publisher-per-event`) — но не удалять из него строки: orphan помечается и выносится в отчёт.
- Читать всё остальное.

Skill **НЕ может**:
- Редактировать `02-ubiquitous-language.md`, `03-data-ownership.md`, `01-context-map.md` — только предлагать.
- Делать `git add` или `git commit`.
- Редактировать `_registry.yaml` — это input манифест.

## Что не входит

- Ревью результатов sync на consistency корпуса — `ucp-arch-consistency-review` (`R-ARCH-*`).
- Оценка breaking changes в контрактах — `ucp-arch-impact`.
- Правки спек / контрактов в самих сервисах — это делается в репо сервиса через `ucp-spec-design` / `ucp-api-design`, не здесь.

$ARGUMENTS
