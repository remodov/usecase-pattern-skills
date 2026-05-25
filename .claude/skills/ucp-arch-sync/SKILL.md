---
name: ucp-arch-sync
description: Подтянуть спеки и публичные контракты сервисов в architecture/services/<name>/spec и /contracts. Запускает scripts/sync.sh (механика rsync), интерпретирует JSON diff и обновляет зависимые карточки + индексы в архитектурном репо. Не коммитит — оставляет diff + предлагаемое сообщение пользователю. Применяется ручным вызовом перед ревью платформы или периодически. Триггеры: «синкни», «обнови архитектурный репо», «pull specs», «sync архитектуру».
allowed-tools: Read Edit Glob Grep Bash(scripts/sync.sh*) Bash(cat*) Bash(jq*) Bash(git diff*) Bash(git status*) Bash(git log*) Bash(ls*)
---

# Sync архитектурного репо

Ты запускаешь sync спек и контрактов из сервисов в `architecture/services/<name>/`, интерпретируешь JSON-отчёт по изменениям и обновляешь зависимые артефакты в архитектурном репо (карточки `services/<name>/README.md`, индексы `contracts/events/_index.md`, секции системных доков). Cross-context изменения (UL, ownership) — только предлагаешь в чат, не правишь молча. Коммит не делаешь — даёшь пользователю diff и предлагаемое сообщение.

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

Если все массивы пустые — sync ничего не изменил, отчитайся «корпус актуален» и выйди.

### Шаг 3: Интерпретировать diff и обновить корпус

Для каждой группы изменений примени маппинг.

#### Новый агрегат — добавлен файл `services/<name>/spec/aggregates/<aggregate>.md`

Действие: открой `services/<name>/README.md`, секция «Домен-агрегаты» — добавь строку. Имя агрегата — из заголовка файла `# <name>`. Назначение — из шапки `## Назначение` или первого абзаца.

#### Удалённый агрегат — `services/<name>/spec/aggregates/<x>.md` в `deleted`

Действие: убери строку из секции «Домен-агрегаты» в README. Warning: проверь grep'ом не упоминается ли агрегат в `docs/business-processes/`, если да — флажок в чат.

#### Новый UC в спеке — изменился `<service>-spec.md` или агрегат-файл (новые строки в таблице UC)

Действие: открой README, секция «Use Cases» — добавь bullet. Warning: проверь упоминается ли UC хоть в одном BP-файле (`grep -r "UC-...\|<UC-name>" docs/business-processes/`), если нет — пометка «нужно добавить в BP или явно out-of-flow».

#### Новое событие — добавлен файл в `services/<name>/contracts/asyncapi.yaml` или появились новые definitions

Действие: добавь запись в `architecture/contracts/events/_index.md` (если такого индекса ещё нет — создай). Проверь что publisher (этот сервис) — owner соответствующего агрегата по `docs/03-data-ownership.md`. Если не owner — флажок в чат (R-ARCH-CTX-3).

#### Новый термин в UL спеки — диф в `<service>-spec.md` содержит секцию «Ubiquitous Language» с новой строкой

Действие: **НЕ ВСТАВЛЯЙ** молча в `02-ubiquitous-language.md`. Сформулируй предложение в чат: «В спеке `<service>` появился термин X. Добавить в платформенный UL? Definition: ...» — пользователь сам решает (может быть конфликт с существующим определением).

#### Изменения в OpenAPI

Действие: если изменения только в новых полях/эндпоинтах — пометка «non-breaking, ничего системного обновлять не нужно». Если есть удаления/переименования — рекомендация в чат «запусти `/ucp-arch-impact` для оценки кто сломается».

### Шаг 4: Применить безопасные обновления

Применяй автоматически: карточки `services/<name>/README.md` (добавления в таблицы), `contracts/events/_index.md`.

НЕ применяй автоматически: `02-ubiquitous-language.md`, `03-data-ownership.md`, `01-context-map.md` — только предлагай в чат.

### Шаг 5: Сформировать предлагаемое коммит-сообщение

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

### Шаг 6: Показать diff пользователю

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
- contracts/events/_index.md — +OrderPlaced

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
- Редактировать `services/<name>/README.md`, `contracts/events/_index.md`.
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
