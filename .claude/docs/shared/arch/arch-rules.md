# Architecture Consistency — индекс правил

> **Что это.** Сжатый индекс правил `arch-style-guide.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с примерами, code-блоками, обоснованием и под-пунктами — `arch-style-guide.md`**; открывай её точечно по
> нужному разделу, когда индекса не хватает (под-списки и code-сниппеты сюда не вынесены).
> Коды: `<PREFIX>-<N>` — обязательно, `<PREFIX>-X<N>` — запрещено.

## 1. Реестр и владение
**MUST:**
- **R-ARCH-REG-1.** Каждый сервис в `_registry.yaml` имеет поля `owner`, `tier`, `subdomain` — без них нельзя ни классифицировать сервис, ни связаться с владельцем при инциденте.
- **R-ARCH-REG-2.** Соответствие 1:1 между папкой `services/<name>/` и записью в `_registry.yaml` — orphan-папка или orphan-запись запрещены.
- **R-ARCH-REG-3.** Сервис с `archived: true` не упомянут в активных BP-файлах в `docs/business-processes/`.

## 2. Context map
**MUST:**
- **R-ARCH-CTX-1.** Связь между BC симметрично объявлена в обеих карточках `services/<name>/README.md`: если A → B как customer-supplier, то у B упомянут A как supplier.
- **R-ARCH-CTX-2.** Связь типа `shared-kernel` требует существующего ADR с обоснованием — антипаттерн по умолчанию.
- **R-ARCH-CTX-3.** Каждое событие в `contracts/events/_index.md` имеет ровно одного publisher-сервиса.

## 3. Ubiquitous Language
**MUST:**
- **R-ARCH-UL-1.** Термин из `02-ubiquitous-language.md` встречается в спеках сервисов с тем же определением — иначе UL-конфликт.
- **R-ARCH-UL-2.** Дублирующиеся имена агрегатов между сервисами допустимы только если в `02-ubiquitous-language.md` отмечены как omonym разных контекстов.

## 4. Владение данными
**MUST:**
- **R-ARCH-DATA-1.** Каждая сущность в `03-data-ownership.md` имеет ровно одного owner-сервис.
- **R-ARCH-DATA-2.** Нет двух сервисов, заявляющих один и тот же агрегат как aggregate-root в своих спеках.
- **R-ARCH-DATA-3.** Consumer не имеет write-UC на чужие сущности — owner-edits-only (ADR-0002).

## 5. Бизнес-процессы
**MUST:**
- **R-ARCH-BP-1.** Каждый BP имеет orchestrator-сервис ИЛИ явную пометку «choreography» с обоснованием.
- **R-ARCH-BP-2.** Каждый шаг BP, исполняемый сервисом, имеет соответствующий UC в карточке этого сервиса (actor-шаги типа «Buyer нажимает Купить» исключены).
- **R-ARCH-BP-3.** Каждая точка отказа (🔴) имеет компенсацию ИЛИ явную пометку «нет компенсации, пользователь видит ошибку» с обоснованием.
- **R-ARCH-BP-4.** Компенсация — semantic state-change (UPDATE status), не DELETE (см. `R-DIST-COMP-*`).
- **R-ARCH-BP-5.** Money-шаги имеют idempotency-key — явно в sequence-диаграмме или в таблице шагов.
- **R-ARCH-BP-6.** Sync-шаги между BC объявлены в `06-integration-patterns.md`.

## 6. Контракты
**MUST:**
- **R-ARCH-CONTR-1.** Каждый `openapi.y*ml` в `services/<name>/contracts/` декларирует `info.version`.
- **R-ARCH-CONTR-2.** Каждое событие в AsyncAPI имеет поля `eventId`, `eventType`, `version` (см. `R-KFK-EV-*`).
- **R-ARCH-CONTR-3.** Breaking changes между версиями контракта перечислены — changelog в самом контракте или в `06-integration-patterns.md`.

## 7. Синхронизация со спеками
**MUST:**
- **R-ARCH-SPEC-1.** Каждый агрегат из секции «Домен-агрегаты» карточки `services/<name>/README.md` существует как файл в `services/<name>/spec/aggregates/`.
- **R-ARCH-SPEC-2.** Каждый UC в карточке существует в спеке (`<service>-spec.md` или агрегат-файлах).
- **R-ARCH-SPEC-3.** Упомянутые в карточке BP (секция «Участие в бизнес-процессах») существуют как `docs/business-processes/BP-NN-*.md`.

## 8. Антипаттерны
Все правила `R-ARCH-*` сформулированы как MUST — нарушение конкретного `R-ARCH-<GROUP>-<N>` и есть антипаттерн. Сводка типичных нарушений по группам — в `arch-style-guide.md` §9.
