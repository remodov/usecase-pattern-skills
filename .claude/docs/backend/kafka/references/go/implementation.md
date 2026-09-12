# Kafka — реализация на Go (net/http + chi)

Реализация контракта `../spec.md` (коды `R-KFK-PROD-*`, `R-KFK-CONS-*`, `R-KFK-OBX-*`, `R-KFK-IDEM-*`,
`R-KFK-RTRY-*`, `R-KFK-EVT-*`, `R-KFK-CFG-*`, `R-KFK-OBS-*`, `R-KFK-SEC-*`) на Go-стеке
(**github.com/segmentio/kafka-go**). Коды правил общие с Java/Python; меняется клиент, семантика одна.

> **Стек.** Kafka-клиент — `segmentio/kafka-go` (синхронный `Writer`/`Reader`, goroutine-per-consumer идиома).
> Ошибки — значения (`apperr.Kind`, `errors.As`, `%w`) — как в `error-handling/go/`. Producer и consumer
> регистрируют метрики через `promauto`; tracing — `go.opentelemetry.io/otel`. DI — ручная конструкторная
> сборка. Конфиг — `github.com/kelseyhightower/envconfig` (`KafkaConfig`-структура).

---

## 1. Producer (`R-KFK-PROD-*`)

`kafka/producer-is-idempotent` — идемпотентный producer. В `kafka-go` это `kafka.Writer` с явными настройками:

```go
// infra/kafka/writer.go
func NewOrderWriter(cfg KafkaConfig) *kafka.Writer {
    return &kafka.Writer{
        Addr:         kafka.TCP(cfg.Brokers...),
        Topic:        cfg.Topics.OrdersConfirmed,
        Balancer:     &kafka.Hash{},          // партиционирование по ключу
        RequiredAcks: kafka.RequireAll,        // R-KFK-PROD-1/X2: acks=all
        MaxAttempts:  math.MaxInt32,           // R-KFK-PROD-1: retries≈∞
    }
}
```

`kafka-go` не имеет флага `enable.idempotence` — `RequireAll` + `MaxAttempts` дают эквивалентную семантику
для порядка доставки. При необходимости точного exactly-once — `kafka.WriterConfig.RequiredAcks: RequireAll`
достаточно для at-least-once с ordering per-partition; stronger exactly-once требует Kafka-транзакции
(см. `kafka.Writer` + `Transactions`-флаг, IMPL-SHAPED).

`kafka/partition-key-required` — partition key обязателен для бизнес-событий = aggregate id:

```go
func (p *OrderEventProducer) Publish(ctx context.Context, evt OrderConfirmed) error {
    msg := kafka.Message{
        Key:   []byte(evt.OrderID),           // R-KFK-PROD-2: ключ = aggregate id
        Value: mustMarshal(evt),              // R-KFK-PROD-3: JSON
    }
    if err := p.writer.WriteMessages(ctx, msg); err != nil {
        return fmt.Errorf("publish OrderConfirmed %s: %w", evt.OrderID, err)
    }
    return nil
}
```

`kafka/serialization-format` — JSON-сериализация (`encoding/json`), ключ — `[]byte(aggregateID)`. Для bandwidth-топиков —
Protobuf/Avro через Schema Registry (отдельная инфра).

`kafka/publish-via-outbox` — domain-события **не** публикуются прямым вызовом `writer.WriteMessages` из UseCase Handler —
только через outbox-relay (`R-KFK-OBX-*`).

**AVOID:**

`kafka/producer-is-idempotent` ❌ `RequiredAcks: kafka.RequireNone` или `kafka.RequireOne` в проде.

`kafka/producer-is-idempotent` ❌ `Balancer: &kafka.RoundRobin{}` для бизнес-событий — теряется ordering per-aggregate.

`kafka/partition-key-required` ❌ `Key: nil` в `kafka.Message` для business-events.

`kafka/publish-via-outbox` ❌ `writer.WriteMessages(ctx, msg)` из той же транзакции, что DB-операция — Kafka не XA;
rollback БД не откатит публикацию. Используй outbox.

---

## 2. Consumer (`R-KFK-CONS-*`)

`kafka/consumer-group-per-purpose` — уникальный `GroupID` в формате `<service>-<purpose>`:

```go
// infra/kafka/reader.go
func NewOrderConfirmedReader(cfg KafkaConfig) *kafka.Reader {
    return kafka.NewReader(kafka.ReaderConfig{
        Brokers:        cfg.Brokers,
        Topic:          cfg.Topics.OrdersConfirmed,
        GroupID:        "billing-order-confirmed",    // R-KFK-CONS-1: <service>-<purpose>
        MinBytes:       1,
        MaxBytes:       10 << 20,
        CommitInterval: 0,                            // R-KFK-CONS-2: manual commit (0 = disable auto)
        StartOffset:    kafka.FirstOffset,            // R-KFK-CONS-4: earliest
    })
}
```

`kafka/manual-offset-commit` — manual commit: `kafka.ReaderConfig.CommitInterval = 0`; явный `reader.CommitMessages(ctx, msg)`
**после** успешной обработки.

`kafka/consumer-is-idempotent` — listener-горутина обязана быть идемпотентной (`R-KFK-IDEM-*`).

`kafka/earliest-offset-for-critical-consumers` — `StartOffset: kafka.FirstOffset` для critical-consumer'ов.

`kafka/concurrency-and-poll-interval` — concurrency через N горутин-reader'ов на одном `GroupID`; их количество ≤ числу партиций.

```go
// adapters/in/kafka/order_confirmed_consumer.go
type OrderConfirmedConsumer struct {
    reader  *kafka.Reader
    handler *OrderConfirmedHandler
}

func (c *OrderConfirmedConsumer) Run(ctx context.Context) error {
    for {
        msg, err := c.reader.FetchMessage(ctx)
        if err != nil {
            if errors.Is(err, context.Canceled) {
                return nil
            }
            return fmt.Errorf("fetch OrderConfirmed: %w", err)
        }

        var evt OrderConfirmedEvent
        if err := json.Unmarshal(msg.Value, &evt); err != nil {
            // poison pill — сразу в DLQ (R-KFK-RTRY-2)
            c.sendToDLQ(ctx, msg, err)
            _ = c.reader.CommitMessages(ctx, msg)
            continue
        }

        if err := c.handler.Handle(ctx, evt); err != nil {
            if isTransient(err) {
                c.sendToRetry(ctx, msg)     // R-KFK-RTRY-1
            } else {
                c.sendToDLQ(ctx, msg, err)  // R-KFK-RTRY-2: poison → DLQ
            }
        }
        if err := c.reader.CommitMessages(ctx, msg); err != nil {
            return fmt.Errorf("commit OrderConfirmed: %w", err)
        }
    }
}
```

`kafka/concurrency-and-poll-interval` — `MaxWait` и таймаут контекста должны учитывать время обработки; не допускать блокировки >1s без
передачи управления (`ctx.Done()`).

**AVOID:**

`kafka/manual-offset-commit` ❌ `CommitInterval > 0` (авто-коммит) в проде.

`kafka/listener-does-not-block-poll-loop` ❌ `time.Sleep` / тяжёлая CPU-блокировка >1s в теле горутины без проверки `ctx.Done()`.

`kafka/consumer-group-per-purpose` ❌ `GroupID: ""` или общий `GroupID` на несколько consumer-горутин с разными ролями.

`kafka/listener-does-not-block-poll-loop` ❌ HTTP-вызов к внешней системе из listener без CB/bulkhead.

---

## 3. Outbox publishing (`R-KFK-OBX-*`)

`kafka/publish-via-outbox` — domain-событие пишется в таблицу `outbox` в той же DB-транзакции (UoW), не через `WriteMessages`
из UseCase Handler:

```go
// core/order/handler.go
func (h *ConfirmOrderHandler) Handle(ctx context.Context, cmd ConfirmOrderCommand) error {
    tx, err := h.db.Begin(ctx)
    if err != nil { return fmt.Errorf("begin: %w", err) }
    defer tx.Rollback(ctx)

    order, err := h.orders.GetForUpdate(ctx, tx, cmd.OrderID)
    if err != nil { return err }
    order.Confirm()

    if err := h.orders.Save(ctx, tx, order); err != nil { return err }

    // outbox-запись в той же транзакции
    if err := h.outbox.Store(ctx, tx, OutboxEvent{
        AggregateID: order.ID,
        EventType:   "OrderConfirmed",
        Payload:     mustMarshal(NewOrderConfirmedEvent(order)),
    }); err != nil {
        return fmt.Errorf("outbox store: %w", err)
    }

    return tx.Commit(ctx)
}
```

`kafka/outbox-relay-reads-in-batches` — outbox-relay — отдельная горутина (запускается в `main` наряду с HTTP-сервером), читает
`SELECT ... FOR UPDATE SKIP LOCKED`, публикует через `kafka.Writer`, проставляет `published_at`:

```go
// infra/kafka/outbox_relay.go
func (r *OutboxRelay) Run(ctx context.Context) {
    ticker := time.NewTicker(200 * time.Millisecond)
    defer ticker.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            if err := r.processBatch(ctx); err != nil {
                slog.ErrorContext(ctx, "outbox relay error", "error", err)
            }
        }
    }
}

func (r *OutboxRelay) processBatch(ctx context.Context) error {
    events, err := r.repo.FetchUnpublished(ctx, 50) // R-KFK-OBX-4: batch 10–50
    if err != nil {
        return fmt.Errorf("fetch unpublished: %w", err)
    }
    for _, e := range events {
        msg := kafka.Message{
            Topic: topicFor(e.EventType),             // R-KFK-OBX-3
            Key:   []byte(e.AggregateID),
            Value: e.Payload,
        }
        if err := r.writer.WriteMessages(ctx, msg); err != nil {
            return fmt.Errorf("publish %s %s: %w", e.EventType, e.ID, err)
        }
        if err := r.repo.MarkPublished(ctx, e.ID); err != nil {
            return fmt.Errorf("mark published %s: %w", e.ID, err)
        }
    }
    return nil
}
```

`kafka/outbox-relay-reads-in-batches` — topic выводится из `event_type` / `aggregate_type` через маппинг-таблицу (не строковые операции
на лету).

`kafka/outbox-relay-reads-in-batches` — batch 10–50 событий за тик.

**AVOID:**

`kafka/publish-via-outbox` ❌ `writer.WriteMessages` из UseCase Handler совместно с DB-операцией.

`kafka/publish-via-outbox` ❌ публикация сразу после `tx.Commit` без outbox — падение между commit и publish потеряет событие.

`kafka/outbox-table-shape` ❌ таблица outbox без колонки `published_at` / без partial-индекса `WHERE published_at IS NULL`.

---

## 4. Idempotent consumer (`R-KFK-IDEM-*`)

`kafka/consumer-is-idempotent` — каждое событие содержит уникальный `EventID` (UUID v7) в payload; consumer проверяет
`processed_event` до обработки:

```go
// adapters/in/kafka/order_confirmed_handler.go
func (h *OrderConfirmedHandler) Handle(ctx context.Context, evt OrderConfirmedEvent) error {
    tx, err := h.db.Begin(ctx)
    if err != nil { return fmt.Errorf("begin: %w", err) }
    defer tx.Rollback(ctx)

    // R-KFK-IDEM-1/2/3: dedup + бизнес-результат в одной транзакции
    inserted, err := h.dedup.TryInsert(ctx, tx, evt.EventID)
    if err != nil { return fmt.Errorf("dedup: %w", err) }
    if !inserted {
        return nil // уже обработано
    }

    if err := h.billing.ApplyOrderConfirmed(ctx, tx, evt); err != nil {
        return err
    }
    return tx.Commit(ctx)
}
```

`kafka/processed-record-in-same-transaction` — таблица `processed_event` с PRIMARY KEY на `event_id`; TTL — через фоновый job или
partition-drop.

`kafka/processed-record-in-same-transaction` — запись в `processed_event` и бизнес-результат — в одной транзакции (`pgx.Tx`).

`kafka/money-operations-double-protected` — для money-операций двойная защита: `EventID` + `Idempotency-Key` на downstream HTTP-вызовах.

**AVOID:**

`kafka/consumer-is-idempotent` ❌ handler без проверки `event_id` когда дубль приводит к проблеме (двойное списание, дублированный заказ).

`kafka/consumer-is-idempotent` ❌ Kafka offset как dedup-ключ — при новом `GroupID` все события «впервые».

---

## 5. Retry topic + DLQ (`R-KFK-RTRY-*`)

`kafka/retry-topics-with-limits` — retry-топики с возрастающим delay через отдельные топики и goroutine-relay с `time.Sleep`
**вне** poll-цикла основного consumer'а:

```go
// Топики: orders.confirmed.retry.5s → orders.confirmed.retry.30s → orders.confirmed.dlq
// Каждый retry-топик обслуживается своей горутиной с задержкой перед обработкой.

func (r *RetryRelay) processWithDelay(ctx context.Context, delay time.Duration) {
    for {
        msg, err := r.reader.FetchMessage(ctx)
        if err != nil { return }

        select {
        case <-ctx.Done():
            return
        case <-time.After(delay): // задержка ВНЕ poll-цикла (R-KFK-RTRY-X1)
        }

        attempts := parseAttempts(msg.Headers) + 1
        if attempts > r.maxAttempts {           // R-KFK-RTRY-X3: лимит попыток
            r.dlqWriter.WriteMessages(ctx, toDLQ(msg))
            r.reader.CommitMessages(ctx, msg)
            continue
        }

        if err := r.handler.Handle(ctx, msg); err != nil {
            r.nextRetryWriter.WriteMessages(ctx, withAttempts(msg, attempts))
        }
        r.reader.CommitMessages(ctx, msg)
    }
}
```

`kafka/retry-only-transient-failures` — retry только для transient failures (timeout, 5xx, брокер недоступен); `isTransient(err)` —
через `errors.As` по типу ошибки (не строке):

```go
func isTransient(err error) bool {
    var ge *GatewayError
    return errors.As(err, &ge) // Integration-категория = transient
}
```

`kafka/dlq-monitored-and-manually-replayed` — alert на размер DLQ за час (Prometheus + AlertManager правило).

`kafka/dlq-monitored-and-manually-replayed` — replay из DLQ — отдельная admin-команда (HTTP endpoint за auth), не автоматика.

**AVOID:**

`kafka/retry-topics-with-limits` ❌ `time.Sleep` / retry внутри `Run`-горутины основного consumer — блокирует poll-цикл → rebalance.

`kafka/no-swallowing-in-listener` ❌ проглатывание: `if err != nil { slog.Error(...); /* commit */ }` — событие потеряно.

`kafka/retry-topics-with-limits` ❌ retry-топик без счётчика попыток (бесконечный lock-step с проблемной системой).

`kafka/dlq-monitored-and-manually-replayed` ❌ DLQ без monitoring (alert на `kafka_consumer_lag` или Prometheus counter).

---

## 6. Event design (`R-KFK-EVT-*`)

`kafka/event-named-in-past-tense` — имя события — глагол в прошедшем времени: `OrderConfirmed`, `PaymentFailed`, `CustomerRegistered`.

`kafka/event-payload-hygiene` — payload содержит `EventID`, `OccurredAt`, `AggregateID`, версию, бизнес-поля:

```go
// core/order/event/order_confirmed.go
type OrderConfirmedEvent struct {
    EventID     string    `json:"event_id"`      // UUID v7
    OccurredAt  time.Time `json:"occurred_at"`
    OrderID     string    `json:"order_id"`      // aggregate id
    CustomerID  string    `json:"customer_id"`
    TotalAmount int64     `json:"total_amount"`  // минорные единицы (int64), не float64
    EventType   string    `json:"event_type"`    // "OrderConfirmed"
}
```

`kafka/event-schema-forward-compatible` — forward-compatible schema: добавление полей non-breaking; удаление/переименование поля →
новый `event_type` = `"OrderConfirmed.v2"`. Consumer использует `json:",omitempty"` + значения по умолчанию
для новых полей при десериализации старых сообщений.

`kafka/event-payload-hygiene` — событие как неизменяемая Go-структура (`OrderConfirmedEvent`) в `core/<bc>/event/`;
конструктор `NewOrderConfirmedEvent(order Order) OrderConfirmedEvent` — единственная точка создания.

**AVOID:**

`kafka/event-named-in-past-tense` ❌ имя-команда (`ConfirmOrder`, `CreateProduct`).

`kafka/event-payload-hygiene` ❌ вложение агрегата или Entity целиком в payload — нестабильные поля, нарушение forward-compat.

`kafka/event-payload-hygiene` ❌ PII (email, phone, адрес) в широковещательных топиках — только `customer_id`; PII подгружается через Customer-сервис в restricted-topic.

`kafka/event-schema-forward-compatible` ❌ изменение существующего поля/удаление без version-суффикса в `event_type`.

---

## 7. Конфигурация (`R-KFK-CFG-*`)

`kafka/settings-are-typed-and-external` — параметры через типизированную структуру с `envconfig`; валидация на старте:

```go
// infra/config/kafka.go
type KafkaConfig struct {
    Brokers  []string `envconfig:"KAFKA_BROKERS" required:"true"`
    Topics   TopicsConfig
    TLS      TLSConfig
    ClientID string `envconfig:"KAFKA_CLIENT_ID" required:"true"` // R-KFK-SEC-2
}

type TopicsConfig struct {
    OrdersConfirmed string `envconfig:"KAFKA_TOPIC_ORDERS_CONFIRMED" required:"true"`
    PaymentsFailed  string `envconfig:"KAFKA_TOPIC_PAYMENTS_FAILED"  required:"true"`
}
```

`kafka/settings-are-typed-and-external` — `RequiredAcks: kafka.RequireAll`; `MaxAttempts`; `CommitInterval: 0` — явно в коде конфигурации
(не магические числа по всему проекту).

`kafka/deserialization-allow-list` — десериализация событий — через **явный реестр** `eventType → func([]byte) (Event, error)`;
не динамический `reflect` по строке из payload:

```go
var eventRegistry = map[string]func([]byte) (Event, error){
    "OrderConfirmed":  unmarshalOrderConfirmed,
    "PaymentFailed":   unmarshalPaymentFailed,
    "CustomerCreated": unmarshalCustomerCreated,
}
```

`kafka/missing-topics-are-fatal` — проверка существования топиков на старте через `kafka.DialLeader`/`ReadPartitions`; при
отсутствии ожидаемого топика — `log.Fatal` / возврат ошибки из `main`.

**AVOID:**

`kafka/deserialization-allow-list` ❌ динамическая десериализация по строке из payload (`reflect.New(registry[typeName])`) — RCE-риск.

`kafka/settings-are-typed-and-external` ❌ `Brokers: []string{"localhost:9092"}` хардкодом; всегда через `envconfig`.

---

## 8. Observability (`R-KFK-OBS-*`)

`kafka/consumer-lag-alerting` — метрики producer/consumer через `promauto`; consumer lag — через `kafka-go`-stats или
отдельный Prometheus exporter:

```go
var (
    messagesProduced = promauto.NewCounterVec(prometheus.CounterOpts{
        Name: "kafka_messages_produced_total",
        Help: "Total Kafka messages produced",
    }, []string{"topic"})

    messagesConsumed = promauto.NewCounterVec(prometheus.CounterOpts{
        Name: "kafka_messages_consumed_total",
        Help: "Total Kafka messages consumed",
    }, []string{"topic", "group"})

    processingErrors = promauto.NewCounterVec(prometheus.CounterOpts{
        Name: "kafka_processing_errors_total",
        Help: "Kafka consumer processing errors",
    }, []string{"topic", "group", "error_kind"})
)
```

`kafka/consumer-lag-alerting` — alert на consumer lag: `kafka_consumer_lag > N` для critical-топиков в течение 5 минут
(threshold: money-events — 1000, analytics — 100000).

`kafka/trace-context-in-headers` — tracing: producer кладёт `traceparent` в Kafka headers через OTel propagator; consumer
извлекает и продолжает span:

```go
// producer side
carrier := propagation.MapCarrier{}
otel.GetTextMapPropagator().Inject(ctx, carrier)
var headers []kafka.Header
for k, v := range carrier {
    headers = append(headers, kafka.Header{Key: k, Value: []byte(v)})
}
msg := kafka.Message{Key: key, Value: payload, Headers: headers}

// consumer side
carrier := propagation.MapCarrier{}
for _, h := range msg.Headers {
    carrier[h.Key] = string(h.Value)
}
ctx = otel.GetTextMapPropagator().Extract(ctx, carrier)
ctx, span := otel.Tracer("kafka-consumer").Start(ctx, "OrderConfirmed.process")
defer span.End()
```

`kafka/dlq-monitored-and-manually-replayed` — DLQ-size alert (counter `kafka_dlq_messages_total` + AlertManager правило).

**AVOID:**

`kafka/consumer-lag-alerting` ❌ отсутствие consumer-lag alerts — «пропадание» событий обнаруживается по жалобам.

---

## 9. Security (`R-KFK-SEC-*`)

`kafka/transport-security-and-acls` — в проде TLS через `kafka.Dialer` с `TLSConfig`:

```go
dialer := &kafka.Dialer{
    Timeout:   10 * time.Second,
    DualStack: true,
    TLS:       tlsCfg, // *tls.Config из cfg.TLS (cert + key + CA)
}
writer := kafka.NewWriter(kafka.WriterConfig{
    Brokers: cfg.Brokers,
    Dialer:  dialer,
    // ...
})
```

`kafka/transport-security-and-acls` — per-service `ClientID` в `KafkaConfig` для ACL-идентификации (не общий для всего кластера).

`kafka/event-payload-hygiene` — PII — отдельные restricted-топики или паттерн «слабая ссылка»: в широком топике только
`customer_id`, full PII consumer запрашивает у Customer-сервиса.

**AVOID:**

`kafka/transport-security-and-acls` ❌ `Dialer` без TLS / `security.protocol=PLAINTEXT` в проде.

`kafka/transport-security-and-acls` ❌ один `ClientID` на все сервисы — нет isolation на ACL-уровне.

---

## 10. Антипаттерны

| Код | Антипаттерн | Почему |
|---|---|---|
| `kafka/publish-via-outbox` | `WriteMessages` из UseCase Handler с DB-операцией | Kafka не XA; publish не откатится при DB rollback |
| `kafka/manual-offset-commit` | `CommitInterval > 0` (авто-commit) | Offset продвигается до завершения обработки |
| `kafka/publish-via-outbox` | Publish после `tx.Commit` без outbox | Падение между commit и publish = потеря события |
| `kafka/consumer-is-idempotent` | Offset как dedup-ключ | Зависит от GroupID; новый group → всё «впервые» |
| `kafka/retry-topics-with-limits` | `time.Sleep` в основном poll-цикле | Блокирует poll → Kafka считает consumer dead → rebalance |
| `kafka/no-swallowing-in-listener` | Проглатывание ошибки + commit | Событие потеряно без трейса |
| `kafka/deserialization-allow-list` | Динамический `reflect` по строке из payload | RCE-риск (аналог `trusted.packages: '*'`) |
| `kafka/event-payload-hygiene` | PII в широковещательном топике | Все consumer'ы группы видят email, phone |

---

## Чеклист подключения к новому сервису (Go)

- [ ] `KafkaConfig` через `envconfig`; `Brokers`, `ClientID`, `Topics.*` — `required:"true"`; нет хардкода
- [ ] `kafka.Writer` с `RequiredAcks: kafka.RequireAll`, `Balancer: &kafka.Hash{}`, `MaxAttempts: math.MaxInt32`
- [ ] Domain-события через outbox: `outbox`-таблица + relay-горутина; нет прямого `WriteMessages` из Handler
- [ ] Outbox-relay: `FOR UPDATE SKIP LOCKED`, batch 10–50, partial-индекс `WHERE published_at IS NULL`
- [ ] `kafka.Reader` с `CommitInterval: 0`, `StartOffset: kafka.FirstOffset`, уникальный `GroupID: "<service>-<purpose>"`
- [ ] `CommitMessages` только после успешной обработки
- [ ] `processed_event` с PK на `event_id`; dedup + бизнес-результат в одной `pgx.Tx`
- [ ] Retry-топики с задержкой **вне** poll-цикла + счётчик попыток + DLQ; нет `time.Sleep` в основной горутине
- [ ] `isTransient(err)` через `errors.As` по Integration-типу; poison pill → сразу в DLQ
- [ ] Событие — прошедшее время, `EventID` (UUID v7), `int64` для денег; конструктор в `core/<bc>/event/`
- [ ] Десериализация — статический реестр `map[string]func([]byte)`, не `reflect` по строке из payload
- [ ] Проверка топиков на старте (`ReadPartitions`); отсутствие ожидаемого топика → `fatal`
- [ ] TLS-dialer в проде; per-service `ClientID`; PII — restricted-топик или «слабая ссылка»
- [ ] `kafka_messages_produced_total`, `kafka_messages_consumed_total`, `kafka_processing_errors_total` (promauto)
- [ ] `traceparent` в Kafka headers: inject на producer, extract на consumer (OTel propagator)
- [ ] Alert на consumer lag + DLQ-size (Prometheus AlertManager)
