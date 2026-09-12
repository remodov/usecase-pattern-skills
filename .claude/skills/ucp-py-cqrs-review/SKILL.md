---
name: ucp-py-cqrs-review
lang: python
description: Ревью CQRS-разделения в FastAPI-сервисе на Python (требования cqrs/*) — command через UoW, query через ViewRepository с read-only сессией, read-model денормализована и sync через outbox+Kafka, idempotent consumer, eventual consistency в API.
when_to_use: Ревью Handler с маркерами Command/Query, ViewRepository, read-DTO, outbox-publishers, read-side consumers.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью CQRS (Python / FastAPI + SQLAlchemy)

Ты ревьюишь CQRS на соответствие **контракту** `backend/cqrs/spec.md` (`R-CQRS-*`) и **Python-реализации** `backend/cqrs/references/python/implementation.md`.

## Зависимости

- **`.claude/docs/backend/cqrs/spec.md`** + **`backend/cqrs/references/python/implementation.md`**.
- Парные: `backend/usecase-pattern/python/...` (`Command`/`Query`/Handler), `backend/python/sqlalchemy/spec.md` (`sqlalchemy/view-repository-for-projections`), `kafka` (outbox/idempotent), `ddd-tactical` (агрегат).

## Инструкции

1. **Прочти** требования `python-style/*`. Цитируй коды (`cqrs/read-via-projection-not-aggregate`), не префикс.

2. **Скоп.** Handler-классы с `Command`/`Query`, `*_view_repository.py`, read-DTO, outbox-publishers, read-side consumers, эндпоинты с eventual-consistency; `git diff`.

3. **Прогон.**
   - **Когда/уровень (`R-CQRS-WHEN/TIER-*`):** уровень соответствует зрелости; lightweight-маркеры имеют enforcement (read-only сессия) — иначе `cqrs/split-matches-maturity-level`; полный split без боли → `cqrs/lightweight-first-full-on-evidence`; event-driven read-model с одним Repository → `cqrs/split-matches-maturity-level`.
   - **Command (`R-CQRS-CMD-*`):** `Command[R]`, меняет один агрегат через UoW, возвращает минимум. Read-DTO из command → `cqrs/command-returns-minimum`. SELECT-for-later-update → `cqrs/command-handler-does-not-query`. Несколько агрегатов без саги → `cqrs/command-changes-one-aggregate`.
   - **Query (`R-CQRS-QRY-*`):** `Query[R]`, через `<X>ViewRepository`, read-only сессия. Write в query → `cqrs/query-is-read-only`. Грузит агрегат целиком ради read-DTO → `cqrs/read-via-projection-not-aggregate`. Агрегат/Entity наружу → `cqrs/query-returns-read-model`. Зовёт доменный метод → нарушение `cqrs/query-is-read-only`.
   - **Read-model (`R-CQRS-RM-*`):** денормализована, восстановима, одна сторона. Бизнес-логика в read-model → `cqrs/projection-has-no-logic-or-backflow`. Source-of-truth read-model → `cqrs/read-model-is-rebuildable`. Bidirectional sync → `cqrs/projection-has-no-logic-or-backflow`.
   - **Sync (`R-CQRS-SYNC-*`):** outbox+Kafka, idempotent consumer, rebuild при бутстрапе, eventual consistency в API. Sync UPDATE read-model в command-UoW → `cqrs/read-model-synced-by-events`. PG-триггеры → `cqrs/read-model-synced-by-events`. Schema-coupled events → `cqrs/events-not-coupled-to-write-schema`.

4. **Cross-check:** ViewRepository-реализация — `ucp-py-sqlalchemy-review`; outbox/idempotent consumer — `ucp-py-kafka-review`; агрегат на write-side — `ucp-py-ddd-tactical-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — write в query-handler (`cqrs/query-is-read-only`), sync UPDATE read-model в command-UoW (`cqrs/read-model-synced-by-events`), bidirectional sync (`cqrs/projection-has-no-logic-or-backflow`), агрегат наружу из query (`cqrs/query-returns-read-model`), schema-coupled events (`cqrs/events-not-coupled-to-write-schema`).
   - **Предупреждение** — грузит агрегат ради read-DTO (`cqrs/read-via-projection-not-aggregate`), read-DTO из command (`cqrs/command-returns-minimum`), PG-триггеры sync (`cqrs/read-model-synced-by-events`), маркеры без enforcement (`cqrs/split-matches-maturity-level`), бизнес-логика в read-model (`cqrs/projection-has-no-logic-or-backflow`).
   - **Замечание** — полный split «just in case» (`cqrs/lightweight-first-full-on-evidence`), eventual consistency не задекларирована в API (`cqrs/eventual-consistency-declared`).

## Что не входит

- ViewRepository/SQL — `ucp-py-sqlalchemy-review`. Outbox/consumer — `ucp-py-kafka-review`. Агрегат — `ucp-py-ddd-tactical-review`.

$ARGUMENTS
