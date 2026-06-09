---
name: ucp-py-cqrs-review
lang: python
description: Ревью CQRS-разделения в FastAPI-сервисе на Python (коды R-CQRS-*) — command через UoW, query через ViewRepository с read-only сессией, read-model денормализована и sync через outbox+Kafka, idempotent consumer, eventual consistency в API.
when_to_use: Ревью Handler с маркерами Command/Query, ViewRepository, read-DTO, outbox-publishers, read-side consumers.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью CQRS (Python / FastAPI + SQLAlchemy)

Ты ревьюишь CQRS на соответствие **контракту** `backend/cqrs/cqrs-rules.md` (`R-CQRS-*`) и **Python-реализации** `backend/cqrs/python/cqrs-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/cqrs/cqrs-rules.md`** + **`backend/cqrs/python/cqrs-style-guide.md`**.
- Парные: `backend/usecase-pattern/python/...` (`Command`/`Query`/Handler), `backend/python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-QRY-5`), `kafka` (outbox/idempotent), `ddd-tactical` (агрегат).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй коды (`R-CQRS-QRY-X2`), не префикс.

2. **Скоп.** Handler-классы с `Command`/`Query`, `*_view_repository.py`, read-DTO, outbox-publishers, read-side consumers, эндпоинты с eventual-consistency; `git diff`.

3. **Прогон.**
   - **Когда/уровень (`R-CQRS-WHEN/TIER-*`):** уровень соответствует зрелости; lightweight-маркеры имеют enforcement (read-only сессия) — иначе `R-CQRS-TIER-X1`; полный split без боли → `R-CQRS-WHEN-X1`; event-driven read-model с одним Repository → `R-CQRS-TIER-X2`.
   - **Command (`R-CQRS-CMD-*`):** `Command[R]`, меняет один агрегат через UoW, возвращает минимум. Read-DTO из command → `R-CQRS-CMD-X2`. SELECT-for-later-update → `R-CQRS-CMD-X1`. Несколько агрегатов без саги → `R-CQRS-CMD-X3`.
   - **Query (`R-CQRS-QRY-*`):** `Query[R]`, через `<X>ViewRepository`, read-only сессия. Write в query → `R-CQRS-QRY-X1`. Грузит агрегат целиком ради read-DTO → `R-CQRS-QRY-X2`. Агрегат/Entity наружу → `R-CQRS-QRY-X3`. Зовёт доменный метод → нарушение `R-CQRS-QRY-4`.
   - **Read-model (`R-CQRS-RM-*`):** денормализована, восстановима, одна сторона. Бизнес-логика в read-model → `R-CQRS-RM-X1`. Source-of-truth read-model → `R-CQRS-RM-X2`. Bidirectional sync → `R-CQRS-RM-X3`.
   - **Sync (`R-CQRS-SYNC-*`):** outbox+Kafka, idempotent consumer, rebuild при бутстрапе, eventual consistency в API. Sync UPDATE read-model в command-UoW → `R-CQRS-SYNC-X1`. PG-триггеры → `R-CQRS-SYNC-X2`. Schema-coupled events → `R-CQRS-SYNC-X3`.

4. **Cross-check:** ViewRepository-реализация — `ucp-py-sqlalchemy-review`; outbox/idempotent consumer — `ucp-py-kafka-review`; агрегат на write-side — `ucp-py-ddd-tactical-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — write в query-handler (`R-CQRS-QRY-X1`), sync UPDATE read-model в command-UoW (`R-CQRS-SYNC-X1`), bidirectional sync (`R-CQRS-RM-X3`), агрегат наружу из query (`R-CQRS-QRY-X3`), schema-coupled events (`R-CQRS-SYNC-X3`).
   - **Предупреждение** — грузит агрегат ради read-DTO (`R-CQRS-QRY-X2`), read-DTO из command (`R-CQRS-CMD-X2`), PG-триггеры sync (`R-CQRS-SYNC-X2`), маркеры без enforcement (`R-CQRS-TIER-X1`), бизнес-логика в read-model (`R-CQRS-RM-X1`).
   - **Замечание** — полный split «just in case» (`R-CQRS-WHEN-X1`), eventual consistency не задекларирована в API (`R-CQRS-SYNC-4`).

## Что не входит

- ViewRepository/SQL — `ucp-py-sqlalchemy-review`. Outbox/consumer — `ucp-py-kafka-review`. Агрегат — `ucp-py-ddd-tactical-review`.

$ARGUMENTS
