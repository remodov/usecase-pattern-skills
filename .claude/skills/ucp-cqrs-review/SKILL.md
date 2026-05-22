---
name: ucp-cqrs-review
description: Ревью CQRS-разделения — когда применён (с учётом уровня зрелости), command-side (запись через aggregate, FOR UPDATE, outbox), query-side (через ViewRepository с read-DTO), read-model (отдельная таблица/Redis/ES, sync через события, не bidirectional, не source-of-truth), синхронизация через outbox+Kafka не sync UPDATE в TX, идемпотентность consumer, eventual consistency декларирована в API, антипаттерны (write в query handler, query грузит агрегат целиком, read-model с бизнес-логикой, sync через PG triggers). Применяется при ревью UseCase/Handler-классов с маркерами Command/Query, ViewRepository, read-DTO, outbox-publishers, read-side consumers. Опирается на коды R-CQRS-*.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью CQRS

Ты ревьюишь CQRS-разделение в Java/Spring-сервисе на соответствие CQRS Style Guide. Главные точки контроля: маркеры Command/Query, разделение repository vs ViewRepository, read-model структура, eventual consistency через события.

## Зависимости

- **`.claude/docs/cqrs-rules.md`** — индекс всех правил (полный текст — соответствующий `*-style-guide.md`). Подгруппы: `R-CQRS-WHEN-*` (когда), `R-CQRS-CMD-*` (command), `R-CQRS-QRY-*` (query), `R-CQRS-RM-*` (read-model), `R-CQRS-SYNC-*` (синхронизация), `R-CQRS-TIER-*` (уровень и эволюция CQRS).
- Парные: `usecase-pattern-rules.md` (`R-UC-*` маркеры), `ddd-tactical-rules.md` (`R-AGG-*`), `jooq-rules.md` (`R-JOOQ-VIEW-*`), `kafka-rules.md` (`R-KFK-OBX-*`).

## Инструкции

1. **Прочти** `.claude/docs/cqrs-rules.md`. Цитируй коды конкретно (`R-CQRS-CMD-X1`, `R-CQRS-RM-X2`).

2. **Определи объект ревью.** Если пользователь назвал — бери. Иначе:
   - `git diff` на handlers (`*CommandHandler*`, `*QueryHandler*`), `*ViewRepository*`, `*ReadModel*`, `*Summary.java`, `*Projection*`.
   - DDL `*_summary`, `*_view`, `*_projection` таблиц.
   - Outbox-event records и read-side consumer-listeners.

3. **Прогон по подгруппам:**
   - **`R-CQRS-WHEN-*`** — full CQRS только при явной read-нагрузке; lightweight (маркеры) обязателен на Уровне 2+ (CQRS — опция Уровня 2); не разделять базы без причины.
   - **`R-CQRS-CMD-*`** — Command — record + UseCaseCommand; меняет один агрегат; `@Transactional` RW; load aggregate с FOR UPDATE; сохраняет; outbox event; возвращает минимум (id/status), не read-DTO.
   - **`R-CQRS-QRY-*`** — Query — record + UseCaseQuery; `@Transactional(readOnly = true)`; через ViewRepository; возвращает read-DTO, не агрегат.
   - **`R-CQRS-RM-*`** — read-model в оптимальном месте; денормализована; обновляется через события; восстановима из write-side; без бизнес-логики; не source-of-truth; не bidirectional.
   - **`R-CQRS-SYNC-*`** — outbox + Kafka, не sync UPDATE в TX; idempotent consumer (`processed_event`); bootstrap-задача для rebuild; eventual consistency в OpenAPI description; read-your-writes когда критично.
   - **`R-CQRS-TIER-*`** — Уровень 1 без маркеров; Уровень 2 lightweight маркеры; Уровень 3 полный split с ViewRepository; event-driven read-model; эволюция в одну сторону.

4. **Ищи паттерны-нарушения:**
   - `Command*Handler` делает отдельный `SELECT` для чтения (не load-aggregate one-shot) — `R-CQRS-CMD-X1`.
   - `Command*Handler` возвращает полный read-DTO (`OrderJson` со всеми вложениями) — `R-CQRS-CMD-X2`.
   - `Command*Handler` меняет 2+ агрегата в одной транзакции — `R-CQRS-CMD-X3` (нужна saga).
   - `Query*Handler` делает `INSERT`/`UPDATE`/`DELETE` — `R-CQRS-QRY-X1`.
   - `Query*Handler` грузит агрегат через основной `<X>Repository.findById()` (с multiset, FOR UPDATE) и маппит в read-DTO — `R-CQRS-QRY-X2` (использовать `<X>ViewRepository`).
   - `Query*Handler` возвращает `Order` (агрегат) или `OrderItem` (Entity внутри) наружу — `R-CQRS-QRY-X3`.
   - Read-model таблица с `CHECK`-constraint бизнес-правил или PG-триггерами для логики — `R-CQRS-RM-X1`.
   - Read-model — единственный источник данных без скрипта rebuild из write-side — `R-CQRS-RM-X2`.
   - Read-model UPDATE → write-side INSERT (обратный sync) — `R-CQRS-RM-X3`.
   - В command-handler синхронный `INSERT INTO <x>_summary` сразу после `repository.save(aggregate)` (не через outbox) — `R-CQRS-SYNC-X1`.
   - PG-триггер на write-таблицу обновляет read-таблицу — `R-CQRS-SYNC-X2`.
   - Event-record содержит generated POJO write-схемы (`OrdersPojo` в payload) — `R-CQRS-SYNC-X3`.
   - Проект Уровня 1 с маркерами `UseCaseCommand`/`Query` без `@Transactional(readOnly = true)` enforcement — `R-CQRS-TIER-X1` (карго-культ).
   - Один `<X>Repository` для read и write при наличии отдельной read-таблицы — `R-CQRS-TIER-X2`.

5. **При ревью OpenAPI:**
   - Endpoint, отдающий read-проекцию, имеет `description: '...задержка до N секунд...'` если eventual consistent — `R-CQRS-SYNC-4`.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/review-finding-format.md`.

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
