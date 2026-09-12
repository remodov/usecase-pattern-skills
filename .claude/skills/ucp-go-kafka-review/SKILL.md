---
name: ucp-go-kafka-review
lang: go
description: Ревью Kafka в Go-сервисе (net/http + chi) по UCP — kafka.Writer acks/key, kafka.Reader manual commit и идемпотентность через processed_event, outbox-relay с pgx.Tx, retry-горутины + DLQ, envconfig-конфиг, TLS-dialer, OTel traceparent.
when_to_use: Изменения в infra/kafka/*.go, adapters/in/kafka/*.go, adapters/out/kafka/*.go, core/*/event/*.go, outbox-relay, KafkaConfig или DLQ-конфигурации.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Kafka (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/kafka/spec.md` (`R-KFK-*`)
и его **Go-реализации** `backend/kafka/references/go/implementation.md`.
Помни парадигму: в Go ошибки — **значения**, а не исключения; `isTransient(err)` — через `errors.As`
по типу, не по строке; DI — конструкторная сборка в `main`/`wire`; consumer — goroutine-per-reader с явным
`CommitMessages` после обработки.

## Зависимости

- **`.claude/docs/backend/kafka/spec.md`** — общий контракт (`R-KFK-PROD-*`/`CONS-*`/`OBX-*`/`IDEM-*`/`RTRY-*`/`EVT-*`/`CFG-*`/`OBS-*`/`SEC-*`).
- **`.claude/docs/backend/kafka/references/go/implementation.md`** — Go-реализация (`segmentio/kafka-go`, `kafka.Writer`/`Reader`, `pgx.Tx`, `promauto`, OTel propagator, `envconfig`).
- Парные: `backend/ddd-tactical/go/...` (событие как Go-структура), `backend/cqrs/...` (outbox sync), `backend/pg-runtime/...` (`FOR UPDATE SKIP LOCKED`), `backend/resilience/go/...` (CB в consumer через `gobreaker`).

## Инструкции

1. **Прочти** общий контракт (`kafka/spec.md`) + требования `go-style/*`. Цитируй конкретные коды (`kafka/manual-offset-commit`, `kafka/publish-via-outbox`), не только префикс.

2. **Скоп.** Producer/consumer-код (`segmentio/kafka-go`), `KafkaConfig`, outbox-relay, `processed_event`, event-структуры в `core/<bc>/event/`; `git diff` на изменённые `.go`.
   **`Grep`**: `RequiredAcks: kafka.RequireNone`, `CommitInterval:` (ненулевой), `Key: nil`, `time.Sleep` внутри `Run`-горутины, `_ = ` (проглоченный err), `reflect.New(` по строке из payload.

3. **Прогон.**

   ### `R-KFK-PROD-*`
   - `kafka.Writer` с `RequiredAcks: kafka.RequireAll` + `MaxAttempts: math.MaxInt32`? Иначе — `kafka/producer-is-idempotent`/`X2`.
   - `Balancer: &kafka.Hash{}` и `Key: []byte(aggregateID)` в `kafka.Message`? Нет ключа → `kafka/partition-key-required`; `RoundRobin` для бизнес-событий → `kafka/producer-is-idempotent`.
   - `writer.WriteMessages` **не** вызывается из UseCase Handler напрямую? Вызов из Handler → `kafka/publish-via-outbox`.

   ### `R-KFK-CONS-*`
   - `CommitInterval: 0` (manual commit) в `kafka.ReaderConfig`? `CommitInterval > 0` → `kafka/manual-offset-commit`.
   - `reader.CommitMessages(ctx, msg)` вызывается **после** успешной обработки? Commit до обработки → `kafka/manual-offset-commit`.
   - `GroupID: "<service>-<purpose>"` — уникальный, не общий? Отсутствие или общий → `kafka/consumer-group-per-purpose`.
   - `StartOffset: kafka.FirstOffset` для critical-consumer'ов? — `kafka/earliest-offset-for-critical-consumers`.
   - Нет `time.Sleep` / тяжёлой блокировки >1s в теле горутины без проверки `ctx.Done()`? Есть → `kafka/listener-does-not-block-poll-loop`.
   - HTTP-вызов к внешней системе из listener обёрнут `gobreaker`? Без CB → `kafka/listener-does-not-block-poll-loop`.

   ### `R-KFK-OBX-*`
   - Domain-событие пишется в таблицу `outbox` **в той же `pgx.Tx`** с бизнес-операцией? Прямой `WriteMessages` из Handler → `kafka/publish-via-outbox`; publish сразу после `tx.Commit` без outbox → `kafka/publish-via-outbox`.
   - Outbox-relay — отдельная горутина с ticker + `FOR UPDATE SKIP LOCKED` + batch 10–50 + `MarkPublished`? — `R-KFK-OBX-2/4`.
   - Таблица outbox содержит `published_at` + partial-индекс `WHERE published_at IS NULL`? Нет → `kafka/outbox-table-shape`.
   - Topic выводится из `event_type` через явный маппинг, не строковые операции на лету? — `kafka/outbox-relay-reads-in-batches`.

   ### `R-KFK-IDEM-*`
   - `processed_event` с PRIMARY KEY на `event_id`; вставка и бизнес-результат в одной `pgx.Tx`? — `R-KFK-IDEM-2/3`.
   - Handler проверяет `event_id` через `dedup.TryInsert` до обработки? Нет проверки при потенциальном дубле → `kafka/consumer-is-idempotent`.
   - Не используется Kafka offset как dedup-ключ? Offset → `kafka/consumer-is-idempotent`.
   - Money-операции защищены `event_id` + `Idempotency-Key` на downstream HTTP? — `kafka/money-operations-double-protected`.

   ### `R-KFK-RTRY-*`
   - Retry через отдельные retry-топики (горутины с `time.After(delay)` **вне** poll-цикла)? `time.Sleep` в основной горутине → `kafka/retry-topics-with-limits`.
   - Retry только для transient-ошибок (`isTransient(err)` через `errors.As` по `*GatewayError` / Integration-типу)? Retry на Domain-ошибках → `kafka/retry-only-transient-failures`.
   - Есть счётчик `attempts` в headers; превышение max → DLQ? Нет лимита → `kafka/retry-topics-with-limits`.
   - Poison pill (parse error) → сразу в DLQ, не в retry? Проглатывание с commit → `kafka/no-swallowing-in-listener`.
   - Alert на размер DLQ (`kafka_dlq_messages_total`)? Нет → `kafka/dlq-monitored-and-manually-replayed`.

   ### `R-KFK-EVT-*`
   - Имя события — глагол прошедшего времени (`OrderConfirmed`, `PaymentFailed`)? Команда-форма → `kafka/event-named-in-past-tense`.
   - Payload содержит `EventID` (UUID v7), `OccurredAt`, `AggregateID`, `EventType`, money — `int64`? Нет — `kafka/event-payload-hygiene`.
   - PII (email, phone, адрес) отсутствует в широковещательных топиках? Есть → `kafka/event-payload-hygiene`.
   - Breaking change поля → новый версионный суффикс в `EventType` (`"OrderConfirmed.v2"`)? Нет версии → `kafka/event-schema-forward-compatible`.
   - Событие — неизменяемая Go-структура в `core/<bc>/event/` с конструктором `New*`? — `kafka/event-payload-hygiene`.

   ### `R-KFK-CFG-*`
   - `KafkaConfig` через `envconfig` с `required:"true"` на `Brokers`, `ClientID`, `Topics.*`? Хардкод `"localhost:9092"` → `kafka/settings-are-typed-and-external`.
   - Десериализация через статический реестр `map[string]func([]byte) (Event, error)`? Динамический `reflect.New(registry[typeName])` → `kafka/deserialization-allow-list` (RCE-риск).
   - Проверка существования топиков на старте (`ReadPartitions`); отсутствие → `log.Fatal`? — `kafka/missing-topics-are-fatal`.
   - `RequiredAcks: kafka.RequireAll`, `CommitInterval: 0`, `MaxAttempts` — явно в конфигурационном коде, не «магией» по всему проекту? — `kafka/settings-are-typed-and-external`.

   ### `R-KFK-SEC-*` / `R-KFK-OBS-*`
   - TLS через `kafka.Dialer{TLS: tlsCfg}` в проде? Plaintext → `kafka/transport-security-and-acls`.
   - `ClientID` — per-service (`KafkaConfig.ClientID`)? Общий → `kafka/transport-security-and-acls`.
   - PII — restricted-топик или «слабая ссылка» (только `customer_id`)? PII в широком топике → `kafka/event-payload-hygiene` + `kafka/event-payload-hygiene`.
   - `kafka_messages_produced_total`, `kafka_messages_consumed_total`, `kafka_processing_errors_total` (`promauto.CounterVec`)? — `kafka/consumer-lag-alerting`.
   - `traceparent` inject/extract через OTel propagator (`propagation.MapCarrier`) в headers? — `kafka/trace-context-in-headers`.
   - Alert на consumer lag + DLQ-size (Prometheus AlertManager)? Нет → `kafka/consumer-lag-alerting`.

4. **Cross-check:** событие как Go-структура в `core/<bc>/event/` → `ucp-go-ddd-tactical-review`; outbox-таблица/`SKIP LOCKED` → `ucp-pg-runtime-review`; CB (`gobreaker`) для HTTP из consumer → `ucp-go-resilience-review`; CQRS read-model sync → `ucp-go-cqrs-review`. Рекомендуй `errcheck`+`errorlint` в линтере, если их нет.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `writer.WriteMessages` из UseCase Handler (`kafka/publish-via-outbox`); `CommitInterval > 0` / commit до обработки (`kafka/manual-offset-commit`); publish сразу после `tx.Commit` без outbox (`kafka/publish-via-outbox`); `WriteMessages` из той же TX с DB (`kafka/publish-via-outbox`); нет проверки `event_id` при потенциальном дубле (`kafka/consumer-is-idempotent`); проглатывание ошибки + commit (`kafka/no-swallowing-in-listener`); динамический `reflect` по строке из payload (`kafka/deserialization-allow-list`); plaintext в проде (`kafka/transport-security-and-acls`).
   - **Предупреждение** — `RequiredAcks` не `RequireAll` (`R-KFK-PROD-X1/X2`); `Key: nil` для бизнес-событий (`kafka/partition-key-required`); `time.Sleep` в poll-цикле (`kafka/retry-topics-with-limits`); retry без лимита попыток (`kafka/retry-topics-with-limits`); PII в широком топике (`kafka/event-payload-hygiene`); нет consumer-lag alert (`kafka/consumer-lag-alerting`); нет DLQ alert (`kafka/dlq-monitored-and-manually-replayed`).
   - **Замечание** — имя события — команда (`kafka/event-named-in-past-tense`); нет версии при breaking change (`kafka/event-schema-forward-compatible`); общий `ClientID` (`kafka/transport-security-and-acls`); нет `traceparent` в headers (`kafka/trace-context-in-headers`); хардкод brokers (`kafka/settings-are-typed-and-external`).

## Что не входит

- Событие как Go-структура и конструктор → `ucp-go-ddd-tactical-review`.
- Outbox DDL, `FOR UPDATE SKIP LOCKED` → `ucp-pg-runtime-review`.
- CB/bulkhead конфигурация (`gobreaker`) → `ucp-go-resilience-review`.
- CQRS read-model sync → `ucp-go-cqrs-review`.
- PII в логах → `ucp-go-observability-review` / `ucp-auth-review`.

$ARGUMENTS
