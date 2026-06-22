# Distributed Patterns — Go Style Guide (net/http + chi)

Реализация контракта `../distributed-patterns-rules.md` (коды `R-DIST-WHEN-*`, `R-DIST-SAGA-*`, `R-DIST-IDEM-*`,
`R-DIST-EC-*`, `R-DIST-OBX-*`, `R-DIST-COMP-*`, `R-DIST-TX-*`) на Go-стеке (stdlib `net/http` + chi).
Паттерны (saga/idempotency/eventual consistency/outbox/compensation) архитектурные — одни на всех языках; меняется
реализация транзакций (`@Transactional` → явная транзакция через `pgx`) и запреты 2PC.

> **Парадигма.** Go не имеет транзакционного менеджера в стиле Spring или SQLAlchemy UoW: транзакция — явный
> `pgxpool.Conn` / `pgx.Tx`, пробрасываемый через `context.Context` или параметр. Saga-оркестратор — обычная
> struct с методом `Advance(ctx, event)`, хранящий state в БД через sqlc. Нет аннотаций, нет магии — всё явно.

Структура слоёв UCP: `core/` (домен), `adapters/out/*` (Kafka-producer, HTTP-клиенты), `adapters/in/*` (chi-роутер,
Kafka-consumer), `internal/saga/` (оркестраторы).

---

## 1. Когда нужны (`R-DIST-WHEN-*`)

`R-DIST-WHEN-1` — операция охватывает 2+ сервиса и не завершается одной локальной транзакцией.
`R-DIST-WHEN-2` — один сервис + один PG → обычная `pgx.Tx`, без распределённых паттернов.
`R-DIST-WHEN-3` — сначала проверь альтернативы: объединить BC, modular monolith с одним PG.
`R-DIST-WHEN-X1` — saga для двух операций в одной БД.
`R-DIST-WHEN-X2` — микросервисы «из амбиций» (latency, debugging, failure modes) — лучше modular monolith.

PREFER: когда boundary явно межсервисный (Order → Payment → Inventory) — вводи saga.

AVOID: не вводи distributed-паттерн для двух операций в одной схеме PG; достаточно одной `pgx.Tx`.

---

## 2. Saga (`R-DIST-SAGA-*`)

`R-DIST-SAGA-1` — saga, когда операция cross-service с локальными транзакциями на каждом шаге.
`R-DIST-SAGA-2` — **orchestration** (центральный координатор) для сложных saga (4+ шага, branching).
`R-DIST-SAGA-3` — **choreography** (события без координатора) для простых (2–3 шага, без branching).
`R-DIST-SAGA-4` — **saga state в БД** (`saga_<name>` таблица): `saga_id`, `status`, `current_step`, `payload`.
`R-DIST-SAGA-5` — `saga_id` сквозной в каждом сообщении.

Orchestrator — отдельный компонент (`OrderSagaOrchestrator`), не handler. Реагирует на события шагов,
продвигает state в БД через sqlc, отправляет следующую команду через outbox.

```go
// internal/saga/order_saga.go
package saga

type OrderSagaStatus string

const (
	SagaCreated          OrderSagaStatus = "created"
	SagaPaymentPending   OrderSagaStatus = "payment_pending"
	SagaInventoryPending OrderSagaStatus = "inventory_pending"
	SagaCompleted        OrderSagaStatus = "completed"
	SagaCompensating     OrderSagaStatus = "compensating"
	SagaFailed           OrderSagaStatus = "failed"
)

type OrderSagaOrchestrator struct {
	queries *db.Queries
	outbox  OutboxWriter
}

func NewOrderSagaOrchestrator(queries *db.Queries, outbox OutboxWriter) *OrderSagaOrchestrator {
	return &OrderSagaOrchestrator{queries: queries, outbox: outbox}
}

func (o *OrderSagaOrchestrator) Start(ctx context.Context, tx pgx.Tx, cmd StartOrderSagaCommand) (uuid.UUID, error) {
	sagaID := uuid.New()
	qtx := o.queries.WithTx(tx)
	if err := qtx.InsertOrderSaga(ctx, db.InsertOrderSagaParams{
		SagaID:      sagaID,
		OrderID:     cmd.OrderID,
		Status:      string(SagaPaymentPending),
		CurrentStep: "reserve_payment",
		Payload:     cmd.Payload,
	}); err != nil {
		return uuid.Nil, fmt.Errorf("insert order saga: %w", err)
	}
	return sagaID, o.outbox.Write(ctx, tx, OutboxMessage{
		SagaID:  sagaID,
		Topic:   "payment.commands",
		Payload: ReservePaymentCommand{SagaID: sagaID, OrderID: cmd.OrderID, Amount: cmd.Amount},
	})
}

func (o *OrderSagaOrchestrator) OnPaymentReserved(ctx context.Context, tx pgx.Tx, event PaymentReservedEvent) error {
	qtx := o.queries.WithTx(tx)
	if err := qtx.UpdateOrderSagaStatus(ctx, db.UpdateOrderSagaStatusParams{
		SagaID:      event.SagaID,
		Status:      string(SagaInventoryPending),
		CurrentStep: "reserve_inventory",
	}); err != nil {
		return fmt.Errorf("update saga status: %w", err)
	}
	return o.outbox.Write(ctx, tx, OutboxMessage{
		SagaID:  event.SagaID,
		Topic:   "inventory.commands",
		Payload: ReserveInventoryCommand{SagaID: event.SagaID, OrderID: event.OrderID},
	})
}

func (o *OrderSagaOrchestrator) OnPaymentFailed(ctx context.Context, tx pgx.Tx, event PaymentFailedEvent) error {
	qtx := o.queries.WithTx(tx)
	return qtx.UpdateOrderSagaStatus(ctx, db.UpdateOrderSagaStatusParams{
		SagaID:      event.SagaID,
		Status:      string(SagaFailed),
		CurrentStep: "terminal",
	})
}
```

`R-DIST-SAGA-X1` — 2PC/XA вместо saga; в Go нет стандартного XA-менеджера, и это не нужно.
`R-DIST-SAGA-X2` — saga без compensation («полусделанная» транзакция в продакшне).
`R-DIST-SAGA-X3` — saga state in-memory (рестарт теряет in-flight saga).
`R-DIST-SAGA-X4` — saga логика в UseCase Handler (orchestrator — отдельный компонент).

PREFER: orchestrator как отдельная struct в `internal/saga/`; handler запускает `saga.Start(...)` в своей транзакции.

AVOID: не помещай saga-переходы в UseCase Handler; не храни current step только в памяти.

---

## 3. Idempotency (`R-DIST-IDEM-*`)

`R-DIST-IDEM-1` — у каждого cross-service сообщения уникальный `event_id` / `message_id` (UUID v4/v7).
`R-DIST-IDEM-2` — receiver хранит `processed_event` (проверка до, запись в той же `pgx.Tx`).
`R-DIST-IDEM-3` — для HTTP-команд хранить `(idempotency_key, response_body, status_code)`: повтор с тем же ключом →
сохранённый ответ; другой `command_hash` с тем же ключом → `409 Conflict`.
`R-DIST-IDEM-4` — money: заголовок `Idempotency-Key` + UNIQUE `(provider_id, external_payment_id)` на уровне БД.
`R-DIST-IDEM-5` — TTL idempotency-записей 24–72 часа (периодически очищать по `created_at`).

### HTTP-команды — idempotency middleware

```go
// adapters/in/http/middleware/idempotency.go
type IdempotencyMiddleware struct {
	queries *db.Queries
	pool    *pgxpool.Pool
}

func (m *IdempotencyMiddleware) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		key := r.Header.Get("Idempotency-Key")
		if key == "" {
			next.ServeHTTP(w, r)
			return
		}

		body, err := io.ReadAll(r.Body)
		if err != nil {
			httperr.Write(w, r, err)
			return
		}
		r.Body = io.NopCloser(bytes.NewReader(body))
		commandHash := sha256Hex(body)

		ctx := r.Context()
		existing, err := m.queries.FindIdempotencyRecord(ctx, key)
		if err == nil {
			if existing.CommandHash != commandHash {
				httperr.Write(w, r, &ConflictingIdempotencyKeyError{Key: key})
				return
			}
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(int(existing.StatusCode))
			_, _ = w.Write(existing.ResponseBody)
			return
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			httperr.Write(w, r, fmt.Errorf("idempotency lookup: %w", err))
			return
		}

		rec := &responseRecorder{ResponseWriter: w, buf: &bytes.Buffer{}}
		next.ServeHTTP(rec, r)

		tx, err := m.pool.Begin(ctx)
		if err != nil {
			return
		}
		defer tx.Rollback(ctx)
		_ = m.queries.WithTx(tx).InsertIdempotencyRecord(ctx, db.InsertIdempotencyRecordParams{
			IdempotencyKey: key,
			CommandHash:    commandHash,
			StatusCode:     int32(rec.status),
			ResponseBody:   rec.buf.Bytes(),
			ExpiresAt:      time.Now().Add(48 * time.Hour),
		})
		_ = tx.Commit(ctx)
	})
}
```

### Kafka consumer — dedup

```go
// adapters/in/kafka/consumer.go

func headerValue(headers []kafka.Header, key string) string {
	for _, h := range headers {
		if h.Key == key {
			return string(h.Value)
		}
	}
	return ""
}

func (c *OrderConsumer) handleMessage(ctx context.Context, tx pgx.Tx, msg kafka.Message) error {
	eventID := headerValue(msg.Headers, "event_id")
	qtx := c.queries.WithTx(tx)

	exists, err := qtx.ExistsProcessedEvent(ctx, eventID)
	if err != nil {
		return fmt.Errorf("check processed event: %w", err)
	}
	if exists {
		return nil
	}

	if err := c.processEvent(ctx, qtx, msg); err != nil {
		return err
	}

	return qtx.InsertProcessedEvent(ctx, db.InsertProcessedEventParams{
		EventID:   eventID,
		Topic:     msg.Topic,
		ExpiresAt: time.Now().Add(72 * time.Hour),
	})
}
```

`R-DIST-IDEM-X1` — receiver без dedup для money/critical.
`R-DIST-IDEM-X2` — только receiver-side (producer тоже exactly-once: kafka-go `RequiredAcks: -1` + `Balancer: &kafka.Hash{}`).
`R-DIST-IDEM-X3` — `Idempotency-Key` генерируется как новый UUID на каждый retry (ключ один на бизнес-операцию).

PREFER: idempotency-проверку атомарно в одной транзакции с самой операцией; выделить middleware для HTTP-команд.

AVOID: не проверяй dupliate вне транзакции (TOCTOU); не храни `Idempotency-Key` только в памяти.

---

## 4. Eventual consistency (`R-DIST-EC-*`)

`R-DIST-EC-1` — декларация в OpenAPI описании endpoint: ожидаемая задержка read-проекции. В Go через аннотации
в swagger-комментариях (`swaggo/swag`) или вручную в `openapi.yaml`.
`R-DIST-EC-2` — read-your-writes при необходимости: читать из write-side (primary replica) или передавать
`version`-токен клиенту в response, клиент прокидывает его в следующий read.
`R-DIST-EC-3` — bounded staleness с явным SLO + алёрт на Prometheus: `read_projection_lag_seconds` > порога.
`R-DIST-EC-4` — causal consistency через `version`-поля: receiver применяет событие только если
`event.version > current_version`, иначе skip (идемпотентный skip).

```go
// core/order/projection.go
func (p *OrderProjection) Apply(ctx context.Context, tx pgx.Tx, event OrderEvent) error {
	qtx := p.queries.WithTx(tx)
	current, err := qtx.GetOrderProjectionVersion(ctx, event.OrderID)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return fmt.Errorf("get projection version: %w", err)
	}
	if event.Version <= current {
		return nil
	}
	return qtx.UpsertOrderProjection(ctx, db.UpsertOrderProjectionParams{
		OrderID: event.OrderID,
		Version: event.Version,
		Status:  string(event.NewStatus),
	})
}
```

Метрика задержки:

```go
// adapters/in/kafka/metrics.go
var projectionLag = promauto.NewHistogram(prometheus.HistogramOpts{
	Name:    "read_projection_lag_seconds",
	Help:    "Lag between event timestamp and projection update",
	Buckets: prometheus.DefBuckets,
})

func recordLag(eventTime time.Time) {
	projectionLag.Observe(time.Since(eventTime).Seconds())
}
```

`R-DIST-EC-X1` — молчаливая EC: endpoint возвращает stale-data без декларации в OpenAPI / без заголовка.
`R-DIST-EC-X2` — strict consistency через 2PC под нагрузкой; перепроектируй boundary или прими EC.

PREFER: явно объявлять EC в OpenAPI-описании endpoint; мерить лаг как метрику, не только логировать.

AVOID: не отдавай stale-data молча; не пытайся реализовать строгую консистентность через несколько PG.

---

## 5. Outbox + Inbox (`R-DIST-OBX-*`)

`R-DIST-OBX-1` — **outbox** для исходящих событий обязателен.
`R-DIST-OBX-2` — **inbox** для входящих (опционально, critical-сценарии): сохранить в `inbox_message` до
обработки, обработать в отдельной горутине/воркере.
`R-DIST-OBX-3` — single source of truth — БД сервиса; Kafka — транспорт.

### Outbox writer

```go
// internal/outbox/writer.go
package outbox

type Writer struct {
	queries *db.Queries
}

func NewWriter(queries *db.Queries) *Writer {
	return &Writer{queries: queries}
}

func (w *Writer) Write(ctx context.Context, tx pgx.Tx, msg Message) error {
	payload, err := json.Marshal(msg.Payload)
	if err != nil {
		return fmt.Errorf("marshal outbox payload: %w", err)
	}
	return w.queries.WithTx(tx).InsertOutboxMessage(ctx, db.InsertOutboxMessageParams{
		MessageID:   uuid.New(),
		Topic:       msg.Topic,
		Key:         msg.Key,
		Payload:     payload,
		Headers:     encodeHeaders(msg.Headers),
		CreatedAt:   time.Now(),
	})
}
```

### Outbox relay (поллер)

```go
// internal/outbox/relay.go
type Relay struct {
	queries  *db.Queries
	pool     *pgxpool.Pool
	producer *kafka.Writer
}

func (r *Relay) Run(ctx context.Context) {
	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := r.flush(ctx); err != nil {
				slog.ErrorContext(ctx, "outbox flush failed", "error", err)
			}
		}
	}
}

func (r *Relay) flush(ctx context.Context) error {
	msgs, err := r.queries.FetchPendingOutboxMessages(ctx, 100)
	if err != nil {
		return fmt.Errorf("fetch outbox: %w", err)
	}
	for _, m := range msgs {
		if err := r.producer.WriteMessages(ctx, kafka.Message{
			Topic:   m.Topic,
			Key:     []byte(m.Key),
			Value:   m.Payload,
			Headers: decodeHeaders(m.Headers),
		}); err != nil {
			return fmt.Errorf("write kafka: %w", err)
		}
		if err := r.queries.MarkOutboxMessageSent(ctx, m.MessageID); err != nil {
			return fmt.Errorf("mark sent: %w", err)
		}
	}
	return nil
}
```

`R-DIST-OBX-X1` — прямой `producer.WriteMessages` из command-handler без outbox.
`R-DIST-OBX-X2` — публикация через goroutine-after-commit без outbox (нет атомарности с транзакцией).

PREFER: writer и relay — отдельные компоненты; relay запускается в отдельной горутине через `errgroup`.

AVOID: не вызывай Kafka producer синхронно из handler внутри транзакции; не запускай relay через `time.Sleep`.

---

## 6. Compensation (`R-DIST-COMP-*`)

`R-DIST-COMP-1` — у каждой command в саге есть compensation-команда.
`R-DIST-COMP-2` — compensation идемпотентен (saga может повторить; проверка по `(saga_id, step)` в БД).
`R-DIST-COMP-3` — **semantic compensation**, не технический rollback: был платёж → compensation = refund
(новая транзакция в платёжной системе), не «откат».
`R-DIST-COMP-4` — compensation оставляет audit trail (статус `refunded` + ссылка на оригинал), не DELETE/UPDATE с
потерей истории.

```go
// internal/saga/order_saga.go — компенсация payment при сбое inventory

func (o *OrderSagaOrchestrator) OnInventoryFailed(ctx context.Context, tx pgx.Tx, event InventoryFailedEvent) error {
	qtx := o.queries.WithTx(tx)
	if err := qtx.UpdateOrderSagaStatus(ctx, db.UpdateOrderSagaStatusParams{
		SagaID:      event.SagaID,
		Status:      string(SagaCompensating),
		CurrentStep: "refund_payment",
	}); err != nil {
		return fmt.Errorf("update saga to compensating: %w", err)
	}
	return o.outbox.Write(ctx, tx, OutboxMessage{
		SagaID:  event.SagaID,
		Topic:   "payment.commands",
		Payload: RefundPaymentCommand{
			SagaID:          event.SagaID,
			OriginalOrderID: event.OrderID,
			Reason:          "inventory_unavailable",
		},
	})
}

func (o *OrderSagaOrchestrator) OnPaymentRefunded(ctx context.Context, tx pgx.Tx, event PaymentRefundedEvent) error {
	qtx := o.queries.WithTx(tx)
	if err := qtx.UpdateOrderSagaStatus(ctx, db.UpdateOrderSagaStatusParams{
		SagaID:      event.SagaID,
		Status:      string(SagaFailed),
		CurrentStep: "terminal",
	}); err != nil {
		return fmt.Errorf("mark saga failed after refund: %w", err)
	}
	return qtx.UpdateOrderStatus(ctx, db.UpdateOrderStatusParams{
		OrderID: event.OrderID,
		Status:  "cancelled",
		Reason:  "payment_refunded",
	})
}
```

DLQ для compensation, которое упало:

```go
// adapters/in/kafka/consumer.go
func (c *Consumer) handleWithDLQ(ctx context.Context, msg kafka.Message) {
	if err := c.handle(ctx, msg); err != nil {
		slog.ErrorContext(ctx, "compensation failed, routing to DLQ",
			"topic", msg.Topic,
			"error", err,
			"saga_id", headerValue(msg.Headers, "saga_id"),
		)
		_ = c.dlqWriter.WriteMessages(ctx, toDLQ(msg, err))
	}
}
```

`R-DIST-COMP-X1` — saga без compensation.
`R-DIST-COMP-X2` — `DELETE FROM orders` как compensation («отмена» → смена статуса на `cancelled`).
`R-DIST-COMP-X3` — compensation, которое может упасть без DLQ + manual review (висящие деньги).

PREFER: compensation-команды через outbox (та же гарантия at-least-once); DLQ-топик + алёрт при попадании в него.

AVOID: не делай `DELETE` как compensation; не игнорируй ошибку compensation (silent fail → финансовый инцидент).

---

## 7. Distributed transactions — чего НЕ делать (`R-DIST-TX-*`)

`R-DIST-TX-X1` — 2PC/XA в стеке. В Go нет стандартного XA-менеджера; `database/sql` не поддерживает XA;
попытка реализовать через ручные prepare/commit по двум `pgx.Conn` — best-effort без recovery.
`R-DIST-TX-X2` — единая «распределённая транзакция» через несколько `pgxpool.Pool` (разные сервисы/БД).
`R-DIST-TX-X3` — последовательный commit по нескольким `pgx.Tx` вручную без saga-recovery:

```go
// AVOID — нет атомарности, нет recovery при сбое между tx1.Commit и tx2.Commit
tx1.Commit(ctx)
tx2.Commit(ctx) // если упало — inconsistency без recovery-плана
```

`R-DIST-TX-1` — saga с локальными транзакциями: каждый сервис коммитит только свою `pgx.Tx`.
`R-DIST-TX-2` — outbox + idempotent consumer для cross-service event-driven sync.
`R-DIST-TX-3` — modular monolith: несколько BC в одном Go-бинаре с одним `pgxpool.Pool`; одна `pgx.Tx` работает.

```go
// PREFER — локальная транзакция в одном сервисе
tx, err := pool.Begin(ctx)
if err != nil {
	return fmt.Errorf("begin tx: %w", err)
}
defer tx.Rollback(ctx)

if err := qtx.UpdateOrderStatus(ctx, ...); err != nil {
	return err
}
if err := outboxWriter.Write(ctx, tx, ...); err != nil {
	return err
}
return tx.Commit(ctx)
```

PREFER: один `pgx.Tx` на шаг saga; outbox в той же транзакции.

AVOID: не начинай две `pgx.Tx` в разных БД без saga-recovery; не держи транзакцию открытой через сетевой вызов.

---

## Чеклист подключения к новому сервису (Go)

- [ ] Распределённые паттерны только при cross-service операции; иначе одна `pgx.Tx` + sqlc.
- [ ] Saga: orchestrator — отдельная struct в `internal/saga/`, state в `saga_<name>` таблице, `saga_id` в каждом сообщении.
- [ ] Каждый шаг saga имеет compensation-команду; compensation идемпотентен и проверяется по `(saga_id, step)`.
- [ ] Outbox writer атомарен с бизнес-транзакцией (`queries.WithTx(tx)`); relay — отдельная горутина в `errgroup`.
- [ ] Idempotency: `processed_event`-таблица с проверкой в той же транзакции; HTTP-команды — middleware с `(idempotency_key, command_hash, response)`.
- [ ] Money: `Idempotency-Key` заголовок + UNIQUE `(provider_id, external_payment_id)` в БД.
- [ ] TTL idempotency-записей 24–72ч; фоновая очистка по `expires_at`.
- [ ] Eventual consistency задекларирована в OpenAPI/комментарии; `read_projection_lag_seconds` как Prometheus-метрика.
- [ ] Causal consistency: `event.Version > current_version` перед применением, иначе идемпотентный skip.
- [ ] Compensation оставляет audit trail (статус + reference); нет `DELETE` как compensation; DLQ при сбое compensation.
- [ ] Нет последовательных commit по двум `pgx.Tx` разных сервисов/БД без saga-recovery.
- [ ] Нет прямого `producer.WriteMessages` из handler в транзакции без outbox.
- [ ] DLQ-топик для failed compensation + алёрт на появление сообщений в нём.
- [ ] Saga state recovery: при рестарте сервиса — поллинг `saga_<name>` по статусу `IN_PROGRESS` и resumption.
