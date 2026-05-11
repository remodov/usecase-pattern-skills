# Use Case Pattern — индекс правил

> **Что это.** Сжатый индекс правил `usecase-pattern-style-guide.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с примерами, code-блоками, обоснованием и под-пунктами — `usecase-pattern-style-guide.md`**; открывай её точечно по
> нужному разделу, когда индекса не хватает (под-списки и code-сниппеты сюда не вынесены).
> Коды: `<PREFIX>-<N>` — обязательно, `<PREFIX>-X<N>` — запрещено.

## 1. Используемые абстракции

## 2. Уровни внедрения

## 3. UseCase
**MUST:**
- **R-UC-1.** Класс реализует `UseCase<R>` (или `UseCaseCommand<R>` / `UseCaseQuery<R>`).
- **R-UC-2.** UseCase — Java `record` (или `final class` с финальными полями). UseCase — **immutable data carrier**, без бизнес-логики.
- **R-UC-3.** Имя выражает бизнес-операцию: `CreateOrderUseCase`, `FindOrderByIdUseCase`. Один UseCase = одна операция.
- **R-UC-4.** Параметр `R` — это тип результата, который контроллер вернёт клиенту: на Уровне 1–2 это обычно `JsonBean` или `UseCaseEmptyResult`, на Уровне 3+ — JsonBean или специальный read-DTO.
**MUST NOT:**
- **R-UC-X1.** Логика внутри UseCase (вычисления, обращения к БД, валидация бизнес-правил). Только в Handler.
- **R-UC-X2.** Один UseCase для нескольких операций (`OrderUseCase`, делающий и create, и update — разнести на два).
- **R-UC-X3.** Mutable поля или сеттеры в UseCase.
- **R-UC-X4.** Возвращать `void` — используйте `UseCaseEmptyResult` как `R`.

## 4. UseCaseHandler
**MUST:**
- **R-HND-1.** Реализует `UseCaseHandler<MyUseCase, R>` и метод `useCaseType()` возвращает `MyUseCase.class`.
- **R-HND-2.** Помечен `@Component` (или эквивалентом для DI), чтобы Spring Boot starter подхватил его автоматически.
- **R-HND-3.** На handler команды — `@Transactional`. На handler запроса — `@Transactional(readOnly = true)` (на Уровне 2+).
- **R-HND-4.** Один Handler — один UseCase. Не делать «универсальных» handler-ов на несколько UseCase.
- **R-HND-5.** Все внешние зависимости (репозитории, мапперы, внешние API) приходят через конструктор. **Default — `@RequiredArgsConstructor`** + `private final` поля (см. `JS-6.1` в `java-style-guide.md`). Явный `public Foo(Bar bar)`-constructor допустим только в нестандартных кейсах: валидация DI-аргументов в теле конструктора, вызов `super(...)`, нетривиальная инициализация поля.
**MUST NOT:**
- **R-HND-X1.** Вызывать другой `UseCaseHandler` напрямую — оркестрация идёт через `UseCaseDispatcher` либо через выделенный `UseCaseStep`.
- **R-HND-X2.** Бросать наружу инфраструктурные исключения (`SQLException`, `JOOQException`). Превращайте их в доменные (`OrderException.NotFound`, `PaymentException.AlreadyProcessed`).
- **R-HND-X3.** Иметь поля, изменяемые между вызовами `handle(...)` — Handler stateless.

## 5. UseCaseDispatcher и Controller
**MUST:**
- **R-DSP-1.** Контроллер не вызывает Handler напрямую — только через `UseCaseDispatcher.dispatch(useCase)`.
- **R-DSP-2.** Dispatcher регистрируется через `usecase-pattern-starter` автоматически. Вручную создавать второй диспетчер — только если нужно физическое разделение (например, командный пул и пул запросов).
- **R-DSP-3.** Контроллер делает только: маппинг `Request → UseCase`, `dispatch`, маппинг `Result → Response`, выставление HTTP-кода.
**MUST NOT:**
- **R-DSP-X1.** Бизнес-логика в контроллере (`if (...) throw new ...`, обращение к БД).
- **R-DSP-X2.** Передача `HttpServletRequest`/`Authentication` в UseCase — извлекайте `userId`/`tenantId` в контроллере и кладите в UseCase как обычные поля.

## 6. CQRS (Уровень 2+)
**MUST:**
- **R-CQRS-1.** Команда (меняет состояние) реализует `UseCaseCommand<R>`, запрос (только читает) — `UseCaseQuery<R>`.
- **R-CQRS-2.** На handler-е команды — `@Transactional` (по умолчанию read-write), на handler-е запроса — `@Transactional(readOnly = true)`.
- **R-CQRS-3.** Имя: команда — глагол в инфинитиве (`CreateOrder`, `ConfirmPayment`), запрос — `Find*` / `Get*` / `Search*`.
- **R-CQRS-4.** Чтения возвращают **Read Model**: `OrderView`, материализованное представление, `*View*Repository`. Запись — через `*Repository` с агрегатом / Pojo.
**MUST NOT:**
- **R-CQRS-X1.** Команда возвращает большой read-DTO с подгрузкой связанных сущностей. Команда возвращает только то, что породила: идентификатор, минимальный summary или `UseCaseEmptyResult`.
- **R-CQRS-X2.** Запрос меняет состояние БД (включая «обновление last-seen» или «инкремент counter» в read-handler). Если действительно нужно — это уже команда.

## 7. Слои моделей
- **R-LAY-1.** На входе UseCase — только `JsonBean` (Уровень 1–2) или явные DTO/VO (Уровень 3+). Не передавать сразу `Pojo` БД в UseCase.
- **R-LAY-2.** На выходе UseCase — только `JsonBean` или явный read-DTO, никогда — `Pojo` БД напрямую.
- **R-LAY-3.** Маппинг между слоями — **default: MapStruct**: `@Mapper(componentModel = "spring")` interface, при необходимости `default`-методы внутри интерфейса для нетривиальных конверсий (`@Mapping(qualifiedByName = ...)`). Hand-written `@Component`-маппер допустим **только** когда маппинг выражается DI-зависимыми вызовами или stateful-логикой, что MapStruct не покрывает. «Лень настраивать annotation processor» — не основание для отступления.
**MUST NOT:**
- **R-LAY-X1.** Использовать один и тот же класс для API-слоя и слоя БД (`Order order = …` приходит из БД и сразу уходит в JSON).
- **R-LAY-X2.** Циклические зависимости между мапперами.
- **R-LAY-X3.** Маппинг через рефлексию вручную (`BeanUtils.copyProperties`) или `ObjectMapper` в качестве «универсального маппера».
- **R-LAY-DDD.** Обязательно использовать `ddd-building-blocks` и правила из `ddd-tactical-style-guide.md`. Доменные объекты (`AggregateRoot`, `Entity`, `ValueObject`) **не** утекают в API-слой.

## 8. Hexagonal (Уровень 4)
**MUST:**
- **R-HEX-1.** Структура пакетов: `core/<bc>/...` (UseCase + Domain + порты) и `adapter/in/...`, `adapter/out/...` (REST, Kafka, jOOQ).
- **R-HEX-2.** Зависимости направлены **внутрь**: `core/` не импортирует Spring, jOOQ, REST, Kafka. Только Java-стандарт + `usecase-pattern` + `ddd-building-blocks`.
- **R-HEX-3.** Все внешние взаимодействия — за интерфейсами портов в `core/<bc>/port/`. Реализация — в `adapter/out/...`.
- **R-HEX-4.** Один UseCase может вызываться из нескольких входных адаптеров (REST, Kafka-listener, scheduler). Это нормальная цель Уровня 4 — **не дублировать** Handler.
**MUST NOT:**
- **R-HEX-X1.** Прямой `JdbcTemplate`/`DSLContext` в `core/`. Только через порт.
- **R-HEX-X2.** Импорт `org.springframework.web.*` или `org.jooq.*` в `core/`.

## 9. UseCaseStep — переиспользование
**MUST:**
- **R-STEP-1.** Step реализует `UseCaseStep<I, O>` и метод `execute`.
- **R-STEP-2.** Step используется, когда **одна и та же** логика встречается в ≥ 2 Handler-ах. Один Handler — не повод выносить Step.
**MUST NOT:**
- **R-STEP-X1.** Step внутри Step (вкладывать). Если хочется — это должно быть в Handler.
- **R-STEP-X2.** Step с состоянием. Step — stateless `@Component`.

## 10. Транзакции и события
- **R-TX-1.** `@Transactional` ставится на уровне `UseCaseHandler`, а не Repository, не Service.
- **R-TX-2.** Один UseCase = одна транзакция. Если нужна Saga — это оркестратор в Handler, а каждый шаг — отдельный UseCase или вызов внешнего сервиса с Outbox.
- **R-TX-3.** Публикация доменных событий (Уровень 3+) — через `DomainEventPublisher` после `repository.save(...)`. После публикации `clearDomainEvents()` (см. ddd-tactical-style-guide.md).

## 11. Структура пакетов (опорная)

## 12. Проектные конвенции (default-ы для генерации)

## 13. Чек-лист обзора
