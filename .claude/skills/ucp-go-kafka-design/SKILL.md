---
name: ucp-go-kafka-design
lang: go
description: Спроектировать работу с Kafka в Go-сервисе (net/http+chi) по UCP — Writer RequireAll+Hash, outbox-relay FOR UPDATE SKIP LOCKED, Reader manual commit и processed_event, retry-топики+DLQ вне poll-цикла, событие-структура с конструктором.
when_to_use: Триггеры — «publish событие X в Kafka», «consumer для Y», «outbox-relay на Go». При добавлении producer/consumer/outbox в Go-сервис.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Kafka — проектирование (Go / net/http + chi)

Ты проектируешь работу с Kafka по **контракту** `backend/kafka/spec.md` (`R-KFK-*`) и **Go-реализации** `backend/kafka/references/go/implementation.md`.

## Инструкции

1. **Прочитай** требования `go-style/*`. Коды правил цитируй в design-обосновании, **не** в комментариях кода. Связанные: `backend/ddd-tactical/go/...` (событие как неизменяемая структура с конструктором), `backend/cqrs/...` (sync read-model через outbox), `backend/pg-runtime/...` (outbox-relay `FOR UPDATE SKIP LOCKED`), `backend/resilience/go/...` (CB для HTTP из consumer). Помни: в Go ошибки — значения; «retry» реализуется через `avast/retry-go`, CB — `sony/gobreaker`; DI — ручная конструкторная сборка.

2. **Идентифицируй сервис.** `git diff` или путь от пользователя. Структура UCP на Go:
   - `core/<bc>/event/` — событие-структура + конструктор.
   - `core/<bc>/` — UseCase handler; пишет в outbox через UoW-транзакцию.
   - `adapters/in/kafka/` — consumer горутина + idempotent handler.
   - `infra/kafka/` — `Writer`/`Reader` фабрики, outbox-relay, retry-relay, DLQ-relay.
   - `infra/config/` — `KafkaConfig` через `envconfig`.

3. **Producer** (`R-KFK-PROD-*`): `kafka.Writer` с `RequiredAcks: kafka.RequireAll`, `Balancer: &kafka.Hash{}`, `MaxAttempts: math.MaxInt32`; ключ сообщения = aggregate id (`[]byte(aggregateID)`), JSON (`encoding/json`). Domain-события — **через outbox**, не прямой `WriteMessages` из handler (`kafka/publish-via-outbox`).

4. **Outbox-relay** (`R-KFK-OBX-*`): запись в таблицу `outbox` в той же `pgx.Tx` (UoW-транзакции); отдельная горутина (`infra/kafka/outbox_relay.go`) читает `SELECT ... FOR UPDATE SKIP LOCKED`, batch 10–50, публикует через `kafka.Writer`, проставляет `published_at`; тик `200ms` через `time.NewTicker`. Partial-индекс `WHERE published_at IS NULL` — через `ucp-pg-schema-design`.

5. **Consumer** (`R-KFK-CONS-*`): `kafka.NewReader` с `CommitInterval: 0` (manual commit), `StartOffset: kafka.FirstOffset`, уникальный `GroupID: "<service>-<purpose>"`. Явный `reader.CommitMessages(ctx, msg)` **после** успешной обработки. Concurrency — N горутин на одном `GroupID`, N ≤ числу партиций.

6. **Idempotent consumer** (`R-KFK-IDEM-*`): `EventID` (UUID v7) в payload; таблица `processed_event` с PRIMARY KEY на `event_id`; `dedup.TryInsert` + бизнес-результат в одной `pgx.Tx`; для money — `EventID` + `Idempotency-Key` на downstream HTTP-вызовах.

7. **Retry + DLQ** (`R-KFK-RTRY-*`): retry-топики с возрастающим delay (например, `<topic>.retry.5s` → `<topic>.retry.30s` → `<topic>.dlq`); задержка реализуется через `time.After(delay)` **вне** poll-цикла основного consumer — каждый retry-топик обслуживается своей горутиной. Определение transient через `errors.As` по Integration-типу (`apperr.Kind`), не по строке. Счётчик попыток в `kafka.Header`. Max-attempts + DLQ + alert на размер DLQ.

8. **Event design** (`R-KFK-EVT-*`): имя — глагол прошедшего времени (`OrderConfirmed`); поля `EventID`, `OccurredAt`, `OrderID`, `EventType` + бизнес-поля; `int64` для денег (минорные единицы), не `float64`; без агрегата целиком и без PII. Структура в `core/<bc>/event/`; единственная точка создания — конструктор `NewXxxEvent(aggregate)`. Десериализация — статический реестр `map[string]func([]byte) (Event, error)`, не `reflect`.

9. **Config/Security/Observability** (`R-KFK-CFG/SEC/OBS-*`): `KafkaConfig` через `envconfig` — `Brokers`, `ClientID`, `Topics.*` с тегом `required:"true"`, TLS через `kafka.Dialer`; per-service `ClientID` для ACL; PII — restricted-топик или «слабая ссылка» (только `customer_id`). Метрики через `promauto`: `kafka_messages_produced_total`, `kafka_messages_consumed_total`, `kafka_processing_errors_total`. Tracing: `traceparent` в `kafka.Header` через OTel propagator (inject на producer, extract на consumer). Alert на consumer lag + DLQ-size.

10. **Самопроверка** — пройдись по чеклисту из `backend/kafka/references/go/implementation.md` §«Чеклист подключения к новому сервису (Go)». DDL outbox-таблицы — через `ucp-pg-schema-design`.

11. **Финальный шаг:** предложи «запусти `ucp-go-kafka-review` для верификации».

## Антипаттерны, которые НЕ генерировать

- `RequiredAcks: kafka.RequireNone` / `kafka.RequireOne` (`R-KFK-PROD-X1/X2`); `Key: nil` в `kafka.Message` для бизнес-событий (`kafka/partition-key-required`); `WriteMessages` из UseCase Handler с DB-операцией (`kafka/publish-via-outbox` / `kafka/publish-via-outbox`).
- `CommitInterval > 0` (авто-коммит) (`kafka/manual-offset-commit`); `time.Sleep` / тяжёлая блокировка >1s в poll-цикле без `ctx.Done()` (`kafka/listener-does-not-block-poll-loop`); HTTP из listener без CB (`kafka/listener-does-not-block-poll-loop`).
- Handler без проверки `event_id` при non-idempotent side-effects (`kafka/consumer-is-idempotent`); Kafka offset как dedup-ключ (`kafka/consumer-is-idempotent`).
- `time.Sleep` / retry **внутри** основной poll-горутины (`kafka/retry-topics-with-limits`); проглатывание ошибки + commit (`kafka/no-swallowing-in-listener`); retry-топик без счётчика попыток (`kafka/retry-topics-with-limits`); DLQ без мониторинга (`kafka/dlq-monitored-and-manually-replayed`).
- Имя-команда у события (`kafka/event-named-in-past-tense`); агрегат/Entity целиком в payload (`kafka/event-payload-hygiene`); PII в широковещательном топике (`kafka/event-payload-hygiene`); breaking change без версии (`kafka/event-schema-forward-compatible`).
- Динамический `reflect` по строке из payload (`kafka/deserialization-allow-list`); `Brokers: []string{"localhost:9092"}` хардкодом (`kafka/settings-are-typed-and-external`); `Dialer` без TLS в проде (`kafka/transport-security-and-acls`).

После работы скилла — обязательно `ucp-go-kafka-review`.

$ARGUMENTS
