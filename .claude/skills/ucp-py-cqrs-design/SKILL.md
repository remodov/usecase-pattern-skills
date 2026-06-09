---
name: ucp-py-cqrs-design
lang: python
description: Спроектировать CQRS-разделение в FastAPI-сервисе (Python) по UCP (коды R-CQRS-*) — маркеры Command/Query (Уровень 2) или полный split (Уровень 3: <X>ViewRepository, read-DTO), read-model через outbox+Kafka, idempotent consumer.
when_to_use: Триггеры — «CQRS для X», «read-модель Y», «вынести чтение в проекцию». При добавлении read-проекций.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# CQRS — проектирование (Python / FastAPI + SQLAlchemy)

Ты проектируешь CQRS по **контракту** `backend/cqrs/cqrs-rules.md` (`R-CQRS-*`) и **Python-реализации** `backend/cqrs/python/cqrs-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Python-style-guide. Коды в обосновании, не в коде. Связанные: `backend/usecase-pattern/python/...` (`Command`/`Query`/Handler/UoW), `backend/python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-QRY-5` ViewRepository), `kafka` (outbox sync), `ddd-tactical` (агрегат на write-side).

2. **Реши уровень** (`R-CQRS-WHEN-*`/`R-CQRS-TIER-*`): Уровень 2 → lightweight (маркеры + read-only сессия, один Repository); Уровень 3 → `<X>ViewRepository` + read-DTO; event-driven → отдельная read-таблица/Redis/ES + outbox. Не вводи полный split без доказанной read-нагрузки (`R-CQRS-WHEN-X1`). Назови выбор.

3. **Command side** (`R-CQRS-CMD-*`): `@dataclass(frozen=True)` `Command[R]`; меняет один агрегат; handler load→доменный метод→save→commit через UoW; возвращает минимум (id/статус/`None`), не read-DTO.

4. **Query side** (`R-CQRS-QRY-*`): `Query[R]`; handler через `<X>ViewRepository`, read-only сессия, без commit; read-DTO (frozen dataclass/Pydantic) под UI; не зовёт доменные методы, не пишет.

5. **Read-model** (`R-CQRS-RM/SYNC-*`): денормализована, восстановима (rebuild-скрипт); sync через **outbox + Kafka** в одну сторону, idempotent consumer (`processed_event`); eventual consistency задекларируй в OpenAPI; read-your-writes если критично.

6. **Самопроверка** (§7) + предложи `ucp-py-cqrs-review`. Read-проекции в SQLAlchemy — `ucp-py-sqlalchemy-design`; outbox-publishing — `ucp-py-kafka-design`.

## Антипаттерны, которые НЕ генерировать

- Полный CQRS/разделение БД без боли (`R-CQRS-WHEN-X1/X2`); маркеры без enforcement (`R-CQRS-TIER-X1`).
- Read-DTO из command (`R-CQRS-CMD-X2`); SELECT-for-later-update в command (`R-CQRS-CMD-X1`); несколько агрегатов в одном UoW без саги (`R-CQRS-CMD-X3`).
- Write в query-handler (`R-CQRS-QRY-X1`); загрузка агрегата целиком ради read-DTO (`R-CQRS-QRY-X2`); агрегат наружу из query (`R-CQRS-QRY-X3`).
- Sync UPDATE read-model в command-UoW (`R-CQRS-SYNC-X1`); PG-триггеры (`R-CQRS-SYNC-X2`); schema-coupled events (`R-CQRS-SYNC-X3`); bidirectional sync (`R-CQRS-RM-X3`).

После работы скилла — обязательно `ucp-py-cqrs-review`.

$ARGUMENTS
