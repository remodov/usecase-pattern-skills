---
name: ucp-spec-design
description: Write a Use Case specification for a new or existing service from a business description, following the team's universal spec template (Tier A / B / C). Use when starting a new service, onboarding a legacy module, or formalising what a team has been building informally.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*) Skill(superpowers:*) Bash(mcp__plugin_context7_context7__*)
---

# Use Case Specification — design

You are writing a Use Case specification for a service. The output is **a directory of split markdown files** under `docs/spec/`, one file per section. Files are structured according to the universal 16-section template, with depth chosen by **Tier** (A / B / C).

## Зависимости

Этот скилл предполагает наличие в окружении:

- **Плагин `superpowers`** — для общих рабочих практик планирования и работы с TodoWrite. Если плагина нет, скилл всё равно отработает, но без вспомогательных хелперов.
- **MCP-сервер `context7`** (`mcp__plugin_context7_context7__*`) — для подтягивания актуальной документации по библиотекам, упоминаемым в спеке (Spring Boot, jOOQ и т.п.). Если сервер не подключён, документационные ссылки в спеке оставляются без проверки актуальности.

Если зависимости отсутствуют — скилл сообщает об этом в начале ответа, не падает молча.

## Instructions

1. **Read the template** from `.claude/docs/usecase-spec-template.md` in the project root. It contains the 16-section structure, Tier rules and examples of what each section should contain. Treat it as binding — do not invent your own section names or order.

2. **Determine the Tier** for the service (template §«Уровни спеки»):
   - **Tier A** — legacy / layered service, Controller → Service → Repository, no `usecase-pattern` library.
   - **Tier B** — service uses `usecase-pattern` (UseCase + Handler ± CQRS markers); UCP Levels 1–2.
   - **Tier C** — full DDD / Hexagonal: aggregates, domain events, ports/adapters; UCP Levels 3–4.

   Inspect the project for hints (Java imports of `ru.vikulinva.usecase.*`, presence of `core/` + `adapter/`, `Aggregate*`, `Entity<ID>`). If still unclear, **ask the user** which Tier they want before writing.

3. **Identify the input.** Spec writing is driven by **business description**, not code. The user will hand it to you as one of:
   - a markdown file in the repo (often `case.md`, `business.md`, or similar);
   - a paste in the prompt;
   - a link to an external doc — in which case ask the user to paste the relevant text.

   If the input is too thin to fill even Tier A (no glossary, no actors, no operations), **stop and ask** for what's missing. Do not invent business facts.

4. **Generate the specification as an Obsidian-vault-compatible directory tree** under `docs/spec/`. Это инвариант — на выходе всегда дерево папок и файлов с frontmatter, готовое к копированию в `architecture/20-systems/<system>/services/<service>/` обсидиановского vault'а.

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
   - Service landing (`00-<svc>/<svc>.md`): `type: service|module` + owner/status/criticality/tech-tags.
   - Section landings (`NN-<svc>-<section>.md`): `type: context-section`, `context: <svc>`, `parent: "[[<svc>]]"`, `section: <section>`.
   - Per-item карточки — по своим схемам:
     - `<ERROR_CODE>.md` → `type: error` + `code`, `http`, `severity`, `retryable`, `raised-by[]`.
     - `<Command>.md` → `type: command` + `command`, `actor`, `intent`, `idempotent`, `side-effects[]`, `br[]`, `errors[]`, `returns`.
     - `<Event>.md` → `type: event` + `event`, `aggregate`, `payload-version`, `partition-key`, `retention`, `consumers[]`.
     - `<Aggregate>.md` → `type: aggregate` + `aggregate`, `root`, `states[]`, `emits[]`, `invariants[]`.
     - `<Query>.md` → `type: query` + `query`, `actor`, `returns`, `read-model`.
     - `<edge>.md` → `type: integration` + `integration-type`, `source`, `target`, `direction`, `protocol`, `sync`, `description`, `auth`, `payload[]`, `status`, `idempotency`, `sla`, `ddd-pattern[]`.

   **Консолидированный `<service>.md` не создаётся.** Если потребителю (бизнес-ревью, ingestion в другую AI-сессию) нужен один файл — собирается ad-hoc через `cat`-конкатенацию и не коммитится.

   **Landing раздела с per-item папкой** содержит короткое описание + Dataview-таблицу, которая автоматически собирает карточки. Пример для §13:

   ````markdown
   # 13. Каталог ошибок

   Все ошибки сервиса собираются Dataview-запросом ниже.

   ```dataview
   TABLE WITHOUT ID file.link AS "Code", http AS "HTTP", severity AS "Severity", retryable AS "Retryable"
   FROM ""
   WHERE type = "error" AND file.folder = this.file.folder
   SORT code ASC
   ```
   ````

   Используйте path-independent шаблон `WHERE ... AND file.folder = this.file.folder` (а не `FROM "docs/spec/..."`) — тогда landing-файл соберёт карточки своей же папки независимо от того, где он лежит: `docs/spec/` в проекте или `architecture/20-systems/<sys>/services/<svc>/` в обсидиановском vault'е.

   Никаких ручных списков карточек в landing-файле — Dataview соберёт.

   Имя сервиса (`<service>`) определяется автоматически из аргументов промпта или из существующих маркеров проекта (build.gradle artifactId, pom.xml, README); если не понятно — спросить у пользователя.

   Разделы, неприменимые на текущем Tier-е, **создаются как короткие landing-файлы с одной строкой пояснения** (`Не применимо на Tier A` / `Сервис не публикует доменных событий`) — landing-файл присутствует всегда, даже если внутри секции нет per-item карточек.

5. **Fill all 16 sections** in the order from the template:
   1. Bounded Context (Tier A: «модуль / компонент»; Tier B+: full BC).
   2. Ubiquitous Language — glossary table.
   3. Domain Model — ER for A; +UseCase models for B; +aggregates / VO / events for C.
   4. Жизненный цикл и состояния — only if the entity has statuses.
   5. Роли и права доступа — actors × commands matrix + ABAC conditions.
   6. Бизнес-правила (BR-001, BR-002, …).
   7. Commands — list + per-command card (5–10 lines each); on Tier B+ — `UseCase` / `UseCaseCommand` class names.
   8. Domain Events — Tier B+ if events are actually published; Tier C — full event catalogue.
   9. Queries / Read Model — list of reads; on Tier B+ Level 2 — Read Model design.
   10. Use Cases — end-to-end flows (actor, trigger, main flow, alternative flows).
   11. UI — screens + commands + error texts (only if UI exists).
   12. Saga / Process Manager — Tier C+; skip on A/B unless real long-running processes exist.
   13. Каталог ошибок — code, HTTP, message, when raised.
   14. Интеграции (Context Mapping) — neighbour contexts, types (ACL, OHS, Conformist, …) on Tier C.
   15. Критерии приёмки — Given/When/Then or numbered list per use case.
   16. НФТ — performance, availability, consistency, security, observability.

6. **Use the right depth per section** (template §«Уровни спеки»):
   - On **Tier A**: skip §1 «Bounded Context» details (call it «модуль»), skip §8 «Domain Events», §12 «Saga»; keep §3 minimal (ER schema only).
   - On **Tier B**: add §8 only if the service really publishes/consumes events.
   - On **Tier C**: full depth, every section, every aggregate.

   When a section is intentionally skipped — **do not omit it silently**, write the heading and a one-line note: «Не применимо на Tier A» / «Сервис не публикует доменных событий».

7. **Cross-reference between sections via Obsidian wikilinks.** Commands (§7) refer to BR codes from §6 and error codes from §13. Use Cases (§10) refer to commands and queries. Sagas (§12) refer to commands. Делайте ссылки и в frontmatter (массивы), и в теле:
   - В frontmatter: `errors: ["[[ENERGY_NOT_AVAILABLE]]"]`, `br: ["[[06-<svc>-rules#BR-007]]"]`, `side-effects: ["[[ChargeStarted]]"]`, `consumers: ["[[csms-session]]"]`.
   - В теле: `см. [[06-<svc>-rules#BR-007]]`, `публикует [[ChargeStarted]]`.

   Wikilinks дают рабочие связи в Obsidian Graph View и Backlinks-панели. Уникальность имён карточек на уровне vault'а: ошибки — `<ERROR_CODE>` (UPPER_SNAKE), команды — `<Command>` (PascalCase), события — `<Event>` (PascalCase), агрегаты — `<Aggregate>`.

8. **Do not write code.** This skill produces only the markdown spec. Code (UseCase classes, aggregates, controllers) is generated by other skills (`ucp-pattern-design`, `ucp-ddd-tactical-design`) from this spec.

9. **Self-review before presenting.** Walk through these checks:
   - Tier in `01-<service>-context.md` matches what the project actually is.
   - Every BR has a code; every command and event references the BRs it touches via wikilinks.
   - Glossary covers every term used elsewhere in the spec.
   - Каталог ошибок (§13) matches all error mentions in commands and use cases (через `errors:` во frontmatter команд).
   - Sections that are not applicable have explicit one-line notes, not silent omissions.
   - Frontmatter валиден: на каждой per-item карточке есть свой `type:` (`error` / `command` / `event` / `aggregate` / `query` / `integration`); на каждом landing-файле секции есть `type: context-section`.
   - Wikilinks ссылаются на существующие имена файлов (никаких опечаток в `[[ChargeStarted]]`).
   - В `docs/spec/` нет консолидированного `<service>.md` — если он есть, удалить.

10. **Output structure:**
    1. One-paragraph **summary**: detected Tier, service name, какие разделы заполнены и какие намеренно минимальные / помечены «Не применимо».
    2. **Дерево созданных файлов и папок** в `docs/spec/` — точные пути. Это первая проверочная точка для пользователя: правильно ли разделено и заполнен ли frontmatter на per-item карточках. Полное содержимое в ответе не дублируется — пользователь читает файлы через свой редактор / Obsidian.
    3. **Implementation notes**: какие downstream-скиллы возьмут эту спеку дальше (`ucp-pattern-design`, `ucp-ddd-tactical-design`, `ucp-api-design`), и что они произведут. Если пользователь ведёт architecture vault — упомянуть, что папку `docs/spec/` можно скопировать под `architecture/20-systems/<system>/services/<service>/` и связи через wikilinks подхватятся автоматически.

$ARGUMENTS
