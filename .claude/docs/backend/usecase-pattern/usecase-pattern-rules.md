# Use Case Pattern — индекс правил (язык-нейтральный)

> **Что это.** Сжатый индекс правил Use Case Pattern: код + интент, по разделам — **общий контракт для всех языков**.
> Рабочий вход скиллов: review цитирует код в findings, design сверяется по чек-листу.
> **Реализация по языкам** — в `java/usecase-pattern-style-guide.md` (библиотека `usecase-pattern` + Spring),
> `python/usecase-pattern-style-guide.md` (FastAPI + dataclass-команды + dispatcher); открывай нужный точечно.
> Коды: `<PREFIX>-<N>` — обязательно, `<PREFIX>-X<N>` — запрещено. **Коды общие для всех языков** — меняется только реализация.

Суть паттерна: каждая бизнес-операция — **immutable input-объект (UseCase/Command/Query)** + **stateless Handler**, который её исполняет; вход в систему (контроллер/consumer) не зовёт Handler напрямую, а через **Dispatcher**. Границы слоёв жёсткие: DTO API ≠ доменная модель ≠ модель БД.

## 1. UseCase (input-объект операции)
**MUST:**
- **R-UC-1.** UseCase реализует общий контракт-маркер (`UseCase<R>` / `Command<R>` / `Query<R>`), параметризованный типом результата `R`.
- **R-UC-2.** UseCase — **immutable data carrier**, без бизнес-логики (Java `record`/`final`; Python `@dataclass(frozen=True)`; Go struct без методов-логики).
- **R-UC-3.** Имя выражает бизнес-операцию (`CreateOrder…`, `FindOrderById…`). Один UseCase = одна операция.
- **R-UC-4.** `R` — тип результата, который вход вернёт клиенту (DTO/read-модель или явный «пустой результат»).

**MUST NOT:**
- **R-UC-X1.** Логика внутри UseCase (вычисления, обращения к БД, бизнес-валидация) — только в Handler.
- **R-UC-X2.** Один UseCase на несколько операций — разнести.
- **R-UC-X3.** Mutable-поля или сеттеры в UseCase.
- **R-UC-X4.** Возвращать «ничего»/void — использовать явный empty-result тип как `R`.

## 2. Handler (исполнитель)
**MUST:**
- **R-HND-1.** Handler реализует контракт `Handler<MyUseCase, R>` и объявляет, какой UseCase обрабатывает (метод/маркер/тип).
- **R-HND-2.** Зарегистрирован в DI-контейнере, чтобы dispatcher находил его автоматически.
- **R-HND-3.** Граница транзакции — на Handler: команда — read-write, запрос — read-only.
- **R-HND-4.** Один Handler — один UseCase; без «универсальных» handler-ов.
- **R-HND-5.** Все зависимости (репозитории, мапперы, внешние клиенты) — через конструктор/инъекцию, поля неизменяемы.

**MUST NOT:**
- **R-HND-X1.** Вызывать другой Handler напрямую — оркестрация через Dispatcher либо выделенный Step.
- **R-HND-X2.** Бросать наружу инфраструктурные ошибки (SQL/драйвер/HTTP) — превращать в доменные (cross-ref `R-ERR-WHERE-2b`).
- **R-HND-X3.** Поля, меняющиеся между вызовами — Handler stateless.

## 3. Dispatcher и вход (Controller/Consumer)
**MUST:**
- **R-DSP-1.** Вход не вызывает Handler напрямую — только через `Dispatcher.dispatch(useCase)`.
- **R-DSP-2.** Dispatcher — один на приложение (регистрируется фреймворком/контейнером); второй — только при физическом разделении пулов (команды/запросы).
- **R-DSP-3.** Контроллер делает только: маппинг `Request → UseCase`, `dispatch`, маппинг `Result → Response`, HTTP-код.

**MUST NOT:**
- **R-DSP-X1.** Бизнес-логика в контроллере (`if … throw`, обращение к БД).
- **R-DSP-X2.** Передача транспортных объектов (HTTP-request, auth-principal) в UseCase — извлекать `userId`/`tenantId` в контроллере и класть в UseCase обычными полями.

## 4. CQRS (опция Уровня 2)
**MUST:**
- **R-CQRS-1.** Команда (меняет состояние) — `Command<R>`, запрос (только читает) — `Query<R>`.
- **R-CQRS-2.** Транзакция: команда — read-write, запрос — read-only.
- **R-CQRS-3.** Имя: команда — глагол (`CreateOrder`), запрос — `Find*`/`Get*`/`Search*`.
- **R-CQRS-4.** Чтения возвращают Read Model (view/read-DTO), запись — через repository с агрегатом.

**MUST NOT:**
- **R-CQRS-X1.** Команда возвращает большой read-DTO со связанными сущностями — только идентификатор/минимальный summary/empty.
- **R-CQRS-X2.** Запрос меняет состояние (включая last-seen/counter) — это уже команда.

## 5. Слои моделей
**MUST:**
- **R-LAY-1.** На входе UseCase — DTO/VO API-слоя или явные поля, не модель БД напрямую.
- **R-LAY-2.** На выходе UseCase — DTO/read-DTO, никогда модель БД напрямую.
- **R-LAY-3.** Маппинг между слоями — выделенный маппер (Java: MapStruct по умолчанию; Python: explicit-функции/Pydantic `model_validate`; Go: explicit), не «один класс на все слои».

**MUST NOT:**
- **R-LAY-X1.** Один класс для API-слоя и слоя БД (объект из БД сразу уходит в JSON).
- **R-LAY-X2.** Циклические зависимости между мапперами.
- **R-LAY-X3.** «Универсальный» маппинг рефлексией (`BeanUtils.copyProperties`/`ObjectMapper`-as-mapper).
- **R-LAY-DDD.** Доменные объекты (Aggregate/Entity/ValueObject) не утекают в API-слой (cross-ref `ddd-tactical`).

## 6. Hexagonal (часть Уровня 3)
**MUST:**
- **R-HEX-1.** Структура: `core/<bc>/...` (UseCase + Domain + порты) и `adapter[s]/in/...`, `adapter[s]/out/...`.
- **R-HEX-2.** Зависимости направлены внутрь: `core/` не импортирует фреймворк/ORM/HTTP/брокер.
- **R-HEX-3.** Внешние взаимодействия — за портами в `core/<bc>/port/`; реализация — в `adapter[s]/out/`.
- **R-HEX-4.** Один UseCase вызывается из нескольких входных адаптеров (REST, consumer, scheduler) — Handler не дублировать.

**MUST NOT:**
- **R-HEX-X1.** Прямой доступ к БД-драйверу в `core/` — только через порт.
- **R-HEX-X2.** Импорт web/ORM/брокер-пакетов в `core/`.

## 7. Step — переиспользование
**MUST:**
- **R-STEP-1.** Step реализует `Step<I, O>` с методом `execute`.
- **R-STEP-2.** Step вводится, когда одна и та же логика в ≥ 2 Handler-ах; один Handler — не повод.

**MUST NOT:**
- **R-STEP-X1.** Step внутри Step (вкладывание) — тогда это логика Handler.
- **R-STEP-X2.** Step с состоянием — Step stateless.

## 8. Транзакции и события
**MUST:**
- **R-TX-1.** Граница транзакции — на Handler, не на repository/service.
- **R-TX-2.** Один UseCase = одна транзакция; нужна Saga — оркестратор в Handler, каждый шаг — отдельный UseCase/внешний вызов с Outbox (cross-ref `distributed`).
- **R-TX-3.** Публикация доменных событий (Уровень 3) — после `repository.save(...)`, затем очистка событий агрегата (cross-ref `ddd-tactical`).

## 9. Чек-лист обзора
См. язык-specific style-guide (`<lang>/usecase-pattern-style-guide.md`) — там реализация каждого правила и чеклист подключения.
