# Distributed Patterns — Python Style Guide (saga + UoW + aiokafka)

Реализация язык-нейтрального контракта `../distributed-patterns-rules.md` (`R-DIST-*`) на Python. Паттерны
(saga/idempotency/eventual consistency/outbox/compensation) архитектурные — одни на всех языках; меняется
реализация транзакций (`@Transactional` → Unit of Work над `AsyncSession`) и запреты 2PC.

## 1. Когда нужны (`R-DIST-WHEN-*`)

`R-DIST-WHEN-1` — операция охватывает 2+ сервиса и не завершается одной локальной транзакцией. `R-DIST-WHEN-2` —
один сервис + один PG → обычный UoW + атомарность БД, без распределённых паттернов. `R-DIST-WHEN-3` — сначала
проверь альтернативы (объединить BC, modular monolith). `R-DIST-WHEN-X1` — saga для двух операций в одной БД.
`R-DIST-WHEN-X2` — микросервисы «из амбиций» (latency, debugging, новые failure modes) — лучше modular monolith.

## 2. Saga (`R-DIST-SAGA-*`)

`R-DIST-SAGA-1` — saga, когда операция cross-service с локальными транзакциями на каждом шаге. `R-DIST-SAGA-2` —
**orchestration** (центральный координатор) для сложных saga (4+ шага, branching). `R-DIST-SAGA-3` — **choreography**
(события без координатора) для простых (2–3 шага). `R-DIST-SAGA-4` — **saga state в БД** (`saga_<name>`-таблица:
`saga_id`, `status`, `current_step`, `payload`) — видимость, recovery, audit. `R-DIST-SAGA-5` — `saga_id` сквозной
в каждом сообщении.

Orchestrator — отдельный компонент (`OrderSagaOrchestrator`), не handler: реагирует на события шагов, продвигает
state в БД, шлёт следующую команду через outbox. Без готовой Spring-saga-либы — хэндмейд на event-driven шагах
(или библиотека вроде `temporalio`, если в стеке).

`R-DIST-SAGA-X1` — 2PC/XA через distributed-TX вместо saga (Kafka не XA). `R-DIST-SAGA-X2` — saga без compensation
(«полусделанная» транзакция). `R-DIST-SAGA-X3` — saga state in-memory (рестарт теряет in-flight saga). `R-DIST-SAGA-X4` —
saga в одном handler с use case (orchestrator — отдельный компонент).

## 3. Idempotency (`R-DIST-IDEM-*`)

`R-DIST-IDEM-1` — у каждого cross-service сообщения уникальный id (`event_id`/`message_id`). `R-DIST-IDEM-2` —
receiver хранит `processed_event` (проверка до, запись в той же UoW-транзакции, cross-ref `R-KFK-IDEM-2`).
`R-DIST-IDEM-3` — для HTTP-команд хранить `(idempotency_key, response)`; повтор с тем же ключом → сохранённый ответ;
другой `command_hash` с тем же ключом → `409 Conflict`. `R-DIST-IDEM-4` — money: `Idempotency-Key` +
UNIQUE `(provider_id, external_payment_id)`. `R-DIST-IDEM-5` — TTL idempotency-записей 24–72ч.

`R-DIST-IDEM-X1` — receiver без dedup для money/critical. `R-DIST-IDEM-X2` — только receiver-side (producer тоже
exactly-once: aiokafka `enable_idempotence=True`, `R-KFK-PROD-1`). `R-DIST-IDEM-X3` — `Idempotency-Key` = новый UUID
на каждый retry (ключ генерируется один раз на бизнес-операцию).

## 4. Eventual consistency (`R-DIST-EC-*`)

`R-DIST-EC-1` — декларация в OpenAPI (задержка read-проекции) — FastAPI: в описании эндпоинта/response-модели.
`R-DIST-EC-2` — read-your-writes при необходимости (читать из write-side / version-токен). `R-DIST-EC-3` — bounded
staleness с явным SLO + alert. `R-DIST-EC-4` — causal consistency через `version`-поля (receiver применяет, только
если `event.version > current_version`, иначе skip).

`R-DIST-EC-X1` — молчаливая EC (stale-data без декларации). `R-DIST-EC-X2` — strict consistency через 2PC под
нагрузкой (перепроектируй boundary или прими EC).

## 5. Outbox + Inbox (`R-DIST-OBX-*`)

`R-DIST-OBX-1` — **outbox** для исходящих событий обязателен (`R-KFK-OBX-*`, `ucp-py-kafka-*`). `R-DIST-OBX-2` —
**inbox** для входящих (опционально, critical): сохранить сообщение в `inbox` до обработки, обработать асинхронно.
`R-DIST-OBX-3` — single source of truth — БД сервиса; Kafka — транспорт (потеря Kafka → outbox продолжает копить).

`R-DIST-OBX-X1` — прямой `producer.send` из command-handler без outbox (`R-KFK-PROD-X4`). `R-DIST-OBX-X2` —
публикация после commit без outbox (`R-KFK-OBX-X2`).

## 6. Compensation (`R-DIST-COMP-*`)

`R-DIST-COMP-1` — у каждой command в саге есть compensation-команда. `R-DIST-COMP-2` — compensation идемпотентен
(saga может повторить). `R-DIST-COMP-3` — **semantic compensation**, не технический rollback (был платёж →
compensation = refund новой транзакцией). `R-DIST-COMP-4` — compensation оставляет audit trail (статус `refunded`
+ ссылка на оригинал), не DELETE/UPDATE-с-потерей.

`R-DIST-COMP-X1` — saga без compensation. `R-DIST-COMP-X2` — `DELETE` как compensation («создан заказ» → «cancelled»,
не `DELETE FROM orders`). `R-DIST-COMP-X3` — compensation, которое может упасть без повторного compensation/DLQ
(висящие деньги).

## 7. Distributed transactions — чего НЕ делать (`R-DIST-TX-*`)

`R-DIST-TX-X1` — 2PC/XA в стеке (Kafka не XA, не масштабируется, SPOF). `R-DIST-TX-X2` — единая распределённая
транзакция через несколько datasource. `R-DIST-TX-X3` — «цепочка» commit'ов по нескольким сессиям/БД (best-effort,
не атомарность; в Python — несколько `AsyncSession`/engine с ручным последовательным commit) — при сбое между
commit'ами inconsistency без recovery.

`R-DIST-TX-1` — saga с локальными транзакциями (стандарт). `R-DIST-TX-2` — outbox + idempotent consumer для
event-driven sync. `R-DIST-TX-3` — modular monolith (несколько BC в одном процессе с одним PG) при tight coupling —
локальный UoW работает.

## 8. Чеклист подключения к новому сервису (Python)

1. Распределённые паттерны только при cross-service операции; иначе локальный UoW.
2. Saga: orchestrator отдельным компонентом, state в БД, `saga_id` сквозной, есть compensation на каждый шаг.
3. Idempotency: уникальный id, `processed_event`/idempotency-key, money — двойная защита, producer+receiver.
4. Eventual consistency задекларирована, bounded-staleness SLO; нет молчаливой EC.
5. Outbox обязателен; БД — source of truth; нет прямого send из handler.
6. Compensation — semantic state-change с audit, идемпотентен, есть DLQ при сбое.
7. Нет 2PC/XA/multi-datasource-commit-цепочек.
