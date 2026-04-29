<!-- BEGIN ucp-skills (managed by usecase-pattern-skills/install.sh) -->
## Use Case Pattern skills

Проект использует методологию Use Case Pattern. Скиллы `ucp-*` и
style-guides установлены через `usecase-pattern-skills/install.sh`.

### Спецификация

Если в проекте есть `docs/spec/` — это источник правды по сервису.
Точка входа — landing-файл с frontmatter `type: service`, обычно
`docs/spec/00-<service>/<service>.md`.

Wikilinks вида `[[Name]]` (например `[[CreateProduct]]`,
`[[PRODUCT_NOT_FOUND]]`, `[[06-<service>-rules#BR-008]]`) резолвятся
поиском по `docs/spec/`:

```
find docs/spec -name "Name.md"
```

Per-item карточки имеют типизированный frontmatter (`type: command` /
`event` / `error` / `query` / `aggregate` / `integration`) — это
машиночитаемая часть спеки, ей можно доверять как контракту.

### Кодогенерация и ревью — через скиллы

- `/ucp-spec-design` — написать спеку по бизнес-описанию.
- `/ucp-pattern-design` — UseCase + handlers по карточкам команд/query.
- `/ucp-api-design` — OpenAPI по карточкам интеграций и команд.
- `/ucp-auth-design` — Spring Security по ролям и интеграциям.
- `/ucp-bootstrap-design` — Liquibase + jOOQ + Spring профили.
- `/ucp-ddd-tactical-design` — агрегаты, VO, доменные события (Tier C).
- `/ucp-test-design` — интеграционные тесты по `15-*-acceptance.md`.
- `/ucp-*-review` — ревью соответствующих артефактов.

Style-guides — в `.claude/docs/` (Java, REST, DDD, auth, test, bootstrap,
usecase-pattern, usecase-spec-template).

### Bootstrap на чистой машине

Если `.claude/skills/` пустой или в нём broken-симлинки — скиллы не
установлены. Выполните:

```bash
git clone https://github.com/remodov/usecase-pattern-skills \
  ~/IdeaProjects/usecase-pattern-skills
~/IdeaProjects/usecase-pattern-skills/install.sh .
```

После этого `.claude/skills/` и `.claude/docs/` будут симлинками на
upstream — обновления методологии прилетят автоматически на следующем
`git pull` в репо скиллов.

### Что в этом блоке управляется автоматически

Всё между маркерами `BEGIN ucp-skills` и `END ucp-skills` управляется
`install.sh` и перезаписывается при каждом запуске. Если хочется
дописать проект-специфичные инструкции для Claude — пишите **снаружи**
этих маркеров (выше или ниже), они сохранятся.
<!-- END ucp-skills -->
