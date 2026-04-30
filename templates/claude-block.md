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

Любая работа над UCP-артефактом **обязана** идти через соответствующий
`/ucp-*` скилл, а не писаться от руки. Это инвариант — без него код
дрейфует от методологии и review-скиллы будут ругаться.

| Тип работы | Скилл |
|---|---|
| Написать спеку по бизнес-описанию | `/ucp-spec-design` |
| UseCase + Handler + Controller + маппер | `/ucp-pattern-design` |
| OpenAPI + DTO + контроллер из карточки команды | `/ucp-api-design` |
| Spring Security + OAuth2 + ABAC + audit | `/ucp-auth-design` |
| Spring Boot bootstrap, Liquibase, jOOQ, профили | `/ucp-bootstrap-design` |
| Aggregate + VO + Domain Event + Repository (Tier C) | `/ucp-ddd-tactical-design` |
| Интеграционные / unit тесты по `15-*-acceptance.md` | `/ucp-test-design` |
| Ревью UseCase / Handler / Controller | `/ucp-pattern-review` |
| Ревью REST-контракта | `/ucp-api-review` |
| Ревью DDD-кода | `/ucp-ddd-tactical-review` |
| Ревью Java-стиля (то, что не ловит checkstyle) | `/ucp-java-style-review` |
| Ревью авторизации | `/ucp-auth-review` |

Style-guides — в `.claude/docs/` (Java, REST, DDD, auth, test, bootstrap,
usecase-pattern, usecase-spec-template).

### Интеграция с плагином superpowers

Если задача планируется через `superpowers:writing-plans` или исполняется
через `superpowers:executing-plans` — **план обязан называть конкретные
`/ucp-*` скиллы как шаги**, а не описывать их прозой («написать UseCase»,
«добавить ендпоинт»). Используйте таблицу маппинга выше.

Конкретно при планировании:

- Шаги плана формулируются как «вызвать `/ucp-pattern-design` для команды
  CreateProduct», а не «реализовать CreateProduct».
- Шаги ревью — отдельной парой к шагу design: «после `/ucp-pattern-design`
  → `/ucp-pattern-review` на изменённых файлах».
- Шаги тестирования — через `/ucp-test-design`, а не от руки.

При исполнении плана (`superpowers:executing-plans`): если текущий шаг
ссылается на ucp-* скилл, исполнитель **обязан** его вызвать, не
переписывать инструкции скилла словами.

Без этого правила superpowers строит размытые планы, обходящие
ucp-* — и review-скиллы потом ловят дрейф от методологии.

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
