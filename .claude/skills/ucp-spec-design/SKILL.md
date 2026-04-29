---
name: ucp-spec-design
description: Write a Use Case specification for a new or existing service from a business description, following the team's universal spec template (Tier A / B / C). Use when starting a new service, onboarding a legacy module, or formalising what a team has been building informally.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*) Skill(superpowers:*) Bash(mcp__plugin_context7_context7__*)
---

# Use Case Specification — design

You are writing a Use Case specification for a service. The output is **a directory of split markdown files** under `docs/spec/`, one file per section, plus a consolidated `<service>.md` that concatenates all sections for sharing and ingestion. Files are structured according to the universal 16-section template, with depth chosen by **Tier** (A / B / C).

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

4. **Generate the specification as split markdown files** under `docs/spec/`. This is an invariant — never produce a single-file spec. Layout:

   ```
   docs/spec/
     01-<service>-context.md          — Bounded Context
     02-<service>-language.md         — Ubiquitous Language
     03-<service>-model.md            — Domain Model
     04-<service>-lifecycle.md        — Жизненный цикл и состояния
     05-<service>-roles.md            — Роли и права
     06-<service>-rules.md            — Бизнес-правила
     07-<service>-commands.md         — Commands
     08-<service>-events.md           — Domain Events (Tier B+ если есть события)
     09-<service>-queries.md          — Queries / Read Model
     10-<service>-use-cases.md        — Use Cases
     11-<service>-ui.md               — UI (если есть)
     12-<service>-sagas.md            — Saga / Process Manager (Tier C+)
     13-<service>-errors.md           — Каталог ошибок
     14-<service>-integrations.md     — Интеграции
     15-<service>-acceptance.md       — Критерии приёмки
     16-<service>-nfr.md              — НФТ
     17-<service>-stack.md            — Стек технологий
     <service>.md                     — Консолидированная версия (все разделы вместе)
   ```

   - Каждый файл начинается с `# N. <Section title>` (markdown H1) и содержит только свой раздел.
   - Frontmatter с `title`, `tier`, `service`, `last_updated` — **только в консолидированном `<service>.md`**, в split-файлах frontmatter не нужен.
   - Консолидированный `<service>.md` собирается из split-файлов (порядок 01 → 17), плюс короткий вводный абзац перед §1. Это файл для шаринга с бизнесом и для ingestion в другие AI-сессии — всегда обновляется синхронно с split-файлами.

   Имя сервиса (`<service>`) определяется автоматически из аргументов промпта или из существующих маркеров проекта (build.gradle artifactId, pom.xml, README); если не понятно — спросить у пользователя.

   Разделы, неприменимые на текущем Tier-е, **создаются как короткие файлы с одной строкой пояснения** (`Не применимо на Tier A` / `Сервис не публикует доменных событий`), не пропускаются молча. Это сохраняет нумерацию и позволяет PR-обзору видеть «решение опустить раздел» как явный артефакт.

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

7. **Cross-reference between sections.** Commands (§7) refer to BR codes from §6 and error codes from §13. Use Cases (§10) refer to commands and queries. Sagas (§12) refer to commands. Make these refs explicit (`см. §6 / BR-007`).

8. **Do not write code.** This skill produces only the markdown spec. Code (UseCase classes, aggregates, controllers) is generated by other skills (`ucp-pattern-design`, `ucp-ddd-tactical-design`) from this spec.

9. **Self-review before presenting.** Walk through these checks:
   - Tier is declared in the frontmatter and matches what the project actually is.
   - Every BR has a code; every command and event references the BRs it touches.
   - Glossary covers every term used elsewhere in the spec.
   - Каталог ошибок (§13) matches all error mentions in commands and use cases.
   - Sections that are not applicable have explicit one-line notes, not silent omissions.

10. **Output structure:**
    1. One-paragraph **summary**: detected Tier, service name, какие разделы заполнены и какие намеренно минимальные / помечены «Не применимо».
    2. **Список созданных файлов** в `docs/spec/` — точные пути и назначение каждого. Это первая проверочная точка для пользователя: правильно ли разделено.
    3. Консолидированный `<service>.md` показывается полностью в ответе (под заголовком с путём). Split-файлы — только пути, без полного содержимого, чтобы не дублировать.
    4. **Implementation notes**: какие downstream-скиллы возьмут эту спеку дальше (`ucp-pattern-design`, `ucp-ddd-tactical-design`, `ucp-api-design`), и что они произведут.

$ARGUMENTS
