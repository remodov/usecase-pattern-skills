# Obsidian vault bootstrap

Минимальный `.obsidian/` для свежей spec-папки. Скилл `ucp-spec-design`
копирует это содержимое в `docs/spec/.obsidian/` при первом запуске —
тогда папку можно открыть в Obsidian и сразу получить:

- **Properties-панель** с типизированными полями для всех схем карточек
  (`severity`, `retryable`, `criticality`, `payload`, и т.д. — см. `types.json`).
- **Graph View** с предзаданными цветовыми группами:
  `#service` (синий), `#module` (фиолетовый), `#integration` (оранжевый),
  карточки errors / commands / events / aggregates — каждый со своим цветом.
- **Backlinks**, **Tag pane**, **Outline**, **Bookmarks** — все нужные core plugins.

## Что включено

- `community-plugins.json` — список community-плагинов, которые вокруг volт
  должен предложить установить (только Dataview сейчас).
- `core-plugins.json` — включённые штатные плагины Obsidian.
- `types.json` — schema всех frontmatter-полей UCP-спеки. Без этого
  Obsidian показывал бы `payload` как простой текст вместо списка.
- `graph.json` — цветовые группы и параметры Graph View.
- `app.json` — общие настройки (без табов, attachments в `./attachments`).

## Что НЕ включено

- **Бинарники плагинов** (`.obsidian/plugins/dataview/`) — не коммитим, чтобы
  не пинить версии и не раздувать репозиторий. Obsidian при первом открытии
  покажет тост «Install dataview», нажимаете — установит автоматически.
- **Темы и кастомизации** — это вкусовщина пользователя.
- **Workspace.json** — состояние открытых вкладок, не должно лежать в репо.

## Использование вручную

Если `ucp-spec-design` уже создал `docs/spec/`, но `.obsidian/` там нет,
скопируйте бутстрап:

```bash
cp -r usecase-pattern-skills/docs/obsidian-vault-bootstrap/.obsidian docs/spec/
```

Затем откройте `docs/spec/` в Obsidian («Open folder as vault»).
