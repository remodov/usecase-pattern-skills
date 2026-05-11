# Kafka — индекс правил

> **Что это.** Сжатый индекс правил `kafka-style-guide.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с примерами, code-блоками, обоснованием и под-пунктами — `kafka-style-guide.md`**; открывай её точечно по
> нужному разделу, когда индекса не хватает (под-списки и code-сниппеты сюда не вынесены).
> Коды: `<PREFIX>-<N>` — обязательно, `<PREFIX>-X<N>` — запрещено.

## 1. Producer
**MUST:**
- **R-KFK-PROD-1.** Producer **всегда** идемпотентный: `enable.idempotence: true`. Это автоматически: `acks=all`, `retries=Integer.MAX_VALUE`, `max.in.flight.requests.per.connection ≤ 5`. Гарантирует exactly-once на уровне partition (по producer-id).
- **R-KFK-PROD-2.** **Partition key** — обязателен для всех бизнес-событий. Без ключа сообщения распределяются round-robin → теряется ordering для одного aggregate. Дефолтный ключ — **aggregate id**: Это гарантирует что все события одного `order.id` приходят на один partition в правильном порядке.
- **R-KFK-PROD-3.** Сериализация — **JSON** (`JsonSerializer`) по умолчанию. Для bandwidth-чувствительных топиков — Avro/Protobuf через Schema Registry (но это отдельная инфра, по умолчанию не настраивается).
- **R-KFK-PROD-4.** **Не используй `KafkaTemplate.send(...)` напрямую из use-case handler-а** для domain-событий. События идут через **outbox pattern** (`R-KFK-OBX-*`) — иначе при rollback транзакции события уже отправлены, появляются «несуществующие» события.
**MUST NOT:**
- **R-KFK-PROD-X1.** **`enable.idempotence: false`** в проде. Без идемпотентности retry на стороне producer создаёт дубликаты.
- **R-KFK-PROD-X2.** **`acks: 0`** или **`acks: 1`**. `0` = fire-and-forget (потеря данных при broker rebalance); `1` = ack от leader без репликации (потеря при failure leader до replication). Только `acks: all`.
- **R-KFK-PROD-X3.** **Send без partition key** для бизнес-событий. Round-robin = потеря порядка для aggregate.
- **R-KFK-PROD-X4.** **`KafkaTemplate.send(...)` из use-case handler в одной транзакции с DB-операцией.** Kafka и Postgres не могут участвовать в одной 2PC-транзакции (Kafka не поддерживает XA). При rollback БД событие в Kafka уже опубликовано — несоответствие. Используй outbox.

## 2. Consumer
**MUST:**
- **R-KFK-CONS-1.** Каждый consumer имеет уникальный **`group.id`** в формате `<service>-<consumer-purpose>`: Один consumer-group = одна логическая роль. Не делай общий `group.id: order-service` для всех listener-ов сервиса — потеряется ребалансинг по конкретной задаче.
- **R-KFK-CONS-2.** **Manual ack** — `spring.kafka.listener.ack-mode: MANUAL_IMMEDIATE` (или `MANUAL`). Auto-commit (`enable.auto.commit: true`) опасен: offset коммитится по таймеру независимо от успеха обработки → при крэше consumer теряет события или дублирует. Manual ack = коммитим только после успешной обработки.
- **R-KFK-CONS-3.** Listener-метод обязательно **idempotent** (см. `R-KFK-IDEM-*`). Сообщение может прийти 2+ раз — это норма Kafka (at-least-once); duplicate-detection — на стороне consumer.
- **R-KFK-CONS-4.** **`auto.offset.reset: earliest`** для critical-consumer'ов. `latest` (дефолт Spring) пропускает события если consumer-group новая или сильно отстал — недопустимо для денег / orders. `earliest` — начинать с самого старого retained-сообщения.
- **R-KFK-CONS-5.** **Concurrency** — настраивается per-listener: `concurrency` ≤ числа partition'ов топика. Иначе лишние consumer-instance бездействуют.
- **R-KFK-CONS-6.** **`max.poll.interval.ms`** ≥ ожидаемого времени обработки batch + buffer. Default 5 минут. Если обработка одного сообщения может занять > 5 минут — увеличить, иначе Kafka считает consumer dead и rebalance-ит.
**MUST NOT:**
- **R-KFK-CONS-X1.** **`enable.auto.commit: true`** в проде. Авто-коммит = offset продвигается до того, как обработка завершилась. Crash → потеря данных.
- **R-KFK-CONS-X2.** **Listener вызывает `Thread.sleep(...)`** или другие blocking-операции > 1s в одном цикле обработки. Блокирует poll-цикл, может привести к rebalance.
- **R-KFK-CONS-X3.** **`group.id` отсутствует** или одинаковый для двух разных listener-методов в одном сервисе. Без явного `group.id` Spring создаёт случайный — нет ребалансинга между pods.
- **R-KFK-CONS-X4.** **HTTP-вызов к внешней системе из listener** без CB/Bulkhead (`R-RES-WHERE-1`). Если внешняя система лежит, listener зависает → rebalance → дубликаты.

## 3. Outbox publishing
**MUST:**
- **R-KFK-OBX-1.** **Domain events** публикуются через outbox-relay, **не** напрямую `kafkaTemplate.send(...)` из handler. В handler:
- **R-KFK-OBX-2.** **Outbox-relay** — отдельный `@Component` с `@Scheduled`, который читает unpublished events с `FOR UPDATE SKIP LOCKED` (см. `PG-L-021`), публикует в Kafka через `KafkaTemplate.send(...)`, помечает `published_at`. Реализация — `ucp-pg-runtime-design` (`outbox` сценарий).
- **R-KFK-OBX-3.** **Topic name** в outbox derives от `eventType` или `aggregateType`:
- **R-KFK-OBX-4.** Outbox-relay обрабатывает batch (10–50 events за раз), **не** по одному. Это снижает overhead на DB-poll и Kafka-roundtrip. См. пример в `pg-runtime-style-guide.md`.
**MUST NOT:**
- **R-KFK-OBX-X1.** **`kafkaTemplate.send(...)` из `@Transactional`-метода**, особенно где есть DB-операция. Kafka commit не откатывается с DB rollback → inconsistent published events.
- **R-KFK-OBX-X2.** **`@TransactionalEventListener` для отправки в Kafka** без outbox. Обработчик срабатывает после commit → если процесс упал между commit и publish, событие потерялось.
- **R-KFK-OBX-X3.** **Outbox без `published_at` колонки** или без partial-индекса `WHERE published_at IS NULL`. Полный scan таблицы — тормоза.

## 4. Idempotent consumer
**MUST:**
- **R-KFK-IDEM-1.** Каждое событие имеет **уникальный `eventId`** (UUID v7) в payload или header'е. Consumer проверяет, обрабатывалось ли уже:
- **R-KFK-IDEM-2.** **`processed_event` таблица** — DDL под `PG-T-*`: PRIMARY KEY на `event_id` — UNIQUE constraint обеспечивает дедупликацию даже под race conditions. **TTL** через partition + drop_old (для долгоживущих топиков) или background-job, удаляющий старые записи.
- **R-KFK-IDEM-3.** **Записи в `processed_event` и бизнес-результат** — в **одной транзакции**. Если процесс упал между бизнес-update и mark-processed → следующий poll увидит «не processed» и обработает повторно (что ОК, потому что бизнес-операция была идемпотентной по `event_id`).
- **R-KFK-IDEM-4.** Для **money-операций** — двойная защита: `event_id` + `Idempotency-Key` на downstream HTTP вызовах. Любая retry-петля не должна привести к двойному списанию.
**MUST NOT:**
- **R-KFK-IDEM-X1.** **Listener без проверки `eventId`** для consumer'ов, где duplicate приведёт к проблеме. Default Kafka — at-least-once; полагаться на «обычно срабатывает один раз» опасно.
- **R-KFK-IDEM-X2.** Использовать **Kafka offset как dedup-ключ**. Offset зависит от consumer-group; при добавлении нового consumer-group все события приходят как «впервые».

## 5. Retry topic + DLQ
**MUST:**
- **R-KFK-RTRY-1.** **Retry topics** — отдельные топики с возрастающим delay:
- **R-KFK-RTRY-2.** Retry **только для transient failures**:
- **R-KFK-RTRY-3.** **DLQ-monitoring** — alert если в DLQ за час > N сообщений. Без алерта DLQ становится свалкой, и проблемы не замечают.
- **R-KFK-RTRY-4.** **Replay из DLQ** — отдельная админская операция (manual review + re-publish в основной топик). Не автоматическая (могут быть genuine bug).
**MUST NOT:**
- **R-KFK-RTRY-X1.** **Blocking retry в listener** через `Thread.sleep(N)` или `@Retryable` Spring-Retry с большой задержкой. Блокирует poll-цикл.
- **R-KFK-RTRY-X2.** **Игнорирование исключения** в listener (`try { ... } catch (Exception e) { log.error(...); ack.acknowledge(); }`). Событие потеряно, никто не узнает что не обработали.
- **R-KFK-RTRY-X3.** **Retry topic без max-attempts**. Бесконечный retry = lock-step с проблемной системой.
- **R-KFK-RTRY-X4.** **DLQ без monitoring**. Alert на размер очереди — обязательно.

## 6. Event design
**MUST:**
- **R-KFK-EVT-1.** **Имя события** — глагол в прошедшем времени: `OrderConfirmed`, `PaymentFailed`, `UserRegistered`. Не `ConfirmOrder` (это команда), не `OrderConfirmation` (это noun).
- **R-KFK-EVT-2.** Payload содержит:
- **R-KFK-EVT-3.** **Forward-compatible schema:** добавление новых полей — non-breaking. Удаление / переименование — breaking, требует нового `eventType.v2`. См. `R-VER-5` (REST forward-compat).
- **R-KFK-EVT-4.** **Domain event как Java record** в `core/<bc>/domain/event/`:
**MUST NOT:**
- **R-KFK-EVT-X1.** **Имя события — команда** (`ConfirmOrder` вместо `OrderConfirmed`). Команды и события — разные концепты в DDD.
- **R-KFK-EVT-X2.** **Внутренние объекты в payload** (`Aggregate`, `Entity` целиком). Сериализация может включить нестабильные внутренние поля, ломает forward-compat.
- **R-KFK-EVT-X3.** **PII в широковещательных топиках** (`orders.confirmed` — все consumer'ы видят email, phone). Нужен отдельный restricted-topic или по `customerId` подгрузка PII через сервис.
- **R-KFK-EVT-X4.** **Breaking change без версии в `eventType`**. Старые consumer'ы при regenerate схемы перестанут работать.

## 7. Конфигурация
**MUST:**
- **R-KFK-CFG-1.** Через `@ConfigurationProperties` + `@Validated` (`R-VLD-CFG-*`):
- **R-KFK-CFG-2.** `application.yml`:
- **R-KFK-CFG-3.** **`spring.json.trusted.packages`** — explicit allow-list. По умолчанию Spring блокирует deserialization (security). Указывай только пакеты с event-records.
- **R-KFK-CFG-4.** **`missing-topics-fatal: true`** в проде. Сервис не должен стартовать если ожидаемый топик не существует — ловим конфигурационные ошибки на старте.
**MUST NOT:**
- **R-KFK-CFG-X1.** **`spring.json.trusted.packages: '*'`** — security risk (deserialization gadgets из произвольных классов).
- **R-KFK-CFG-X2.** **`bootstrap-servers` hard-coded** в коде или yml без env-substitution. Нельзя катить разные кластеры (test/prod).

## 8. Observability
**MUST:**
- **R-KFK-OBS-1.** Spring Kafka автоматически экспортирует через Micrometer:
- **R-KFK-OBS-2.** **Alert на consumer lag**: если `kafka_consumer_lag > N` для критичных topic'ов в течение 5 минут → инцидент. Threshold зависит от пропускной способности (для money-events — 1000; для analytics — 100000).
- **R-KFK-OBS-3.** **Tracing через `traceparent`** (см. `R-HDR-4` REST). Producer кладёт current `traceparent` в Kafka headers; consumer извлекает и продолжает trace. Spring Kafka + OTel автоконфиг это делает.
- **R-KFK-OBS-4.** **DLQ-size alert** (см. `R-KFK-RTRY-3`).
**MUST NOT:**
- **R-KFK-OBS-X1.** **Отсутствие consumer-lag alerts**. Без них «пропадание» сообщений замечается через жалобы пользователей.

## 9. Security
**MUST:**
- **R-KFK-SEC-1.** В прод-кластере **TLS** (`security.protocol: SSL`) — обязательно для cross-network communication. SASL/PLAIN over plaintext запрещено.
- **R-KFK-SEC-2.** **ACL'ы на топики** — каждый сервис имеет ACL на чтение/запись только тех топиков, что ему нужны. Проектирование — DevOps/SRE, использование — clientId per-сервис в `KafkaSettings`.
- **R-KFK-SEC-3.** **PII-данные** — отдельные топики с restricted ACL, либо паттерн «слабая ссылка»: в широком топике только `customerId`, full PII consumer запрашивает у Customer-сервиса.
**MUST NOT:**
- **R-KFK-SEC-X1.** **`PLAINTEXT` в проде**. Только в локальной разработке.
- **R-KFK-SEC-X2.** **Один service-account** на весь кластер. ACL'ы по сервисам — для blast-radius containment.

## 10. Антипаттерны
