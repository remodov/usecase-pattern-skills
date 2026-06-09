# Distributed Patterns — индекс правил (язык-нейтральный)

> **Что это.** Сжатый индекс правил: код + интент, по разделам — **общий контракт для всех языков**.
> Рабочий вход скиллов: review цитирует код, design сверяется по чек-листу.
> **Реализация по языкам** — `java/distributed-patterns-style-guide.md` (Spring + JTA-запреты) и
> `python/distributed-patterns-style-guide.md` (saga-orchestrator + UoW + aiokafka); открывай нужный точечно.
> Коды: `R-DIST-<GROUP>-<N>` — обязательно, `R-DIST-<GROUP>-X<N>` — запрещено. **Коды общие для всех языков** —
> паттерны (saga/idempotency/EC/outbox/compensation) архитектурные; меняется реализация транзакций (`@Transactional` ↔ UoW).

## 1. Когда нужны распределённые паттерны
**MUST:**
- **R-DIST-WHEN-1.** Распределённые паттерны нужны когда **бизнес-операция охватывает 2+ микросервиса** и нельзя завершить её одной локальной транзакцией:
- **R-DIST-WHEN-2.** Если операция **в одном сервисе и одном PG** — не нужны распределённые паттерны. Используй локальную транзакцию (UoW) и атомарность БД.
- **R-DIST-WHEN-3.** Перед введением распределённого паттерна — **проверь альтернативы:**
**MUST NOT:**
- **R-DIST-WHEN-X1.** **Распределённые паттерны для одного сервиса.** Saga для двух операций в одной БД = self-orchestrated сложность.
- **R-DIST-WHEN-X2.** **Микросервисы из амбиций.** Распределение всегда дорогое: увеличивает latency, усложняет debugging, требует distributed tracing, добавляет failure modes. Если бизнес не требует — лучше modular monolith.

## 2. Saga — оркестрация vs хореография
**MUST:**
- **R-DIST-SAGA-1.** Saga применяется когда:
- **R-DIST-SAGA-2.** **Orchestration** (центральный координатор) — рекомендуется для **complex sagas** с 4+ шагов или sagas с branching.
- **R-DIST-SAGA-3.** **Choreography** (события без координатора) — для **simple sagas** 2-3 шага без branching.
- **R-DIST-SAGA-4.** **Saga state** хранится в БД (`saga_<name>` таблица): Это даёт видимость («какие saga в процессе»), recovery (если orchestrator упал), audit.
- **R-DIST-SAGA-5.** **Saga ID в каждом сообщении** — сквозной ID для трассировки, связывает все шаги.
**MUST NOT:**
- **R-DIST-SAGA-X1.** **Distributed transaction (2PC, XA)** через JTA вместо saga. JTA не работает для большинства не-XA брокеров (Kafka), не масштабируется, добавляет single point of failure.
- **R-DIST-SAGA-X2.** **Saga без compensation logic.** Если шаг 3 упал, а шаги 1-2 уже committed — без compensation у нас «полусделанная» транзакция в проде.
- **R-DIST-SAGA-X3.** **Saga state только in-memory.** При рестарте orchestrator теряется состояние всех in-flight sagas → процессы зависают.
- **R-DIST-SAGA-X4.** **Saga смешана с use case** в одном handler-е. Saga — отдельный orchestrator-компонент; use cases — отдельные локальные транзакции.

## 3. Idempotency
**MUST:**
- **R-DIST-IDEM-1.** **Каждое cross-service сообщение** имеет уникальный ID:
- **R-DIST-IDEM-2.** **Receiver хранит processed-events** в БД (`processed_event` таблица, см. `R-KFK-IDEM-2`). Перед обработкой — проверка наличия. После — запись в той же транзакции.
- **R-DIST-IDEM-3.** Для **HTTP-команд** receiver хранит `(idempotency_key, response)` пару в БД: Повторный запрос с тем же ключом возвращает сохранённый response. Если `command_hash` отличается (тот же ключ, другая команда) — `409 Conflict`.
- **R-DIST-IDEM-4.** **Money-операции — двойная защита**: `Idempotency-Key` от клиента + внутренняя дедупликация по `(payment_provider_id, external_payment_id)` уникальный constraint.
- **R-DIST-IDEM-5.** **TTL для idempotency-records** — типично 24-72 часа. Дольше — таблица растёт; короче — реальный retry клиента (через час) не проходит дедупликацию.
**MUST NOT:**
- **R-DIST-IDEM-X1.** **Receiver без dedup** для money / critical-команд. «Обычно дублируется редко» = дважды списанные деньги в инциденте.
- **R-DIST-IDEM-X2.** **Полагаться на receiver-side только**. Sender (producer) тоже должен иметь exactly-once гарантии (Kafka `enable.idempotence: true`, см. `R-KFK-PROD-1`).
- **R-DIST-IDEM-X3.** **`Idempotency-Key = UUID каждый раз`**. Клиент должен генерировать ключ **один раз** на бизнес-операцию, retry'ить с тем же ключом. Иначе дедупликация бессмысленна.

## 4. Eventual consistency
**MUST:**
- **R-DIST-EC-1.** **Декларация в API** — для endpoint, который читает eventual-consistent данные, в OpenAPI описании указывать ожидаемую задержку:
- **R-DIST-EC-2.** **Read-your-writes** — если критично — реализуется одним из способов:
- **R-DIST-EC-3.** **Bounded staleness** — у каждой read-model явный SLO на максимальную задержку: «не более 5 секунд между write и появлением в read-проекции». Алерт если превышается.
- **R-DIST-EC-4.** **Causal consistency** через `vector clocks` или `version`-поля — для cases где порядок событий важен. Receiver проверяет: `event.version > current_version` перед применением; иначе skip.
**MUST NOT:**
- **R-DIST-EC-X1.** **Молчаливая eventual consistency.** Endpoint возвращает stale-data без декларации; клиент удивляется «я только что write сделал, почему не вижу».
- **R-DIST-EC-X2.** **Strict immediate consistency через 2PC** в распределённой системе с большой нагрузкой. Не масштабируется. Перепроектируй boundary либо прими EC.

## 5. Outbox + Inbox
**MUST:**
- **R-DIST-OBX-1.** **Outbox pattern** для исходящих событий — обязателен (см. `R-KFK-OBX-*`):
- **R-DIST-OBX-2.** **Inbox pattern** для входящих сообщений (опционально, для critical-сценариев):
- **R-DIST-OBX-3.** **Single source of truth** — БД сервиса. Kafka — транспорт сообщений, не источник правды. При потере Kafka-данных — outbox-таблица продолжает накапливать, после восстановления Kafka — публикует.
**MUST NOT:**
- **R-DIST-OBX-X1.** **Direct send из command-handler** без outbox. См. `R-KFK-PROD-X4`.
- **R-DIST-OBX-X2.** after-commit-листенер для отправки в Kafka. См. `R-KFK-OBX-X2`.

## 6. Compensation
**MUST:**
- **R-DIST-COMP-1.** **Каждая command, участвующая в саге, имеет compensation-команду**:
- **R-DIST-COMP-2.** **Compensation идемпотентен** — saga может повторить compensation несколько раз при retry. См. `R-DIST-IDEM-*`.
- **R-DIST-COMP-3.** **Semantic compensation, не технический rollback.** Если был платёж — compensation = refund (новая транзакция), не «откат» (ничего не откатывается, деньги уже у банка).
- **R-DIST-COMP-4.** **Compensation в БД оставляет audit trail** — статус «refunded» с reference к оригинальной транзакции. Не DELETE, не UPDATE с потерей истории.
**MUST NOT:**
- **R-DIST-COMP-X1.** **Saga без compensation** (см. `R-DIST-SAGA-X2`).
- **R-DIST-COMP-X2.** **DELETE как compensation**. Если было «создан заказ» → compensation должно быть «cancelled order» (state-change), не `DELETE FROM orders`. Иначе теряется audit + реальные данные (refund к зомби-заказу).
- **R-DIST-COMP-X3.** **Compensation, которое снова может упасть и не имеет повторного compensation.** Если refund упал — у нас «висящие деньги». Нужен dead-letter queue + manual review.

## 7. Distributed transactions — что НЕ делать
**MUST NOT:**
- **R-DIST-TX-X1.** **JTA / 2PC / XA транзакции** в нашем стеке. Причины:
- **R-DIST-TX-X2.** **Single distributed transaction через Spring `JtaTransactionManager`** для multi-datasource. Используй modular monolith с одним PG, либо разделение на сервисы с saga.
- **R-DIST-TX-X3.** **`PlatformTransactionManager` over multiple datasources** через `ChainedTransactionManager` — best-effort, **не** атомарность. При failure между commit'ами — inconsistency, без recovery-плана.
**MUST:**
- **R-DIST-TX-1.** **Saga с локальными транзакциями** — стандарт UCP (см. `R-DIST-SAGA-*`).
- **R-DIST-TX-2.** **Outbox + Idempotent consumer** для cross-service event-driven sync.
- **R-DIST-TX-3.** **Modular monolith** для tight coupling — несколько BC в одном процессе с одним PG. Локальные транзакции работают.

## 8. Антипаттерны
