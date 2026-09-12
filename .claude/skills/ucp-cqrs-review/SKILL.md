---
name: ucp-cqrs-review
description: Ревью CQRS-разделения в Java/Spring (требования cqrs/*) — command-side через aggregate и outbox, query-side через ViewRepository с read-DTO, read-model и sync через события, идемпотентность consumer, eventual consistency в API.
when_to_use: Изменения в Command/Query-handler-ах, ViewRepository, read-DTO, outbox-publisher-ах, read-side consumer-ах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью CQRS

Ты ревьюишь CQRS-разделение в Java/Spring-сервисе на соответствие требованиям `cqrs/*`. Главные точки контроля: маркеры Command/Query, разделение repository vs ViewRepository, read-model структура, eventual consistency через события.

## Зависимости

- **`.claude/docs/backend/cqrs/spec.md`** — индекс всех правил (полный текст — `references/<lang>/implementation.md`). Подгруппы: `R-CQRS-WHEN-*` (когда), `R-CQRS-CMD-*` (command), `R-CQRS-QRY-*` (query), `R-CQRS-RM-*` (read-model), `R-CQRS-SYNC-*` (синхронизация), `R-CQRS-TIER-*` (уровень и эволюция CQRS).
- Парные: `backend/usecase-pattern/spec.md` (`R-UC-*` маркеры), `backend/ddd-tactical/spec.md` (`R-AGG-*`), `backend/java/jooq/spec.md` (`R-JOOQ-VIEW-*`), `backend/kafka/spec.md` (`R-KFK-OBX-*`).

## Инструкции

1. **Прочти** `.claude/docs/backend/cqrs/spec.md`. Цитируй коды конкретно (`cqrs/command-handler-does-not-query`, `cqrs/read-model-is-rebuildable`).

2. **Определи объект ревью.** Если пользователь назвал — бери. Иначе:
   - `git diff` на handlers (`*CommandHandler*`, `*QueryHandler*`), `*ViewRepository*`, `*ReadModel*`, `*Summary.java`, `*Projection*`.
   - DDL `*_summary`, `*_view`, `*_projection` таблиц.
   - Outbox-event records и read-side consumer-listeners.

3. **Прогон по подгруппам:**
   - **`R-CQRS-WHEN-*`** — full CQRS только при явной read-нагрузке; lightweight (маркеры на каждой операции, имя кончается на `Command`/`Query`) обязателен на Уровне 2+; не разделять базы без причины.
   - **`R-CQRS-CMD-*`** — Command — record + UseCaseCommand; меняет один агрегат; `@Transactional` RW; load aggregate с FOR UPDATE; сохраняет; outbox event; возвращает минимум (id/status), не read-DTO.
   - **`R-CQRS-QRY-*`** — Query — record + UseCaseQuery; `@Transactional(readOnly = true)`; через ViewRepository; возвращает read-DTO, не агрегат.
   - **`R-CQRS-RM-*`** — read-model в оптимальном месте; денормализована; обновляется через события; восстановима из write-side; без бизнес-логики; не source-of-truth; не bidirectional.
   - **`R-CQRS-SYNC-*`** — outbox + Kafka, не sync UPDATE в TX; idempotent consumer (`processed_event`); bootstrap-задача для rebuild; eventual consistency в OpenAPI description; read-your-writes когда критично.
   - **`R-CQRS-TIER-*`** — Уровень 1 без маркеров; Уровень 2 lightweight маркеры; Уровень 3 полный split с ViewRepository; event-driven read-model; эволюция в одну сторону.

4. **Ищи паттерны-нарушения:**
   - `Command*Handler` делает отдельный `SELECT` для чтения (не load-aggregate one-shot) — `cqrs/command-handler-does-not-query`.
   - `Command*Handler` возвращает полный read-DTO (`OrderJson` со всеми вложениями) — `cqrs/command-returns-minimum`.
   - `Command*Handler` меняет 2+ агрегата в одной транзакции — `cqrs/command-changes-one-aggregate` (нужна saga).
   - `Query*Handler` делает `INSERT`/`UPDATE`/`DELETE` — `cqrs/query-is-read-only`.
   - `Query*Handler` грузит агрегат через основной `<X>Repository.findById()` (с multiset, FOR UPDATE) и маппит в read-DTO — `cqrs/read-via-projection-not-aggregate` (использовать `<X>ViewRepository`).
   - `Query*Handler` возвращает `Order` (агрегат) или `OrderItem` (Entity внутри) наружу — `cqrs/query-returns-read-model`.
   - Read-model таблица с `CHECK`-constraint бизнес-правил или PG-триггерами для логики — `cqrs/projection-has-no-logic-or-backflow`.
   - Read-model — единственный источник данных без скрипта rebuild из write-side — `cqrs/read-model-is-rebuildable`.
   - Read-model UPDATE → write-side INSERT (обратный sync) — `cqrs/projection-has-no-logic-or-backflow`.
   - В command-handler синхронный `INSERT INTO <x>_summary` сразу после `repository.save(aggregate)` (не через outbox) — `cqrs/read-model-synced-by-events`.
   - PG-триггер на write-таблицу обновляет read-таблицу — `cqrs/read-model-synced-by-events`.
   - Event-record содержит generated POJO write-схемы (`OrdersPojo` в payload) — `cqrs/events-not-coupled-to-write-schema`.
   - Проект Уровня 1 с маркерами `UseCaseCommand`/`Query` без `@Transactional(readOnly = true)` enforcement — `cqrs/split-matches-maturity-level` (карго-культ).
   - Один `<X>Repository` для read и write при наличии отдельной read-таблицы — `cqrs/split-matches-maturity-level`.

5. **При ревью OpenAPI:**
   - Endpoint, отдающий read-проекцию, имеет `description: '...задержка до N секунд...'` если eventual consistent — `cqrs/eventual-consistency-declared`.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md`.

7. **Доменные ориентиры серьёзности**:
   - **Критично:**
     - Sync UPDATE read-model в command-TX (теряется decoupling).
     - PG-триггеры для CQRS-sync (невидимая магия).
     - Несколько агрегатов в одном command-handler без саги.
     - Read-model bidirectional sync (data inconsistency risk).
     - Query handler делает write (нарушение разделения).
   - **Предупреждение:**
     - Query грузит агрегат целиком вместо ViewRepository.
     - Полный CQRS без явной нагрузочной причины.
     - Read-model с CHECK-constraint бизнес-правил.
     - Eventual consistency не задекларирован в API.
   - **Замечание:**
     - Command возвращает больше необходимого (read-DTO).
     - Уровень 1 с маркерами без enforcement.

## Что не входит

- Domain aggregate / VO / Entity — `ucp-ddd-tactical-review`.
- UseCase Pattern маркеры implementation — `ucp-pattern-review`.
- jOOQ ViewRepository implementation — `ucp-jooq-review`.
- Kafka outbox / consumer impl — `ucp-kafka-review`.
- Materialized views / partial-indexes для read-model — `ucp-pg-explain-review` / `ucp-pg-runtime-review`.

$ARGUMENTS
