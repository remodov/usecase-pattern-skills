# Obsidian vault bootstrap

Минимальный `.obsidian/` для свежей spec-папки. Скилл `ucp-spec-design`
копирует это содержимое в `docs/spec/.obsidian/` при первом запуске —
тогда папку можно открыть в Obsidian и сразу получить:

- **Properties-панель** с типизированными полями для всех схем карточек
  (`severity`, `retryable`, `criticality`, `payload`, и т.д. — см. `types.json`).
- **Graph View** с предзаданными цветовыми группами:
  `#service` (синий), `#module` (фиолетовый), `#integration` (оранжевый),
  карточки errors / commands / events / aggregates — каждый со своим цветом
  (фильтрация по нативному обсидиановскому `["type":"error"]`-синтаксису,
  без community-плагинов).
- **Backlinks**, **Tag pane**, **Outline**, **Bookmarks** — все нужные core plugins.

## Что включено

- `types.json` — schema всех frontmatter-полей UCP-спеки. Без этого
  Obsidian показывал бы `payload` как простой текст вместо списка.
- `graph.json` — цветовые группы и параметры Graph View.
- `core-plugins.json` — включённые штатные плагины Obsidian
  (Properties / Graph / Backlinks / Tag pane / Outline).
- `community-plugins.json` — пустой список (community-плагины не ставим
  по умолчанию).
- `app.json` — общие настройки (без табов, attachments в `./attachments`).

## Что НЕ включено

- **Community-плагины** (Dataview, Templater и т.п.). Раньше пытались
  поставлять Dataview прямо в бутстрапе — отказались: пинит версию,
  раздувает репо, вшитый бинарник вызывал больше проблем чем решал.
  Хотите Dataview-таблицы в landing-файлах — установите плагин руками
  через Obsidian → Settings → Community plugins → Browse.
- **Темы и кастомизации** — это вкусовщина пользователя.
- **Workspace.json** — состояние открытых вкладок, не должно лежать в репо.

## Использование вручную

Если `ucp-spec-design` уже создал `docs/spec/`, но `.obsidian/` там нет,
скопируйте бутстрап:

```bash
cp -r usecase-pattern-skills/docs/obsidian-vault-bootstrap/.obsidian docs/spec/
```

Затем откройте `docs/spec/` в Obsidian («Open folder as vault»).
