# Java-ядро — что действует в каждом сервисе

Выжимка решений методологии для Java/Spring-сервиса по Use Case Pattern: то, что надо знать до первого символа кода и что не выводится из самого кода. Полные требования, гейты и примеры — `.claude/docs/backend/<домен>/spec.md` и `references/java/implementation.md`; здесь только база, глубину дают скиллы `ucp-*`. Идентификаторы в скобках — требования, по которым искать подробности.

## Модули и раскладка

- Gradle-модули: `core`, `bootstrap`, `<протокол>-in-adapter` на аудиторию или протокол (`rest-api-in-adapter`, `kafka-in-adapter`, `scheduler-in-adapter`), `<система>-out-adapter` на внешнюю систему (`postgres-out-adapter`, `kafka-out-adapter`). Зависимости: `bootstrap → core ← adapters`; адаптеры друг о друге не знают (`hexagonal/module-per-part`, `hexagonal/in-adapter-per-audience`, `hexagonal/out-adapter-per-system`, `hexagonal/adapters-do-not-know-each-other`).
- В `core` нет слоя bounded context'ов — BC живут в документации и в `adapter/out/postgres/<bc>/`. Пакеты `core`: `domain/{aggregate,entity,valueobject,event,factory,service}`, `usecase/{command,query}/<фича>`, `port/in`, `port/out/{repository,filter,publisher,client}`, `view`, `service`, `exception`, `dto`, `mapper`, `util` (`hexagonal/core-structure`, `ddd-tactical/packages-grouped-by-domain`).
- Внутри адаптера пакеты по роли: `adapter/in/<протокол>/{listener,controller,mapper,security,config}`, `adapter/out/<система>/{client,publisher,mapper,configuration}`; адаптер хранения вкладывает контекст и агрегат — `adapter/out/postgres/<bc>/<агрегат>/`. Классы приёма и отображения несут транспорт в имени: `<Агрегат>KafkaListener`, `<Агрегат>KafkaMapper`, `<Протокол><Агрегат>Controller` (`hexagonal/adapter-structure`).
- `bootstrap` — композиция и конфигурация, `@SpringBootApplication` только там; бизнес-кода в нём нет (`hexagonal/bootstrap-composition-only`).

## Чистота core

- Spring в `core` — только `compileOnly` и только пакеты `org.springframework.stereotype`, `org.springframework.transaction`, `org.springframework.beans.factory` (ровно он, без `.annotation`), `org.springframework.core.task`. Jackson — `compileOnly` для payload'ов. Web, Kafka-транспорт, jOOQ и servlet в `core` не импортируются (`hexagonal/core-free-of-framework`, `hexagonal/di-annotations-in-core`).
- `@Value` запрещён: конфигурация входит через интерфейс в `port/in`, который реализует `@Validated @ConfigurationProperties`-класс в `bootstrap` (`hexagonal/config-enters-core-via-interface`, `validation/config-validated-at-startup`).
- Сгенерированные типы — jOOQ POJO, OpenAPI DTO, модели топиков — не пересекают границу `core`; маппинг живёт в адаптере, порт говорит доменными типами (`hexagonal/no-generated-types-in-core`, `hexagonal/port-speaks-domain-types`).
- Формировать сообщения в `core` (payload события, тело команды партнёру) — норма; транспорт — только в адаптере.

## Операции

- Каждая операция — `record <Операция>Command implements UseCaseCommand<R>` или `record <Операция>Query implements UseCaseQuery<R>` плюс `<Операция>CommandHandler` / `<Операция>QueryHandler`: `@Component`, `@RequiredArgsConstructor`, `@Transactional` (у запроса `readOnly = true`). Голый `UseCase<R>` и имя без суффикса запрещены (`usecase-pattern/command-versus-query`, `usecase-pattern/usecase-implements-marker`, `usecase-pattern/transaction-boundary-on-handler`).
- Запускает операцию только входящий адаптер через `UseCaseDispatcher`; фильтры, конвертеры токена и провайдеры контекста операцией не являются — читают через порт и состояние не меняют; handler не диспатчит и не вызывает другой handler — общая логика уходит в доменный сервис или в `core/service` (`usecase-pattern/entry-calls-dispatcher`, `usecase-pattern/handlers-do-not-call-handlers`).
- Контроллер реализует сгенерированный из OpenAPI `<Tag>Api`, мапит DTO ↔ Command MapStruct-интерфейсом и диспатчит — без логики и без ручных DTO (`hexagonal/controller-dispatches-only`, `usecase-pattern/explicit-mapper-between-layers`, `validation/controller-implements-generated-contract`).
- Запрос читает через модель чтения (`view` + `port/out/filter`), а не поднимает агрегат; команда возвращает минимум (`usecase-pattern/reads-via-read-model`, `usecase-pattern/command-returns-minimum`).

## Домен

- Агрегат — наследник `AggregateRoot<ID>`, сущность — `Entity<ID>`, значение — `record` с `ValueObject`; инварианты и переходы состояния — методами агрегата (`confirm()`, `activate()`), не сеттерами и не в handler'е. Метод агрегата принимает доменные типы, а не объект команды: пакет `domain` не импортирует `usecase` (`ddd-tactical/domain-does-not-know-operations`). Набор атрибутов, приходящий целиком — снимок из внешней системы — заводится значением `<Агрегат>Snapshot` (`ddd-tactical/model-is-not-anemic`, `ddd-tactical/aggregate-root-is-single-entry`, `validation/domain-invariants-in-aggregate`).
- Публичных конструкторов у агрегата нет: создаёт `@UtilityClass <Агрегат>Factory.create(...)`, там же чеканится идентификатор (UUID v7); `@Builder` — служебный канал фабрики и persistence-маппера, гейт `AggregateBuildersUsedOnlyByFactoriesTest` (`ddd-tactical/factory-only-when-needed`, `pg-types/uuid-v7-for-keys`).
- Один репозиторий на корень агрегата — `AggregateRepository<T, ID>` в `port/out/repository`; сущность внутри агрегата сохраняется через агрегат, у неё своего репозитория нет (`ddd-tactical/repository-per-aggregate-root`, `jooq/repository-interface-in-domain`).
- Доменное событие — `record` в `domain/event`, имя в прошедшем времени, регистрирует корень, публикуется после сохранения через outbox (`ddd-tactical/event-named-in-past-tense`, `ddd-tactical/events-registered-by-root`, `kafka/publish-via-outbox`).
- Время — только через источник времени сервиса: статический `DateTimeUtil.currentDateTime()` с `setClock` для тестов или бин над `Clock`, один вариант на сервис; прямые `Instant.now()` / `OffsetDateTime.now()` / `LocalDateTime.now()` запрещены (гейт `checkstyle:RegexpSingleline`); значения усекаются до микросекунд — точность `timestamp` в PostgreSQL (`spring-bootstrap/time-source-is-single-and-swappable`, `pg-types/time-through-clock-service`).

## Исключения

- Доменные — `sealed abstract class <Агрегат>Exception extends RuntimeException` в `core/exception` с вложенными `final`-вариантами по смыслу отказа (`NotFound`, `InvalidStateTransition`); общих корней вроде `DomainException` нет (`error-handling/four-exception-kinds`, `error-handling/domain-exception-named-by-meaning`).
- Интеграционные — семейство на внешнюю систему с видом отказа внутри (`PartnerClientException.Group`, `SberClientException.Kind`: клиентский / серверный / недоступность / таймаут), бросает interceptor клиента в out-adapter (`error-handling/integration-exception-names-system`).
- Catch — в четырёх местах: advice входного адаптера, граница интеграции, обёртка устойчивости, единица работы relay-цикла. В handler'е, сервисе и агрегате перехвата нет (`error-handling/catch-in-three-places-only`, `error-handling/catch-does-not-swallow`).
- `@RestControllerAdvice` — свой у каждого входного адаптера; отображение — исчерпывающий `switch` без `default` по вариантам семейства в статус и `ErrorCode` OpenAPI-контракта; валидация контракта → 400 с перечнем по полям; непредвиденное → 500 с `traceId` (`error-handling/domain-and-validation-mapping`, `error-handling/integration-and-technical-mapping`, `rest-api/error-codes-enumerated`).
- `IllegalStateException` — только в недостижимой ветке исчерпывающего `switch`; `throw new RuntimeException(...)` не бывает (`error-handling/no-bare-base-exceptions`).

## Хранение и интеграции

- Outbound-порт — интерфейс в `core/port/out`, реализация в `<система>-out-adapter` на jOOQ без сгенерированных DAO; отсутствие значения — `Optional`, не исключение; адаптер мапит, а не решает (`hexagonal/outbound-port-interface-in-core`, `jooq/no-generated-daos`, `jooq/absence-and-existence-are-explicit`, `hexagonal/adapter-maps-not-decides`).
- Транзакция одна на операцию и открывается на handler'е; репозиторий своей не открывает (`usecase-pattern/one-usecase-one-transaction`, `jooq/transaction-on-handler`).
- Outbox — агрегат с собственным репозиторием плюс relay-use-case; `published_at` ставится только после ack брокера; relay ловит исключение на одной записи, не на пачке (`kafka/publish-via-outbox`, `kafka/outbox-relay-reads-in-batches`).
- Consumer: ack после записи (`RECORD` или `MANUAL_IMMEDIATE`), `auto-offset-reset: earliest`, дедуп по `eventId`, десериализация в явный тип, DLQ — retry-топик или таблица `kafka_errors`; свои топики создаёт сервис через `KafkaAdmin.NewTopics`; справочники из шины наливаются через API источника (`kafka/manual-offset-commit`, `kafka/consumer-is-idempotent`, `kafka/deserialization-allow-list`, `kafka/reference-data-backfilled-via-api`).
- Фоновая задача — `<Задача>Processing` в `scheduler-in-adapter`: `@Scheduled(fixedRate)` + `@SchedulerLock(lockAtLeastFor = интервал)`, тело — диспатч команды; параметры — `@Validated @ConfigurationProperties`; тик без блокировки допустим только явным исключением в ArchUnit-тесте (`scheduler/single-source-of-tick`, `scheduler/job-parameters-are-typed-config`).

## Стиль

- Lombok везде: `@RequiredArgsConstructor` на бинах, `@Slf4j` вместо ручного логгера, `@Getter` на состоянии; records — для DTO, VO, команд и запросов, на records Lombok не нужен (`java-style/boilerplate-is-generated`, `java-style/no-generation-on-records`, `java-style/builder-used-sparingly`).
- В исходниках нет комментариев, Javadoc и кодов правил — смысл несут имена и структура; имена полные, без сокращений (`java-style/no-comments-in-code`, `java-style/no-rule-codes-or-history-in-code`, `java-style/member-naming`).
- Закрытые иерархии — `sealed` + records, разбор — `switch`-выражением; `default` не добавляется там, где компилятор проверяет полноту (`java-style/exhaustive-switch-on-sealed`).
- Валидация формы входа — Jakarta-аннотации, перенесённые генерацией из OpenAPI, и `@Valid` на границе; повторной проверки внутри нет (`validation/input-validated-at-edge`, `validation/generation-carries-constraints`, `validation/no-revalidation-after-edge`).
- Копия чужих данных — справочник, реплицируемый из внешней системы, — сохраняется как пришла: проверяются идентификатор и метка версии, правила владельца не перепроверяются и запись по ним не бракуется (`validation/replica-is-stored-as-received`).

## Тесты и гейты

- ArchUnit в `bootstrap/src/test`: whitelist Spring в `core`, структура пакетов, суффиксы `Command` / `Query`, билдеры агрегатов только из фабрик, guarded-тики планировщика, handler не зависит от handler'а, нет try-catch в handler'ах кроме relay. Отсутствие теста — критическая находка ревью (`hexagonal/architecture-tests-required`; каталог гейтов — `.claude/docs/_meta/project-gates.md`).
- Юнит-тесты агрегатов и handler'ов — без Spring; интеграционные — Testcontainers PostgreSQL, HTTP через клиент, без брокера и кэша; время — через `setClock`; имя теста описывает сценарий (`test-strategy/test-layers-separated`, `test-strategy/no-broker-or-cache-in-integration-tests`, `test-strategy/test-name-states-scenario`).

## Когда звать скилл

Новая операция — `/ucp-pattern-design`; агрегат, VO, событие — `/ucp-ddd-tactical-design`; Kafka — `/ucp-kafka-design`; ошибки — `/ucp-error-handling-design`; скелет сервиса — `/ucp-bootstrap-design`; ревью — парный `*-review`. Ядро не заменяет спеку домена: перед правкой открой `spec.md` нужного домена по идентификатору.
