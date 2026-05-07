---
name: ucp-spec-design
description: Написать Use Case спецификацию для нового или существующего сервиса из бизнес-описания, по командному универсальному шаблону спеки (Tier A / B / C). Применяется при старте нового сервиса, онбординге существующего модуля или формализации того, что команда делала неформально.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*) Skill(superpowers:*) Bash(mcp__plugin_context7_context7__*)
---

# Use Case спецификация — проектирование

Ты пишешь Use Case спецификацию для сервиса. На выходе — **дерево разбитых markdown-файлов** под `docs/spec/`, по одному файлу на раздел. Файлы структурированы по универсальному шаблону на 16 разделов, глубина выбирается **Tier**-ом (A / B / C).

## Зависимости

Этот скилл предполагает наличие в окружении:

- **Плагин `superpowers`** — для общих рабочих практик планирования и работы с TodoWrite. Если плагина нет, скилл всё равно отработает, но без вспомогательных хелперов.
- **MCP-сервер `context7`** (`mcp__plugin_context7_context7__*`) — для подтягивания актуальной документации по библиотекам, упоминаемым в спеке (Spring Boot, jOOQ и т.п.). Если сервер не подключён, документационные ссылки в спеке оставляются без проверки актуальности.

Если зависимости отсутствуют — скилл сообщает об этом в начале ответа, не падает молча.

## Инструкции

1. **Прочитай шаблон** из `.claude/docs/usecase-spec-template.md` в корне проекта. Он содержит структуру 16 разделов, правила Tier и примеры того, что должно быть в каждом разделе. Считай шаблон обязательным — не выдумывай свои названия и порядок разделов.

2. **Определи Tier** для сервиса (шаблон §«Уровни спеки»):
   - **Tier A** — существующий слоёный сервис, Controller → Service → Repository, без библиотеки `usecase-pattern`.
   - **Tier B** — сервис использует `usecase-pattern` (UseCase + Handler ± CQRS-маркеры); UCP-уровни 1–2.
   - **Tier C** — полный DDD / Hexagonal: агрегаты, доменные события, ports/adapters; UCP-уровни 3–4.

   Осмотри проект на признаки (Java-импорты `ru.mosmetro.usecase.*`, наличие `core/` + `adapter/`, `Aggregate*`, `Entity<ID>`). Если по-прежнему непонятно — **спроси у пользователя**, какой Tier он хочет, прежде чем писать.

3. **Определи вход.** Написание спеки идёт **от бизнес-описания**, не от кода. Пользователь передаст его одним из:
   - markdown-файл в репо (часто `case.md`, `business.md` или похоже);
   - вставка в промпт;
   - ссылка на внешний документ — в этом случае попроси пользователя вставить релевантный текст.

   Если вход слишком тонкий, чтобы заполнить даже Tier A (нет глоссария, акторов, операций), **остановись и спроси**, что недостаёт. Не выдумывай бизнес-факты.

4. **Сгенерируй спеку как Obsidian-vault-совместимое дерево папок** под `docs/spec/`. Это инвариант — на выходе всегда дерево папок и файлов с frontmatter, готовое к копированию в `architecture/20-systems/<system>/services/<service>/` обсидиановского vault'а.

   Раскладка — **каждая секция всегда папка** с одноимённым landing-файлом внутри. Это инвариант: даже если секция содержит только нарратив, она всё равно лежит в папке. Так структура единообразна и в Obsidian wikilink `[[NN-<svc>-<section>]]` стабильно резолвится.

   ```
   docs/spec/
     00-<service>/
       <service>.md                                 — service landing (без префикса в имени файла, чтобы [[<service>]] резолвился)
     01-<service>-context/
       01-<service>-context.md                      — Bounded Context (нарратив)
     02-<service>-language/
       02-<service>-language.md                     — Ubiquitous Language (таблица)
     03-<service>-model/
       03-<service>-model.md                        — landing (ER + Dataview-индекс агрегатов)
       <Aggregate>.md                               — карточка на агрегат (Tier B/C)
     04-<service>-lifecycle/
       04-<service>-lifecycle.md                    — Жизненный цикл (нарратив)
     05-<service>-roles/
       05-<service>-roles.md                        — Роли и права (матрица)
     06-<service>-rules/
       06-<service>-rules.md                        — Бизнес-правила (BR-XXX, нумерованный список)
     07-<service>-commands/
       07-<service>-commands.md                     — landing (Dataview-индекс команд)
       <Command>.md                                 — карточка на команду
     08-<service>-events/                           — Tier B+, если события публикуются
       08-<service>-events.md
       <Event>.md
     09-<service>-queries/                          — Tier B+ Level 2, если есть Read Model
     09-<service>-queries.md
       <Query>.md
     10-<service>-use-cases/
       10-<service>-use-cases.md                    — Use Cases (нарратив, Given/When/Then)
     11-<service>-ui/
       11-<service>-ui.md                           — UI (если есть)
     12-<service>-sagas/
       12-<service>-sagas.md                        — Saga (Tier C+)
     13-<service>-errors/
       13-<service>-errors.md                       — landing (Dataview-индекс ошибок)
       <ERROR_CODE>.md                              — карточка на ошибку
     14-<service>-integrations/
       14-<service>-integrations.md                 — landing (Dataview-индекс рёбер)
       <service>-{from|to}-<other>.md               — карточка на ребро
     15-<service>-acceptance/
       15-<service>-acceptance.md                   — Критерии приёмки (нарратив)
     16-<service>-nfr/
       16-<service>-nfr.md                          — НФТ
     17-<service>-stack/
       17-<service>-stack.md                        — Стек технологий
   ```

   **Папки с per-item карточками** (landing + N файлов внутри): §03 (агрегаты, Tier B+), §07 (команды), §08 (события, Tier B+), §09 (запросы, Tier B+ Level 2), §13 (ошибки), §14 (интеграции).

   **Папки только с landing-файлом** (нарратив или короткая таблица): §01, §02, §04, §05, §06, §10, §11, §12, §15, §16, §17.

   **Service landing** (`00-<service>/<service>.md`) — особый случай: имя файла без префикса `00-`, чтобы wikilink `[[<service>]]` резолвился прямо на landing. Frontmatter: `type: service` (или `type: module`), `owner`, `status`, `criticality`, `since`, `repo`, теги `tech/*`.

   **Frontmatter — обязателен** на следующих файлах (схемы — в `.claude/docs/usecase-spec-template.md`, раздел «Per-item cards»):
   - Service landing (`00-<svc>/<svc>.md`): `type: service|module` + owner / status / criticality / tech-tags.
   - Section landings (`NN-<svc>-<section>.md`): `type: context-section`, `context: <svc>`, `parent: "[[<svc>]]"`, `section: <section>`.
   - Per-item карточки — по своим схемам:
     - `<ERROR_CODE>.md` → `type: error` + `code`, `http`, `severity`, `retryable`, `raised-by[]`.
     - `<Command>.md` → `type: command` + `command`, `actor`, `intent`, `idempotent`, `side-effects[]`, `br[]`, `errors[]`, `returns`.
     - `<Event>.md` → `type: event` + `event`, `aggregate`, `payload-version`, `partition-key`, `retention`, `consumers[]`.
     - `<Aggregate>.md` → `type: aggregate` + `aggregate`, `root`, `states[]`, `emits[]`, `invariants[]`.
     - `<Query>.md` → `type: query` + `query`, `actor`, `returns`, `read-model`.
     - `<edge>.md` → `type: integration` + `integration-type`, `source`, `target`, `direction`, `protocol`, `sync`, `description`, `auth`, `payload[]`, `status`, `idempotency`, `sla`, `ddd-pattern[]`.

   **Консолидированный `<service>.md` не создаётся.** Если потребителю (бизнес-ревью, ingestion в другую AI-сессию) нужен один файл — собирается ad-hoc через `cat`-конкатенацию и не коммитится.

   **Landing раздела с per-item папкой** содержит H1-заголовок + 1–2 строки общего описания. Список карточек получается из листинга папки (любой файловый менеджер / IDE / `ls` справляются), специальных индексов в landing'е не нужно. Пример:

   ```markdown
   # 13. Каталог ошибок

   Каждый код ошибки — отдельный файл-карточка в этой же папке.
   ```

   Если пользователь установит Dataview-плагин в Obsidian вручную — landing можно дополнить запросом, но базовый шаблон без него.

   Имя сервиса (`<service>`) определяется автоматически из аргументов промпта или из существующих маркеров проекта (build.gradle artifactId, pom.xml, README); если не понятно — спросить у пользователя.

   Разделы, неприменимые на текущем Tier-е, **создаются как короткие landing-файлы с одной строкой пояснения** (`Не применимо на Tier A` / `Сервис не публикует доменных событий`) — landing-файл присутствует всегда, даже если внутри секции нет per-item-карточек.

   **Бутстрап Obsidian-vault.** Если в `docs/spec/` ещё нет `.obsidian/`, скопируй туда содержимое бутстрапа:

   ```bash
   cp -R .claude/docs/obsidian-vault-bootstrap/.obsidian docs/spec/.obsidian
   ```

   Бутстрап лежит в `.claude/docs/obsidian-vault-bootstrap/.obsidian/` (симлинк создаёт `install.sh`). Внутри:
   - `types.json` — schema всех frontmatter-полей карточек, чтобы Properties-панель показывала правильные виджеты (checkbox для `retryable`, multitext для `payload` и т.д.).
   - `core-plugins.json` — Properties / Graph / Backlinks / Tag pane включены.
   - `graph.json` — цветовые группы Graph View по типам узлов через нативный обсидиановский синтаксис `["type":"error"]` (errors красные, commands зелёные, events фиолетовые и т.д.) — без community-плагинов.
   - `community-plugins.json` — пустой массив. Community-плагины (Dataview, Templater) не ставим по умолчанию: пользователь добавит сам, если понадобится.

   Если `.obsidian/` уже есть — **не перезаписывай**, пользователь мог поправить под себя. Только сообщи в Output, что бутстрап доступен по пути выше.

5. **Заполни все 16 разделов** в порядке из шаблона:
   1. Bounded Context (Tier A: «модуль / компонент»; Tier B+: полноценный BC).
   2. Ubiquitous Language — таблица глоссария.
   3. Domain Model — ER для A; +UseCase-модели для B; +агрегаты / VO / события для C. **При выборе типов колонок — следуй `pg-types-style-guide.md` (правила `PG-T-NNN`):** `bigint IDENTITY` или `uuid` v7 для PK, `timestamptz` для бизнес-времени, `numeric(p,s)` для денег, `text` для строк без бизнес-длины. Антипаттерны (`varchar(255)`, `timestamp` без TZ, `varchar(36)` для UUID, `float` для денег) — не должны попасть в ER даже на Tier A.
   4. Жизненный цикл и состояния — только если у сущности есть статусы.
   5. Роли и права доступа — матрица «акторы × команды» + ABAC-условия.
   6. Бизнес-правила (BR-001, BR-002, …).
   7. Commands — список + per-command-карточка (5–10 строк каждая); на Tier B+ — имена классов `UseCase` / `UseCaseCommand`.
   8. Domain Events — Tier B+, если события реально публикуются; Tier C — полный каталог событий.
   9. Queries / Read Model — список чтений; на Tier B+ Level 2 — дизайн Read Model.
   10. Use Cases — сквозные потоки (актор, триггер, основной поток, альтернативные потоки).
   11. UI — экраны + команды + тексты ошибок (только если UI существует).
   12. Saga / Process Manager — Tier C+; пропусти на A/B, если реально нет долгих процессов.
   13. Каталог ошибок — code, HTTP, message, когда поднимается.
   14. Интеграции (Context Mapping) — соседние контексты, типы (ACL, OHS, Conformist, …) на Tier C.
   15. Критерии приёмки — Given/When/Then или нумерованный список на каждый use case.
   16. НФТ — производительность, доступность, согласованность, безопасность, наблюдаемость.

6. **Используй правильную глубину на раздел** (шаблон §«Уровни спеки»):
   - На **Tier A**: пропусти детали §1 «Bounded Context» (называй «модуль»), пропусти §8 «Domain Events», §12 «Saga»; §3 — минимально (только ER-схема).
   - На **Tier B**: добавь §8, только если сервис реально публикует / потребляет события.
   - На **Tier C**: полная глубина, каждый раздел, каждый агрегат.

   Когда раздел осознанно пропущен — **не опускай его молча**, напиши заголовок и однострочную пометку: «Не применимо на Tier A» / «Сервис не публикует доменных событий».

7. **Кросс-ссылайся между разделами через Obsidian wikilinks.** Команды (§7) ссылаются на BR-коды из §6 и коды ошибок из §13. Use Cases (§10) ссылаются на команды и запросы. Sagas (§12) ссылаются на команды. Делай ссылки и в frontmatter (массивы), и в теле:
   - В frontmatter: `errors: ["[[ENERGY_NOT_AVAILABLE]]"]`, `br: ["[[06-<svc>-rules#BR-007]]"]`, `side-effects: ["[[ChargeStarted]]"]`, `consumers: ["[[csms-session]]"]`.
   - В теле: `см. [[06-<svc>-rules#BR-007]]`, `публикует [[ChargeStarted]]`.

   Wikilinks дают рабочие связи в Obsidian Graph View и Backlinks-панели. Уникальность имён карточек на уровне vault'а: ошибки — `<ERROR_CODE>` (UPPER_SNAKE), команды — `<Command>` (PascalCase), события — `<Event>` (PascalCase), агрегаты — `<Aggregate>`.

8. **Код не пиши.** Этот скилл производит только markdown-спеку. Код (классы UseCase, агрегаты, контроллеры) генерируется другими скиллами (`ucp-pattern-design`, `ucp-ddd-tactical-design`) из этой спеки.

9. **Самопроверка перед выдачей.** Пройди эти проверки:
   - Tier в `01-<service>-context.md` соответствует тому, что проект реально из себя представляет.
   - У каждого BR есть код; каждая команда и событие ссылаются на затрагиваемые BR через wikilinks.
   - Глоссарий покрывает каждый термин, использованный в других разделах.
   - Каталог ошибок (§13) совпадает со всеми упоминаниями ошибок в командах и use-cases (через `errors:` во frontmatter команд).
   - Разделы, которые не применимы, имеют явную однострочную пометку, не молчаливое опущение.
   - Frontmatter валиден: на каждой per-item-карточке есть свой `type:` (`error` / `command` / `event` / `aggregate` / `query` / `integration`); на каждом landing-файле секции есть `type: context-section`.
   - Wikilinks ссылаются на существующие имена файлов (никаких опечаток в `[[ChargeStarted]]`).
   - В `docs/spec/` нет консолидированного `<service>.md` — если он есть, удалить.

10. **Структура вывода:**
    1. Один абзац **резюме**: определённый Tier, имя сервиса, какие разделы заполнены и какие намеренно минимальные / помечены «Не применимо».
    2. **Дерево созданных файлов и папок** в `docs/spec/` — точные пути. Это первая проверочная точка для пользователя: правильно ли разделено и заполнен ли frontmatter на per-item-карточках. Полное содержимое в ответе не дублируется — пользователь читает файлы через свой редактор / Obsidian.
    3. **Заметки по реализации**: какие downstream-скиллы возьмут эту спеку дальше (`ucp-pattern-design`, `ucp-ddd-tactical-design`, `ucp-api-design`) и что они произведут. Если пользователь ведёт architecture vault — упомянуть, что папку `docs/spec/` можно скопировать под `architecture/20-systems/<system>/services/<service>/` и связи через wikilinks подхватятся автоматически.

$ARGUMENTS
