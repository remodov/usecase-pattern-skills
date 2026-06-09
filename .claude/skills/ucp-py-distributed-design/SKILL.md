---
name: ucp-py-distributed-design
lang: python
description: Спроектировать распределённый сценарий в Python-микросервисах по UCP (коды R-DIST-*) — saga orchestration/choreography со state-таблицей и сквозным saga_id, idempotency, outbox+inbox, compensation, eventual consistency, запрет 2PC/XA.
when_to_use: Триггеры — «saga для X», «cross-service процесс Y», «компенсация Z на питоне». Для cross-service бизнес-операции.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Distributed Patterns — проектирование (Python / saga + UoW + aiokafka)

Ты проектируешь распределённый сценарий по **контракту** `backend/distributed-patterns/distributed-patterns-rules.md`
(`R-DIST-*`) и **Python-реализации** `backend/distributed-patterns/python/distributed-patterns-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Python-style-guide. Коды в обосновании, не в коде. Связанные: `backend/kafka/python/...` (outbox/idempotent consumer), `cqrs` (EC read-model), `backend/usecase-pattern/python/...` (UoW), `pg-runtime` (saga/idempotency-таблицы).

2. **Проверь необходимость** (`R-DIST-WHEN-*`): только если операция cross-service. Один сервис+PG → локальный UoW. Сначала альтернативы (объединить BC, modular monolith). Назови решение.

3. **Saga** (`R-DIST-SAGA-*`): orchestration (центральный координатор, отдельный компонент) для 4+ шагов/branching; choreography (события) для 2–3; **state в БД** (`saga_<name>`); `saga_id` сквозной; каждый шаг — локальная транзакция.

4. **Idempotency** (`R-DIST-IDEM-*`): уникальный id сообщения; receiver `processed_event` (запись в той же UoW); HTTP — `(idempotency_key, response)`; money — `Idempotency-Key` + UNIQUE `(provider, external_id)`; TTL 24–72ч.

5. **Eventual consistency** (`R-DIST-EC-*`): декларация в OpenAPI; read-your-writes если критично; bounded-staleness SLO + alert; causal через `version`-поля.

6. **Outbox/Compensation** (`R-DIST-OBX/COMP-*`): outbox обязателен (`ucp-py-kafka-design`); на каждый шаг — идемпотентная **semantic** compensation (refund, не rollback) с audit; DLQ при сбое compensation.

7. **Запрет** (`R-DIST-TX-*`): без 2PC/XA/цепочек commit по нескольким сессиям. Самопроверка (§8) + предложи `ucp-py-distributed-review`.

## Антипаттерны, которые НЕ генерировать

- Saga для одного сервиса (`R-DIST-WHEN-X1`); saga без compensation (`R-DIST-SAGA-X2`/`R-DIST-COMP-X1`); saga state in-memory (`R-DIST-SAGA-X3`); saga в одном handler с use case (`R-DIST-SAGA-X4`).
- Receiver без dedup для money (`R-DIST-IDEM-X1`); idempotency-key новый на каждый retry (`R-DIST-IDEM-X3`); молчаливая EC (`R-DIST-EC-X1`).
- `DELETE` как compensation (`R-DIST-COMP-X2`); compensation без повторного compensation/DLQ (`R-DIST-COMP-X3`).
- 2PC/XA (`R-DIST-TX-X1`); multi-datasource-commit-цепочка (`R-DIST-TX-X3`); прямой send без outbox (`R-DIST-OBX-X1`).

После работы скилла — обязательно `ucp-py-distributed-review`.

$ARGUMENTS
