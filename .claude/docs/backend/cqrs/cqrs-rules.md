# CQRS — индекс правил (язык-нейтральный)

> **Что это.** Сжатый индекс правил: код + интент, по разделам — **общий контракт для всех языков**.
> Рабочий вход скиллов: review цитирует код, design сверяется по чек-листу.
> **Реализация по языкам** — `java/cqrs-style-guide.md` (Spring + jOOQ ViewRepository) и
> `python/cqrs-style-guide.md` (FastAPI + SQLAlchemy ViewRepository, read-only сессия); открывай нужный точечно.
> Коды: `R-CQRS-<GROUP>-<N>` — обязательно, `R-CQRS-<GROUP>-X<N>` — запрещено. **Коды общие для всех языков** —
> меняется реализация (маркеры `UseCaseCommand`/`UseCaseQuery` ↔ `Command`/`Query` Protocol, `SelectMode.NO_LOCK` ↔ read-only сессия).

## 1. Когда CQRS оправдан
**MUST:**
- **R-CQRS-WHEN-1.** **Lightweight CQRS на маркерах** (Command / Query) — обязателен на Уровне 2+. Это бесплатное разделение: один и тот же интерфейс, два маркера, разные транзакционные свойства, разная валидация. Не требует отдельной read-БД. CQRS — опция Уровня 2 (Use Case Pattern), не отдельный уровень зрелости.
- **R-CQRS-WHEN-2.** **Полный CQRS с разделением хранилищ** (write-DB + read-DB / search-engine / cache) оправдан при:
- **R-CQRS-WHEN-3.** **Денормализованная read-model** (отдельная PG-таблица в той же БД) — middle-ground. Подходит когда:
**MUST NOT:**
- **R-CQRS-WHEN-X1.** **Полный CQRS «just in case»** для нового сервиса без явной проблемы read-нагрузки. Стартуем с lightweight (маркеры + один и тот же `Repository`), эволюционируем к full CQRS когда метрики покажут необходимость.
- **R-CQRS-WHEN-X2.** **Разделение баз без явной причины.** Read-DB + write-DB добавляют sync complexity, eventual consistency, инфра-стоимость. Должна быть конкретная боль.

## 2. Command side
**MUST:**
- **R-CQRS-CMD-1.** Command — иммутабельный тип, реализует Command-маркер (см. `R-UC-1`):
- **R-CQRS-CMD-2.** Command **меняет state одного агрегата**. Если меняет несколько — это либо saga (см. `R-DIST-SAGA-*`), либо неправильно нарезаны границы агрегатов (`R-AGG-*`).
- **R-CQRS-CMD-3.** Command handler:
- **R-CQRS-CMD-4.** Command возвращает **минимум**: id новой/изменённой entity, статус (id/код) либо пустой результат. Не возвращай read-DTO целиком из command — это смешение responsibilities.
- **R-CQRS-CMD-5.** Validation на command — частично контракт (через DTO-валидацию, см. `R-VLD-WHERE-1`); бизнес-инварианты — в агрегате (`R-VLD-WHERE-3`).
**MUST NOT:**
- **R-CQRS-CMD-X1.** Command-handler делает SELECT для **чтения** «и обновления потом». Read должен идти через query-handler. Если внутри command нужно что-то прочитать — это часть load-aggregate (одно действие), не отдельный read.
- **R-CQRS-CMD-X2.** Command возвращает **полный read-DTO** (`OrderJson` со всеми вложениями для UI). Контроллер сам сделает второй call в query-handler если UI нужен read после write.
- **R-CQRS-CMD-X3.** **Несколько агрегатов** меняются в одной транзакции command-handler без саги. Нарушает aggregate-границы и atomicity (`R-AGG-X*`).

## 3. Query side
**MUST:**
- **R-CQRS-QRY-1.** Query — иммутабельный тип, реализует Query-маркер (см. `R-UC-1`):
- **R-CQRS-QRY-2.** Query handler:
- **R-CQRS-QRY-3.** Read-DTO — **read-model record** в `core/<bc>/dto/view/` или `core/<bc>/domain/repository/view/`: Структура продиктована UI/API needs, не агрегатом.
- **R-CQRS-QRY-4.** Query handler **не вызывает доменные методы** агрегата (`order.confirm()` etc.). Только read.
**MUST NOT:**
- **R-CQRS-QRY-X1.** Query handler делает write (UPDATE / INSERT / DELETE). Это уже command, перенеси.
- **R-CQRS-QRY-X2.** Query handler **загружает агрегат целиком** через основной `<X>Repository` (с multiset, FOR UPDATE и т.п.) и потом маппит в read-DTO. Это лишняя работа: если есть `<X>ViewRepository` — используй его; если нет — создай.
- **R-CQRS-QRY-X3.** Query возвращает агрегат (`Order`) или его внутренние Entity (`OrderItem`) наружу. Это нарушение границ DDD — потребитель может вызвать business-методы на read-объекте, что разорвёт инварианты.

## 4. Read-model
**MUST:**
- **R-CQRS-RM-1.** Read-model хранится в **месте, оптимальном для нагрузки чтения**:
- **R-CQRS-RM-2.** **Schema read-model** — независимая от write-схемы. Денормализуй: `order_summary` содержит `customer_name`, `customer_email_hash` без join к `customer` таблице.
- **R-CQRS-RM-3.** Read-model **обновляется через события** (`R-CQRS-SYNC-*`), не synchronously в command-handler:
- **R-CQRS-RM-4.** Read-model **может быть восстановлена** из write-side данных. Если read-model потеряна — есть скрипт перебора всех агрегатов и пересчёта read-model. Это критично для disaster recovery.
**MUST NOT:**
- **R-CQRS-RM-X1.** Read-model **с бизнес-логикой** (триггеры на UPDATE с CHECK-constraint бизнес-правил). Логика в write-side; read-model — только проекция.
- **R-CQRS-RM-X2.** **Source-of-truth read-model.** Если read-model потеряна и не восстановима из write-side — это уже не CQRS, это две разных системы с risk inconsistency.
- **R-CQRS-RM-X3.** **Bidirectional sync** (read-model → write-side). Eventual consistency идёт **в одну сторону**: write → events → read. Обратное направление = две систему с своим source-of-truth = ад.

## 5. Синхронизация через события
**MUST:**
- **R-CQRS-SYNC-1.** **Синхронизация через outbox + Kafka** (см. `R-KFK-OBX-1`):
- **R-CQRS-SYNC-2.** **Idempotent consumer** обязателен (см. `R-KFK-IDEM-1`). Read-model UPDATE может прийти дважды; consumer должен это распознавать (`processed_event` таблица или idempotent UPDATE через `version`-проверку).
- **R-CQRS-SYNC-3.** **Синхронный fallback при бутстрапе.** При первом запуске сервиса (или при потере read-model) — батч-задача проходит по агрегатам и rebuilds read-model. Не ждём пока придут события за 30 дней.
- **R-CQRS-SYNC-4.** **Eventual consistency декларируется в API**. Endpoint `GET /orders/{id}/summary` имеет в OpenAPI:
- **R-CQRS-SYNC-5.** **Read-your-writes** при необходимости — гарантия что после `POST /orders` (write) тот же клиент видит `GET /orders/{id}/summary` (read) с уже актуальными данными. Реализуется через:
**MUST NOT:**
- **R-CQRS-SYNC-X1.** **Синхронный UPDATE read-model в command-handler** (прямым INSERT в `order_summary` после save Order). Read-model становится partof write-transaction → теряется decoupling, при rollback всё откатывается. Используй outbox.
- **R-CQRS-SYNC-X2.** **Sync через triggers БД** (PG trigger на `order` UPDATE → INSERT в `order_summary`). Невидимая магия, ломается на bulk-операциях, не работает cross-DB.
- **R-CQRS-SYNC-X3.** **Schema-coupled events.** Если event payload — это generated POJO write-схемы, любой ALTER TABLE на write-side ломает consumers. См. `R-KFK-EVT-X4` (event versioning).

## 6. Уровень и эволюция CQRS
**MUST:**
- **R-CQRS-TIER-1.** **Уровень 1** (Слоёный: Controller → Service → Repository): CQRS не применяется, UseCase-маркеров нет.
- **R-CQRS-TIER-2.** **Уровень 2** (Use Case Pattern): lightweight CQRS — опция уровня, маркеры Command/Query обязательны. Read и write через **один и тот же `<X>Repository`**, но read-методы — в read-only режиме (без блокировок, read-only транзакция).
- **R-CQRS-TIER-3.** **Уровень 3** (DDD + Hexagonal): полный split. Появляется `<X>ViewRepository` (persistence read-проекция) с read-DTO; write — через `<X>Repository` с агрегатом и `FOR UPDATE`.
- **R-CQRS-TIER-4.** **Уровень 3, event-driven**: read-model в отдельной таблице/Redis/ElasticSearch, синхронизация через outbox + Kafka. Дальнейшая эволюция полного split по мере роста нагрузки.
- **R-CQRS-TIER-5.** **Эволюция всегда в одну сторону**: A → B → C → C+. Возврат назад (от C+ к C) — крайне редкий и обычно говорит о неверной first-step decision.
**MUST NOT:**
- **R-CQRS-TIER-X1.** Уровень 1 с CQRS-маркерами «потому что красиво». Маркеры без enforcement (transactional readOnly, отдельный repository) — карго-культ.
- **R-CQRS-TIER-X2.** Event-driven read-model с одним `<X>Repository` для read и write. Если есть отдельная read-инфраструктура (отдельная таблица), то и интерфейс отдельный.

## 7. Антипаттерны
