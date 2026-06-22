---
name: ucp-go-kafka-design
lang: go
description: Спроектировать работу с Kafka в Go-сервисе (net/http+chi) по UCP (коды R-KFK-*) — Writer RequireAll+Hash, outbox-relay FOR UPDATE SKIP LOCKED, Reader manual commit и processed_event, retry-топики+DLQ вне poll-цикла, событие-структура с конструктором.
when_to_use: Триггеры — «publish событие X в Kafka», «consumer для Y», «outbox-relay на Go». При добавлении producer/consumer/outbox в Go-сервис.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Kafka — проектирование (Go / net/http + chi)

Ты проектируешь работу с Kafka по **контракту** `backend/kafka/kafka-rules.md` (`R-KFK-*`) и **Go-реализации** `backend/kafka/go/kafka-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Go-style-guide. Коды правил цитируй в design-обосновании, **не** в комментариях кода. Связанные: `backend/ddd-tactical/go/...` (событие как неизменяемая структура с конструктором), `backend/cqrs/...` (sync read-model через outbox), `backend/pg-runtime/...` (outbox-relay `FOR UPDATE SKIP LOCKED`), `backend/resilience/go/...` (CB для HTTP из consumer). Помни: в Go ошибки — значения; «retry» реализуется через `avast/retry-go`, CB — `sony/gobreaker`; DI — ручная конструкторная сборка.

2. **Идентифицируй сервис.** `git diff` или путь от пользователя. Структура UCP на Go:
   - `core/<bc>/event/` — событие-структура + конструктор.
   - `core/<bc>/` — UseCase handler; пишет в outbox через UoW-транзакцию.
   - `adapters/in/kafka/` — consumer горутина + idempotent handler.
   - `infra/kafka/` — `Writer`/`Reader` фабрики, outbox-relay, retry-relay, DLQ-relay.
   - `infra/config/` — `KafkaConfig` через `envconfig`.

3. **Producer** (`R-KFK-PROD-*`): `kafka.Writer` с `RequiredAcks: kafka.RequireAll`, `Balancer: &kafka.Hash{}`, `MaxAttempts: math.MaxInt32`; ключ сообщения = aggregate id (`[]byte(aggregateID)`), JSON (`encoding/json`). Domain-события — **через outbox**, не прямой `WriteMessages` из handler (`R-KFK-PROD-4`).

4. **Outbox-relay** (`R-KFK-OBX-*`): запись в таблицу `outbox` в той же `pgx.Tx` (UoW-транзакции); отдельная горутина (`infra/kafka/outbox_relay.go`) читает `SELECT ... FOR UPDATE SKIP LOCKED`, batch 10–50, публикует через `kafka.Writer`, проставляет `published_at`; тик `200ms` через `time.NewTicker`. Partial-индекс `WHERE published_at IS NULL` — через `ucp-pg-schema-design`.

5. **Consumer** (`R-KFK-CONS-*`): `kafka.NewReader` с `CommitInterval: 0` (manual commit), `StartOffset: kafka.FirstOffset`, уникальный `GroupID: "<service>-<purpose>"`. Явный `reader.CommitMessages(ctx, msg)` **после** успешной обработки. Concurrency — N горутин на одном `GroupID`, N ≤ числу партиций.

6. **Idempotent consumer** (`R-KFK-IDEM-*`): `EventID` (UUID v7) в payload; таблица `processed_event` с PRIMARY KEY на `event_id`; `dedup.TryInsert` + бизнес-результат в одной `pgx.Tx`; для money — `EventID` + `Idempotency-Key` на downstream HTTP-вызовах.

7. **Retry + DLQ** (`R-KFK-RTRY-*`): retry-топики с возрастающим delay (например, `<topic>.retry.5s` → `<topic>.retry.30s` → `<topic>.dlq`); задержка реализуется через `time.After(delay)` **вне** poll-цикла основного consumer — каждый retry-топик обслуживается своей горутиной. Определение transient через `errors.As` по Integration-типу (`apperr.Kind`), не по строке. Счётчик попыток в `kafka.Header`. Max-attempts + DLQ + alert на размер DLQ.

8. **Event design** (`R-KFK-EVT-*`): имя — глагол прошедшего времени (`OrderConfirmed`); поля `EventID`, `OccurredAt`, `OrderID`, `EventType` + бизнес-поля; `int64` для денег (минорные единицы), не `float64`; без агрегата целиком и без PII. Структура в `core/<bc>/event/`; единственная точка создания — конструктор `NewXxxEvent(aggregate)`. Десериализация — статический реестр `map[string]func([]byte) (Event, error)`, не `reflect`.

9. **Config/Security/Observability** (`R-KFK-CFG/SEC/OBS-*`): `KafkaConfig` через `envconfig` — `Brokers`, `ClientID`, `Topics.*` с тегом `required:"true"`, TLS через `kafka.Dialer`; per-service `ClientID` для ACL; PII — restricted-топик или «слабая ссылка» (только `customer_id`). Метрики через `promauto`: `kafka_messages_produced_total`, `kafka_messages_consumed_total`, `kafka_processing_errors_total`. Tracing: `traceparent` в `kafka.Header` через OTel propagator (inject на producer, extract на consumer). Alert на consumer lag + DLQ-size.

10. **Самопроверка** — пройдись по чеклисту из `backend/kafka/go/kafka-style-guide.md` §«Чеклист подключения к новому сервису (Go)». DDL outbox-таблицы — через `ucp-pg-schema-design`.

11. **Финальный шаг:** предложи «запусти `ucp-go-kafka-review` для верификации».

## Антипаттерны, которые НЕ генерировать

- `RequiredAcks: kafka.RequireNone` / `kafka.RequireOne` (`R-KFK-PROD-X1/X2`); `Key: nil` в `kafka.Message` для бизнес-событий (`R-KFK-PROD-X3`); `WriteMessages` из UseCase Handler с DB-операцией (`R-KFK-PROD-X4` / `R-KFK-OBX-X1`).
- `CommitInterval > 0` (авто-коммит) (`R-KFK-CONS-X1`); `time.Sleep` / тяжёлая блокировка >1s в poll-цикле без `ctx.Done()` (`R-KFK-CONS-X2`); HTTP из listener без CB (`R-KFK-CONS-X4`).
- Handler без проверки `event_id` при non-idempotent side-effects (`R-KFK-IDEM-X1`); Kafka offset как dedup-ключ (`R-KFK-IDEM-X2`).
- `time.Sleep` / retry **внутри** основной poll-горутины (`R-KFK-RTRY-X1`); проглатывание ошибки + commit (`R-KFK-RTRY-X2`); retry-топик без счётчика попыток (`R-KFK-RTRY-X3`); DLQ без мониторинга (`R-KFK-RTRY-X4`).
- Имя-команда у события (`R-KFK-EVT-X1`); агрегат/Entity целиком в payload (`R-KFK-EVT-X2`); PII в широковещательном топике (`R-KFK-EVT-X3`); breaking change без версии (`R-KFK-EVT-X4`).
- Динамический `reflect` по строке из payload (`R-KFK-CFG-X1`); `Brokers: []string{"localhost:9092"}` хардкодом (`R-KFK-CFG-X2`); `Dialer` без TLS в проде (`R-KFK-SEC-X1`).

После работы скилла — обязательно `ucp-go-kafka-review`.

$ARGUMENTS
