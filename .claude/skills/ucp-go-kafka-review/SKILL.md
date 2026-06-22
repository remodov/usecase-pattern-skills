---
name: ucp-go-kafka-review
lang: go
description: Ревью Kafka в Go-сервисе (net/http + chi) по UCP (коды R-KFK-*) — kafka.Writer acks/key, kafka.Reader manual commit и идемпотентность через processed_event, outbox-relay с pgx.Tx, retry-горутины + DLQ, envconfig-конфиг, TLS-dialer, OTel traceparent.
when_to_use: Изменения в infra/kafka/*.go, adapters/in/kafka/*.go, adapters/out/kafka/*.go, core/*/event/*.go, outbox-relay, KafkaConfig или DLQ-конфигурации.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Kafka (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/kafka/kafka-rules.md` (`R-KFK-*`)
и его **Go-реализации** `backend/kafka/go/kafka-style-guide.md`.
Помни парадигму: в Go ошибки — **значения**, а не исключения; `isTransient(err)` — через `errors.As`
по типу, не по строке; DI — конструкторная сборка в `main`/`wire`; consumer — goroutine-per-reader с явным
`CommitMessages` после обработки.

## Зависимости

- **`.claude/docs/backend/kafka/kafka-rules.md`** — общий контракт (`R-KFK-PROD-*`/`CONS-*`/`OBX-*`/`IDEM-*`/`RTRY-*`/`EVT-*`/`CFG-*`/`OBS-*`/`SEC-*`).
- **`.claude/docs/backend/kafka/go/kafka-style-guide.md`** — Go-реализация (`segmentio/kafka-go`, `kafka.Writer`/`Reader`, `pgx.Tx`, `promauto`, OTel propagator, `envconfig`).
- Парные: `backend/ddd-tactical/go/...` (событие как Go-структура), `backend/cqrs/...` (outbox sync), `backend/pg-runtime/...` (`FOR UPDATE SKIP LOCKED`), `backend/resilience/go/...` (CB в consumer через `gobreaker`).

## Инструкции

1. **Прочти** общий контракт (`kafka-rules.md`) + Go style-guide. Цитируй конкретные коды (`R-KFK-CONS-X1`, `R-KFK-OBX-X1`), не только префикс.

2. **Скоп.** Producer/consumer-код (`segmentio/kafka-go`), `KafkaConfig`, outbox-relay, `processed_event`, event-структуры в `core/<bc>/event/`; `git diff` на изменённые `.go`.
   **`Grep`**: `RequiredAcks: kafka.RequireNone`, `CommitInterval:` (ненулевой), `Key: nil`, `time.Sleep` внутри `Run`-горутины, `_ = ` (проглоченный err), `reflect.New(` по строке из payload.

3. **Прогон.**

   ### `R-KFK-PROD-*`
   - `kafka.Writer` с `RequiredAcks: kafka.RequireAll` + `MaxAttempts: math.MaxInt32`? Иначе — `R-KFK-PROD-X1`/`X2`.
   - `Balancer: &kafka.Hash{}` и `Key: []byte(aggregateID)` в `kafka.Message`? Нет ключа → `R-KFK-PROD-X3`; `RoundRobin` для бизнес-событий → `R-KFK-PROD-X2`.
   - `writer.WriteMessages` **не** вызывается из UseCase Handler напрямую? Вызов из Handler → `R-KFK-PROD-X4`.

   ### `R-KFK-CONS-*`
   - `CommitInterval: 0` (manual commit) в `kafka.ReaderConfig`? `CommitInterval > 0` → `R-KFK-CONS-X1`.
   - `reader.CommitMessages(ctx, msg)` вызывается **после** успешной обработки? Commit до обработки → `R-KFK-CONS-X1`.
   - `GroupID: "<service>-<purpose>"` — уникальный, не общий? Отсутствие или общий → `R-KFK-CONS-X3`.
   - `StartOffset: kafka.FirstOffset` для critical-consumer'ов? — `R-KFK-CONS-4`.
   - Нет `time.Sleep` / тяжёлой блокировки >1s в теле горутины без проверки `ctx.Done()`? Есть → `R-KFK-CONS-X2`.
   - HTTP-вызов к внешней системе из listener обёрнут `gobreaker`? Без CB → `R-KFK-CONS-X4`.

   ### `R-KFK-OBX-*`
   - Domain-событие пишется в таблицу `outbox` **в той же `pgx.Tx`** с бизнес-операцией? Прямой `WriteMessages` из Handler → `R-KFK-OBX-X1`; publish сразу после `tx.Commit` без outbox → `R-KFK-OBX-X2`.
   - Outbox-relay — отдельная горутина с ticker + `FOR UPDATE SKIP LOCKED` + batch 10–50 + `MarkPublished`? — `R-KFK-OBX-2/4`.
   - Таблица outbox содержит `published_at` + partial-индекс `WHERE published_at IS NULL`? Нет → `R-KFK-OBX-X3`.
   - Topic выводится из `event_type` через явный маппинг, не строковые операции на лету? — `R-KFK-OBX-3`.

   ### `R-KFK-IDEM-*`
   - `processed_event` с PRIMARY KEY на `event_id`; вставка и бизнес-результат в одной `pgx.Tx`? — `R-KFK-IDEM-2/3`.
   - Handler проверяет `event_id` через `dedup.TryInsert` до обработки? Нет проверки при потенциальном дубле → `R-KFK-IDEM-X1`.
   - Не используется Kafka offset как dedup-ключ? Offset → `R-KFK-IDEM-X2`.
   - Money-операции защищены `event_id` + `Idempotency-Key` на downstream HTTP? — `R-KFK-IDEM-4`.

   ### `R-KFK-RTRY-*`
   - Retry через отдельные retry-топики (горутины с `time.After(delay)` **вне** poll-цикла)? `time.Sleep` в основной горутине → `R-KFK-RTRY-X1`.
   - Retry только для transient-ошибок (`isTransient(err)` через `errors.As` по `*GatewayError` / Integration-типу)? Retry на Domain-ошибках → `R-KFK-RTRY-2`.
   - Есть счётчик `attempts` в headers; превышение max → DLQ? Нет лимита → `R-KFK-RTRY-X3`.
   - Poison pill (parse error) → сразу в DLQ, не в retry? Проглатывание с commit → `R-KFK-RTRY-X2`.
   - Alert на размер DLQ (`kafka_dlq_messages_total`)? Нет → `R-KFK-RTRY-X4`.

   ### `R-KFK-EVT-*`
   - Имя события — глагол прошедшего времени (`OrderConfirmed`, `PaymentFailed`)? Команда-форма → `R-KFK-EVT-X1`.
   - Payload содержит `EventID` (UUID v7), `OccurredAt`, `AggregateID`, `EventType`, money — `int64`? Нет — `R-KFK-EVT-X2`.
   - PII (email, phone, адрес) отсутствует в широковещательных топиках? Есть → `R-KFK-EVT-X3`.
   - Breaking change поля → новый версионный суффикс в `EventType` (`"OrderConfirmed.v2"`)? Нет версии → `R-KFK-EVT-X4`.
   - Событие — неизменяемая Go-структура в `core/<bc>/event/` с конструктором `New*`? — `R-KFK-EVT-4`.

   ### `R-KFK-CFG-*`
   - `KafkaConfig` через `envconfig` с `required:"true"` на `Brokers`, `ClientID`, `Topics.*`? Хардкод `"localhost:9092"` → `R-KFK-CFG-X2`.
   - Десериализация через статический реестр `map[string]func([]byte) (Event, error)`? Динамический `reflect.New(registry[typeName])` → `R-KFK-CFG-X1` (RCE-риск).
   - Проверка существования топиков на старте (`ReadPartitions`); отсутствие → `log.Fatal`? — `R-KFK-CFG-4`.
   - `RequiredAcks: kafka.RequireAll`, `CommitInterval: 0`, `MaxAttempts` — явно в конфигурационном коде, не «магией» по всему проекту? — `R-KFK-CFG-2`.

   ### `R-KFK-SEC-*` / `R-KFK-OBS-*`
   - TLS через `kafka.Dialer{TLS: tlsCfg}` в проде? Plaintext → `R-KFK-SEC-X1`.
   - `ClientID` — per-service (`KafkaConfig.ClientID`)? Общий → `R-KFK-SEC-X2`.
   - PII — restricted-топик или «слабая ссылка» (только `customer_id`)? PII в широком топике → `R-KFK-EVT-X3` + `R-KFK-SEC-3`.
   - `kafka_messages_produced_total`, `kafka_messages_consumed_total`, `kafka_processing_errors_total` (`promauto.CounterVec`)? — `R-KFK-OBS-1`.
   - `traceparent` inject/extract через OTel propagator (`propagation.MapCarrier`) в headers? — `R-KFK-OBS-3`.
   - Alert на consumer lag + DLQ-size (Prometheus AlertManager)? Нет → `R-KFK-OBS-X1`.

4. **Cross-check:** событие как Go-структура в `core/<bc>/event/` → `ucp-go-ddd-tactical-review`; outbox-таблица/`SKIP LOCKED` → `ucp-pg-runtime-review`; CB (`gobreaker`) для HTTP из consumer → `ucp-go-resilience-review`; CQRS read-model sync → `ucp-go-cqrs-review`. Рекомендуй `errcheck`+`errorlint` в линтере, если их нет.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `writer.WriteMessages` из UseCase Handler (`R-KFK-PROD-X4`); `CommitInterval > 0` / commit до обработки (`R-KFK-CONS-X1`); publish сразу после `tx.Commit` без outbox (`R-KFK-OBX-X2`); `WriteMessages` из той же TX с DB (`R-KFK-OBX-X1`); нет проверки `event_id` при потенциальном дубле (`R-KFK-IDEM-X1`); проглатывание ошибки + commit (`R-KFK-RTRY-X2`); динамический `reflect` по строке из payload (`R-KFK-CFG-X1`); plaintext в проде (`R-KFK-SEC-X1`).
   - **Предупреждение** — `RequiredAcks` не `RequireAll` (`R-KFK-PROD-X1/X2`); `Key: nil` для бизнес-событий (`R-KFK-PROD-X3`); `time.Sleep` в poll-цикле (`R-KFK-RTRY-X1`); retry без лимита попыток (`R-KFK-RTRY-X3`); PII в широком топике (`R-KFK-EVT-X3`); нет consumer-lag alert (`R-KFK-OBS-X1`); нет DLQ alert (`R-KFK-RTRY-X4`).
   - **Замечание** — имя события — команда (`R-KFK-EVT-X1`); нет версии при breaking change (`R-KFK-EVT-X4`); общий `ClientID` (`R-KFK-SEC-X2`); нет `traceparent` в headers (`R-KFK-OBS-3`); хардкод brokers (`R-KFK-CFG-X2`).

## Что не входит

- Событие как Go-структура и конструктор → `ucp-go-ddd-tactical-review`.
- Outbox DDL, `FOR UPDATE SKIP LOCKED` → `ucp-pg-runtime-review`.
- CB/bulkhead конфигурация (`gobreaker`) → `ucp-go-resilience-review`.
- CQRS read-model sync → `ucp-go-cqrs-review`.
- PII в логах → `ucp-go-observability-review` / `ucp-auth-review`.

$ARGUMENTS
