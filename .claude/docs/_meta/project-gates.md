# Гейты проекта

Каталог проверок, которые методология **определяет сама** и которые
`ucp-*-bootstrap-design` заводит в сервисе. Это ответ на вопрос волны 4: две
трети требований корпуса держались ревью не потому, что нарушение неуловимо,
а потому, что подходящего готового правила не было. Там, где нарушение видно
в артефакте, который мы контролируем — DDL, конфигурация, манифест
развёртывания, — проверку пишем сами.

**Правило честности.** Требование ссылается на гейт из этого каталога только
если проверка описана здесь достаточно точно, чтобы её сгенерировать. Имя
чужого правила линтера, в существовании которого нет уверенности, гейтом
не является — такое требование остаётся с гейтом `ревью`.

**Граница.** Эти проверки читают файлы. Всё, что определяется поведением под
нагрузкой, смыслом предметной области или порядком релизов, они не видят —
и это записано в поле «Не ловит» каждого требования.

## `script:ddl-check` — проверка схемы и миграций

Читает файлы миграций (`db/changelog/**`, `db/migrations/**`, `migrations/**`)
и разбирает объявления таблиц, колонок, индексов и ограничений.

| Проверка | Что ищет | Закрывает |
| --- | --- | --- |
| `money-not-float` | колонка с денежным именем (`*_amount`, `*_price`, `*_rate`, `*_sum`, `*_cost`) объявлена типом с плавающей точкой или типом `money` | `pg-types/money-is-numeric` |
| `timestamp-with-zone` | колонка момента (`*_at`) объявлена без часового пояса | `pg-types/business-time-is-timestamptz` |
| `uuid-native-type` | колонка с именем на `*_uuid`/`*_id` объявлена строкой длиной 36 | `pg-types/uuid-is-uuid-type` |
| `no-varchar-255` | объявлен `varchar(255)` | `pg-types/text-by-default` |
| `identity-not-serial` | объявлен `serial`/`bigserial` | `pg-types/pk-bigint-identity` |
| `pk-is-bigint` | первичный ключ объявлен типом `integer` | `pg-types/pk-bigint-identity` |
| `boolean-is-boolean` | колонка с приставкой `is_`/`has_`/`can_` объявлена не булевым типом | `pg-types/boolean-is-boolean` |
| `no-char-flag` | объявлен `char(1)` с ограничением из двух значений | `pg-types/boolean-is-boolean` |
| `snake-case-identifiers` | идентификатор не в нижнем регистре через подчёркивание либо в кавычках | `pg-naming/snake-case-no-quotes` |
| `reserved-words` | имя совпадает со словом из списка зарезервированных | `pg-naming/no-reserved-words` |
| `identifier-length` | имя длиннее предела или два имени совпадают после обрезки | `pg-naming/short-names-consistent-abbreviations` |
| `boolean-name-prefix` | булева колонка названа без приставки-утверждения | `pg-naming/boolean-column-prefix` |
| `time-column-suffix` | колонка момента без суффикса `_at`, даты — без `_on` | `pg-naming/time-column-suffix` |
| `duration-unit` | колонка длительности без единицы в имени | `pg-naming/duration-unit-in-name` |
| `index-name-prefix` | индекс или ограничение без принятого префикса по типу | `pg-naming/index-constraint-prefix` |
| `constraint-explicit-name` | внешний ключ или проверочное ограничение без явного имени | `pg-naming/index-constraint-prefix` |
| `soft-delete-moment` | колонка мягкого удаления объявлена булевой | `pg-naming/soft-delete-keeps-moment` |
| `document-column-name` | колонка документа названа обобщённо (`data`, `info`, `details`) | `pg-naming/document-column-meaningful-name` |
| `view-suffix` | представление без суффикса | `pg-naming/view-suffix` |
| `lock-timeout` | изменение таблицы без предшествующего ограничения ожидания блокировки | `pg-migrations/lock-timeout-required` |
| `index-concurrently` | создание или удаление индекса без параллельного режима | `pg-migrations/index-concurrently` |
| `no-redundant-index` | индекс по полю, которое уже является левым префиксом другого | `pg-indexes/no-redundant-prefix-index` |
| `fk-has-index` | внешний ключ без индекса по нему | `pg-indexes/index-foreign-keys` |
| `fillfactor-on-hot-tables` | таблица с интенсивными обновлениями без запаса места на странице | `pg-runtime/fillfactor-for-hot-updates` |
| `autovacuum-per-table` | большая горячая таблица без пер-таблично сниженного порога фоновой очистки | `pg-runtime/autovacuum-tuning-per-table` |
| `rename-column-single-step` | переименование колонки одним изменением | `pg-migrations/rename-column-expand-contract` |
| `table-drop-in-migration` | удаление или переименование таблицы | `pg-migrations/table-drop-after-release` |
| `unbounded-data-change` | изменение или удаление данных без ограничения выборки | `pg-migrations/batched-data-migration` |
| `rollback-drops-data` | секция отката удаляет колонку или таблицу | `pg-migrations/no-down-migrations` |
| `no-full-rebuild` | полная перестройка таблицы в миграции | `pg-runtime/no-vacuum-full-in-production` |
| `partition-key-in-pk` | первичный ключ секционированной таблицы без ключа секционирования | `pg-partitioning/pk-includes-partition-key` |

## `script:config-check` — проверка конфигурации сервиса

Читает конфигурацию приложения по профилям и сверяет значения, от которых
зависит поведение под отказом.

| Проверка | Что ищет | Закрывает |
| --- | --- | --- |
| `broker-producer-idempotent` | отправитель без идемпотентного режима или с ослабленным подтверждением | `kafka/producer-is-idempotent` |
| `broker-manual-commit` | включено автоматическое подтверждение обработки, либо режим подтверждения не «вручную» и не «после записи» | `kafka/manual-offset-commit` |
| `broker-offset-earliest` | у критичного потребителя чтение начинается с конца | `kafka/earliest-offset-for-critical-consumers` |
| `broker-missing-topics-fatal` | отсутствие топика не останавливает старт | `kafka/missing-topics-are-fatal` |
| `broker-deserialization-allow-list` | десериализатор объектов без явного списка типов, либо разрешены произвольные типы | `kafka/deserialization-allow-list` |
| `broker-transport-secure` | в промышленном профиле открытый протокол | `kafka/transport-security-and-acls` |
| `cache-per-cache-ttl` | кеш без собственного срока жизни или с общим сроком на все | `caching/explicit-ttl-per-cache` |
| `cache-distributed-in-production` | в промышленном профиле кеш в памяти процесса | `caching/distributed-cache-in-production` |
| `cache-serialization-text` | настроена двоичная сериализация значений | `caching/values-serialized-as-json` |
| `pool-settings-complete` | пул без размера, времени ожидания, срока жизни или порога утечек | `pg-runtime/pool-settings-complete` |
| `pool-leak-detection` | обнаружение утечек соединений отключено | `pg-runtime/leak-detection-enabled` |
| `pool-single-per-database` | объявлено несколько пулов к одной базе | `pg-runtime/single-pool-per-database` |
| `management-port-separate` | эндпоинты обслуживания на рабочем порту | `observability/separate-management-port` |
| `management-endpoints-listed` | эндпоинты обслуживания публикуются целиком | `observability/management-endpoints-restricted` |
| `shutdown-graceful-enabled` | плавная остановка веб-сервера не включена | `graceful-shutdown/web-server-graceful-enabled` |
| `shutdown-budget-consistent` | сумма фаз остановки превышает общий бюджет | `graceful-shutdown/shutdown-budget-is-explicit` |
| `resilience-timeout-hierarchy` | тайм-ауты не заданы или заданы противоречиво | `resilience/timeout-hierarchy` |
| `resilience-instance-per-system` | обвязка устойчивости с общим именем для разных систем | `resilience/instance-names-match-system` |
| `consumer-shutdown-timeout` | потребитель без ограничения времени остановки | `graceful-shutdown/consumer-finishes-batch` |
| `executor-awaits-termination` | пул фоновых задач без ожидания завершения при остановке | `graceful-shutdown/background-tasks-finish-iteration` |
| `no-schema-autosync` | автоматическая синхронизация схемы включена в любом профиле | `nest-bootstrap/datasource-and-migrations`, `typeorm/schema-via-reviewed-migrations` |
| `event-serialization-visible-fields` | сериализация событий не видит полей записей | `spring-bootstrap/event-serialization-sees-record-fields` |
| `payload-not-double-encoded` | объектная сериализация значения при уже подготовленной строке | `spring-bootstrap/no-double-encoding-of-payload` |
| `cache-names-are-namespaces` | имена кешей не уникальны или не в принятом стиле | `caching/cache-name-is-namespace` |
| `no-hardcoded-endpoints` | адрес внешней системы или брокера задан литералом вместо подстановки | `kafka/settings-are-typed-and-external` |

## `script:manifest-check` — проверка манифестов развёртывания

Читает манифесты развёртывания и сверяет параметры остановки и проверок
состояния.

| Проверка | Что ищет | Закрывает |
| --- | --- | --- |
| `termination-grace-period` | бюджет остановки не задан явно или меньше суммы фаз | `graceful-shutdown/shutdown-budget-is-explicit` |
| `prestop-delay` | нет паузы перед остановкой | `graceful-shutdown/prestop-delay` |
| `probes-split` | проверки живости и готовности указывают на один эндпоинт | `graceful-shutdown/readiness-off-first` |
| `rolling-update-keeps-capacity` | обновление допускает снижение числа экземпляров | `graceful-shutdown/rolling-update-keeps-capacity` |
| `container-non-root` | запуск от суперпользователя | `security/image-pinned-and-nonroot` |
| `image-pinned` | базовый образ по подвижной метке | `security/image-pinned-and-nonroot` |

## `script:test-lint` — проверка тестов

Читает исходники тестов и ловит приёмы, делающие набор недетерминированным или
проверяющим меньше заявленного.

| Проверка | Что ищет | Закрывает |
| --- | --- | --- |
| `no-waiting-in-tests` | пауза, опрос в цикле или ожидание с повторами внутри теста | `test-strategy/tests-are-synchronous-and-deterministic` и одноимённые требования остальных треков |
| `no-real-clock-in-tests` | обращение к настоящим часам или генератору идентификаторов в тесте и в доменном коде | те же требования |
| `no-broker-container-in-integration` | контейнер брокера или кеша в базовой подготовке интеграционного теста | `test-strategy/no-broker-or-cache-in-integration-tests` и одноимённые |
| `no-schema-recreate-between-tests` | пересоздание схемы или автоматическая синхронизация между тестами | `test-strategy/schema-once-data-cleaned` и одноимённые |
| `no-mocking-ports-in-integration` | подмена порта репозитория или обработчика в тесте, помеченном интеграционным | `python-test-strategy/no-mocking-business-logic`, `go-test-strategy/test-layers-separated`, `node-test-strategy/no-mocking-business-logic` |
| `test-name-shape` | имя теста не по принятой форме «действие — условие — ожидание» | требования об именовании тестов в четырёх треках |
| `no-manual-token-assembly` | сборка токена авторизации в теле теста вместо общего помощника | требования о единой тестовой авторизации |

## `archunit:*` и аналоги — структурные проверки кода

Структурные проверки живут в языке: архитектурный тест в Java, контракт
импортов в Python, запрет импортов в Go, правило слоёв в Node. Их имена
перечислены в самих требованиях; `ucp-bootstrap-design` заводит базовый набор
и добавляет по одному тесту на каждое требование, которое на него ссылается.

## Структурные проверки, которые заводит bootstrap

Помимо базового набора, `ucp-bootstrap-design` генерирует эти правила — они
закрывают требования, которые иначе остаются на ревью.

| Правило | Что проверяет | Закрывает |
| --- | --- | --- |
| `archunit:QueryHandlersDoNotWriteTest` | обработчик запроса не вызывает изменяющих методов репозитория | `usecase-pattern/query-does-not-mutate` |
| `archunit:NoRetryAtEdgeTest` | обработчик ошибок границы не выполняет повторов | `error-handling/no-retry-at-edge` |
| `archunit:NoCacheOnAuthorizationTest` | результаты проверки прав не кешируются | `caching/no-caching-authorization-results` |
| `archunit:NoExternalCallInTransactionTest` | внутри транзакции нет вызовов внешних систем | `pg-runtime/short-transactions` |
| `archunit:ScheduledMethodsAreGuardedTest` | каждый `@Scheduled` помечен `@SchedulerLock`; тик без блокировки — только явным исключением в тесте | `scheduler/single-source-of-tick` |

Правила именуются по требованию, которое закрывают: связь должна читаться из
имени упавшего теста, без похода в конфигурацию.

## Архитектурные тесты (Java)

Структурные правила, которые `ucp-bootstrap-design` заводит в модуле
архитектурных тестов. Имя теста повторяет требование: связь «упавший тест →
нарушенное требование» читается без похода в конфигурацию.

| Правило | Что проверяет | Закрывает |
| --- | --- | --- |
| `archunit:AdapterImplementsPortTest` | модуль out-adapter на каждую внешнюю систему | `hexagonal/out-adapter-per-system` |
| `archunit:AdaptersDoNotDependOnEachOtherTest` | адаптеры не знают друг о друге | `hexagonal/adapters-do-not-know-each-other` |
| `archunit:AggregateRootIsEntryPointTest` | корень агрегата — единственная точка входа | `ddd-tactical/aggregate-root-is-single-entry` |
| `archunit:DomainDoesNotDependOnUseCasesTest` | домен не зависит от слоя операций: метод корня принимает доменные типы, не команду | `ddd-tactical/domain-does-not-know-operations` |
| `archunit:AggregatesReferenceByIdTest` | сущность не хранит ссылок на чужие агрегаты | `ddd-tactical/no-object-references-across-aggregates` |
| `archunit:BootstrapHasNoBusinessLogicTest` | bootstrap — только композиция | `hexagonal/bootstrap-composition-only` |
| `archunit:CommandsAndQueriesAreNamedTest` | каждая операция — команда или запрос, имя кончается на `Command` / `Query` | `usecase-pattern/command-versus-query` |
| `archunit:ControllersDoNotUseRepositoriesTest` | контроллер реализует сгенерированный контракт и диспатчит | `hexagonal/controller-dispatches-only` |
| `archunit:ControllersHaveAuthorizationTest` | у каждого эндпоинта есть проверка роли | `auth-patterns/every-endpoint-has-role-check` |
| `archunit:ControllersHaveNoBusinessLogicTest` | контроллер только отображает и диспатчит | `usecase-pattern/controller-maps-and-dispatches` |
| `archunit:ControllersImplementGeneratedApiTest` | контроллер реализует сгенерированный контракт | `validation/controller-implements-generated-contract` |
| `archunit:ControllersReturnDtoTest` | маппинг REST ↔ домен живёт в отдельном классе in-adapter'а | `hexagonal/rest-mapping-in-adapter` |
| `archunit:ControllersUseDispatcherTest` | вход зовёт диспетчер, а не обработчик | `usecase-pattern/entry-calls-dispatcher` |
| `archunit:ControllersValidateInputTest` | контракт входа проверяется на границе декларативно | `validation/input-validated-at-edge` |
| `archunit:CoreStructureTest` | агрегаты в `domain.aggregate`, сущности в `domain.entity`, порты — интерфейсы в `port.*` | `hexagonal/core-structure`, `ddd-tactical/packages-grouped-by-domain` |
| `archunit:CoreUsesOnlyWhitelistedFrameworkPackagesTest` | core импортирует из фреймворка только whitelist DI и транзакций, инфраструктуру — никогда | `hexagonal/core-free-of-framework`, `hexagonal/di-annotations-in-core`, `hexagonal/config-enters-core-via-interface`, `hexagonal/no-generated-types-in-core`, `hexagonal/port-exceptions-in-core` |
| `archunit:EntitiesHaveNoSettersTest` | конструктор сущности проверяет инварианты | `ddd-tactical/entity-constructor-validates` |
| `archunit:EntitiesUseIdentityEqualityTest` | сущность равна себе по идентификатору | `ddd-tactical/entity-equality-by-identity` |
| `archunit:EntityIdIsFinalTest` | идентификатор стабилен и неизменяем | `ddd-tactical/identity-is-immutable` |
| `archunit:EventsAreImmutableTest` | событие — неизменяемый тип с базовыми полями | `ddd-tactical/event-is-immutable-record` |
| `archunit:EventsHaveNoAggregateRefsTest` | событие несёт бизнес-контекст, а не ссылки | `ddd-tactical/event-carries-business-context` |
| `archunit:EventsRegisteredByRootTest` | события регистрирует корень | `ddd-tactical/events-registered-by-root` |
| `archunit:GeneratedDtoStaysInAdapterTest` | наружу отдаются доменные значения | `payment-integration/domain-values-outside-adapter`, `resilience/mapper-between-client-and-port` |
| `archunit:HandlersAreStatelessTest` | обработчик без состояния, зависимости — через конструктор | `usecase-pattern/handler-is-stateless` |
| `archunit:HandlersDeclareUseCaseTest` | обработчик объявляет свою операцию и обрабатывает только её | `usecase-pattern/one-handler-one-usecase` |
| `archunit:HandlersDoNotDependOnHandlersTest` | обработчики не зависят друг от друга; `UseCaseDispatcher` — только во входящих адаптерах, в core его нет | `usecase-pattern/handlers-do-not-call-handlers` |
| `archunit:HexagonalLayersTest` | частичного hexagonal не бывает | `hexagonal/architecture-tests-required`, `hexagonal/no-partial-adoption` |
| `archunit:MappersStayInPersistenceTest` | мапперы делегируют, а не наследуют | `jooq/mappers-delegate` |
| `archunit:NestedFieldsAreValidatedTest` | вложенные структуры проверяются рекурсивно | `validation/nested-validated-recursively` |
| `archunit:NoAdHocDslContextTest` | контекст доступа — единственный бин | `jooq/dsl-context-is-singleton-bean` |
| `archunit:AggregateBuildersUsedOnlyByFactoriesTest` | у агрегата нет публичного конструктора; `builder()` зовут только фабрика и persistence-маппер | `java-style/builder-used-sparingly`, `ddd-tactical/factory-only-when-needed` |
| `archunit:NoCacheableOnCommandsTest` | на пути записи кеша нет | `caching/no-cache-on-write-path` |
| `archunit:NoChainedTransactionManagerTest` | распределённых транзакций не бывает | `distributed-patterns/no-two-phase-commit` |
| `archunit:NoCyclicDependenciesTest` | мапперы не образуют циклов | `usecase-pattern/no-cyclic-mappers` |
| `archunit:NoDirectBrokerSendInHandlersTest` | исходящие события идут через таблицу исходящих | `distributed-patterns/outbox-for-outgoing-events` |
| `archunit:NoDirectKafkaSendInHandlersTest` | доменные события публикуются через надёжную публикацию | `kafka/publish-via-outbox` |
| `archunit:NoFieldInjectionTest` | зависимости внедряются через конструктор | `jooq/constructor-injection` |
| `archunit:NoGeneratedDaoUsageTest` | сгенерированные объекты доступа не используются | `jooq/no-generated-daos` |
| `archunit:NoManualJwtParsingTest` | токен проверяется библиотекой, а не руками | `auth-patterns/token-validated-by-library`, `security/token-validated-by-library` |
| `archunit:NoOtherPersistenceApisTest` | иных механизмов доступа к базе не применяется | `jooq/no-other-persistence-frameworks`, `spring-bootstrap/single-persistence-mechanism` |
| `archunit:NoPersistenceTypesInApiTest` | на входе и выходе операции — объекты слоя границы | `usecase-pattern/layer-models-do-not-leak` |
| `archunit:NoPlainSqlTest` | запросы строятся типобезопасно | `jooq/type-safe-query-building` |
| `archunit:NoProgrammaticProfileActivationTest` | профиль активируется снаружи, а не кодом | `spring-bootstrap/profile-activated-externally` |
| `archunit:NoThreadSleepInListenersTest` | обработчик не блокирует цикл опроса | `kafka/listener-does-not-block-poll-loop` |
| `archunit:NoTryCatchInHandlersTest` | перехват — граница, интеграция, устойчивость и relay-цикл на единицу работы; в обычном handler'е — нет | `error-handling/catch-in-three-places-only` |
| `archunit:NoValidationAnnotationsInDomainTest` | доменные инварианты живут в агрегате | `validation/domain-invariants-in-aggregate` |
| `archunit:OutAdaptersAreProtectedTest` | исходящие вызовы к внешним системам защищены полным набором | `resilience/outbound-calls-fully-protected` |
| `archunit:PortsAreInterfacesTest` | outbound-порт — интерфейс в core | `hexagonal/outbound-port-interface-in-core` |
| `archunit:PortsUseDomainTypesTest` | порт оперирует доменными типами | `hexagonal/port-speaks-domain-types` |
| `archunit:QueriesReturnReadModelsTest` | запрос возвращает модель чтения, а не агрегат | `cqrs/query-returns-read-model` |
| `archunit:QueryHandlersAreReadOnlyTest` | запрос только читает | `cqrs/query-is-read-only` |
| `archunit:RepositoriesReturnDomainTypesTest` | методы репозитория названы в терминах домена | `ddd-tactical/repository-speaks-domain`, `jooq/repository-speaks-domain-types` |
| `archunit:RepositoryPortsInDomainTest` | порт репозитория объявлен в домене | `ddd-tactical/repository-port-in-domain`, `jooq/repository-interface-in-domain` |
| `archunit:ResilienceAnnotationsOnAdaptersTest` | размыкатель стоит на публичном методе адаптера | `resilience/breaker-on-adapter-method` |
| `archunit:StepsAreStatelessTest` | шаги не вкладываются и не хранят состояние | `usecase-pattern/steps-flat-and-stateless` |
| `archunit:TransactionalOnHandlersOnlyTest` | транзакция объявляется на обработчике | `jooq/transaction-on-handler` |
| `archunit:UseCasesAreImmutableTest` | объект операции неизменяем и не содержит логики | `usecase-pattern/usecase-is-immutable-carrier` |
| `archunit:UseCasesDeclareResultTest` | результат объявлен типом, пустой результат — явно | `usecase-pattern/explicit-result-type` |
| `archunit:UseCasesHaveNoTransportTypesTest` | транспортные объекты не попадают в операцию | `usecase-pattern/no-transport-objects-in-usecase` |
| `archunit:UseCasesImplementMarkerTest` | операция объявляет общий контракт с типом результата | `usecase-pattern/usecase-implements-marker` |
| `archunit:ValueObjectsAreImmutableTest` | значение помечено как значение и неизменяемо | `ddd-tactical/value-object-is-immutable` |
| `archunit:ValueObjectsHaveNoIdTest` | значение не имеет идентификатора и жизненного цикла | `ddd-tactical/value-has-no-identity` |
| `archunit:ValueObjectsUseValueEqualityTest` | значение равно по всем значимым полям | `ddd-tactical/value-equality-by-all-fields` |

## Контракты импортов (Python)

Контракты, которые `ucp-py-bootstrap-design` объявляет в конфигурации проекта.

| Правило | Что проверяет | Закрывает |
| --- | --- | --- |
| `import-linter:adapters-independent` | адаптеры не знают друг о друге | `hexagonal/adapters-do-not-know-each-other`, `hexagonal/out-adapter-per-system` |
| `import-linter:bootstrap` | bootstrap — только композиция | `hexagonal/bootstrap-composition-only` |
| `import-linter:contracts` | модуль сборки на каждую часть | `hexagonal/module-per-part` |
| `import-linter:core-independence` | порт репозитория объявлен в домене | `ddd-tactical/repository-port-in-domain`, `hexagonal/core-free-of-framework`, `hexagonal/di-annotations-in-core`, `hexagonal/config-enters-core-via-interface`, `hexagonal/no-generated-types-in-core`, `hexagonal/port-exceptions-in-core`, `sqlalchemy/port-in-core-implementation-in-adapter`, `validation/domain-invariants-in-aggregate` |
| `import-linter:handlers` | обработчики не зовут друг друга напрямую | `usecase-pattern/handlers-do-not-call-handlers` |
| `import-linter:in-adapter` | контроллер реализует сгенерированный контракт и диспатчит | `hexagonal/controller-dispatches-only`, `usecase-pattern/entry-calls-dispatcher` |
| `import-linter:layers` | пакеты группируются по домену, а не по слоям | `codegen/orm-draft-is-finished-by-hand`, `ddd-tactical/packages-grouped-by-domain`, `hexagonal/architecture-tests-required`, `hexagonal/no-partial-adoption`, `python-bootstrap/layout-directs-dependencies-inward`, `sqlalchemy/orm-models-are-anemic-and-in-adapter`, `usecase-pattern/layer-models-do-not-leak`, `usecase-pattern/no-cyclic-mappers` |
| `import-linter:ports` | outbound-порт — интерфейс в core | `hexagonal/outbound-port-interface-in-core` |

## Правила зависимостей (Node)

Правила, которые `ucp-node-bootstrap-design` объявляет в конфигурации проверки
зависимостей.

| Правило | Что проверяет | Закрывает |
| --- | --- | --- |
| `dependency-cruiser:bootstrap-only-composition` | bootstrap — только композиция | `hexagonal/bootstrap-composition-only` |
| `dependency-cruiser:no-adapter-to-adapter` | адаптеры не знают друг о друге | `hexagonal/adapters-do-not-know-each-other`, `hexagonal/out-adapter-per-system` |
| `dependency-cruiser:no-circular` | мапперы не образуют циклов | `usecase-pattern/no-cyclic-mappers` |
| `dependency-cruiser:no-controller-to-repository` | контроллер реализует сгенерированный контракт и диспатчит | `hexagonal/controller-dispatches-only` |
| `dependency-cruiser:no-core-to-adapter` | порт репозитория объявлен в домене | `ddd-tactical/repository-port-in-domain`, `hexagonal/core-free-of-framework`, `hexagonal/di-annotations-in-core`, `hexagonal/config-enters-core-via-interface`, `hexagonal/no-generated-types-in-core`, `hexagonal/port-exceptions-in-core`, `nest-bootstrap/inject-by-port-tokens`, `nest-bootstrap/layout-directs-dependencies-inward`, `typeorm/entities-are-anemic-data-mapper`, `typeorm/port-in-core-implementation-in-adapter` |
| `dependency-cruiser:no-cross-module` | модуль сборки на каждую часть | `hexagonal/module-per-part` |
| `dependency-cruiser:no-layer-violation` | пакеты группируются по домену, а не по слоям | `ddd-tactical/packages-grouped-by-domain`, `hexagonal/architecture-tests-required`, `hexagonal/no-partial-adoption`, `usecase-pattern/layer-models-do-not-leak` |
| `dependency-cruiser:ports-in-core` | outbound-порт — интерфейс в core | `hexagonal/outbound-port-interface-in-core` |

## `script:openapi-lint` — проверка описания контракта

Читает описание интерфейса сервиса и сверяет форму путей, параметров, ответов
и ошибок.

| Правило | Что проверяет | Закрывает |
| --- | --- | --- |
| `script:openapi-lint` | путь в нижнем регистре через дефис | `rest-api/action-endpoints-shape`, `rest-api/arrays-as-repeated-parameters`, `rest-api/collection-response-shape`, `rest-api/deprecation-with-sunset`, `rest-api/error-body-follows-standard`, `rest-api/error-codes-enumerated`, `rest-api/error-status-codes-limited`, `rest-api/file-upload-and-download`, `rest-api/json-field-naming`, `rest-api/long-running-via-polling`, `rest-api/nesting-max-two-levels`, `rest-api/no-nulls-in-successful-response`, `rest-api/operation-has-summary`, `rest-api/operation-id-and-tags`, `rest-api/pagination-forms`, `rest-api/path-lowercase-kebab-case`, `rest-api/query-parameter-naming`, `rest-api/unique-path-parameter-names`, `rest-api/version-in-path` |

## `script:arch-check` — проверка архитектурного корпуса

Читает документы корпуса `architecture/` и сверяет их согласованность.
Запускается из корня корпуса, а не из репозитория сервиса.

| Правило | Что проверяет | Закрывает |
| --- | --- | --- |
| `script:arch-check` | запись сервиса в реестре полна и однозначна | `arch/archived-service-not-in-live-processes`, `arch/context-links-are-symmetric`, `arch/contracts-are-versioned`, `arch/failure-points-have-compensation`, `arch/index-documents-are-tables`, `arch/one-publisher-per-event`, `arch/process-has-orchestrator-or-note`, `arch/process-step-matches-service-use-case`, `arch/registry-entry-is-complete`, `arch/service-card-matches-spec`, `arch/shared-kernel-needs-adr`, `arch/single-owner-per-entity`, `arch/sync-steps-are-declared` |

## Прогоны сквозных сценариев

Две джобы конвейера, которые заводит `ucp-e2e-pipeline-design`. В отличие от
проверок выше они запускаются не на изменении кода, а вокруг выкатки.

| Джоба | Когда идёт | Что делает | Закрывает требования |
| --- | --- | --- | --- |
| `ci:e2e-smoke` | после каждого деплоя, на том же стенде | гоняет смоук-набор в объявленном бюджете времени; красный результат блокирует продвижение сборки | `e2e-pipeline/smoke-after-every-deploy`, `e2e-pipeline/red-smoke-blocks-promotion`, `e2e-suite/run-time-is-budgeted` |
| `ci:e2e-regression` | по расписанию и перед релизом, на предпродакшене | гоняет полный набор, публикует отчёт и сохраняет следы падений | `e2e-pipeline/regression-on-schedule-and-before-release`, `e2e-suite/failure-leaves-evidence` |

Джоба, которая запускается, но чей результат ничего не блокирует и никем не
читается, требование не закрывает: это уведомление, а не гейт.

## Правила сторонних инструментов — сверено 4 сентября 2026

Имена правил чужих анализаторов, на которые ссылаются требования. Мы их не
пишем и не контролируем: **имя, которого нет в пинуемой версии, делает
требование ложно закрытым**. Ниже — результат сверки с самими инструментами,
а не с памятью: каждое имя проверено запуском или чтением реестра правил
инструмента указанной версии.

| Инструмент | Версия сверки | Правила |
| --- | --- | --- |
| `checkstyle` | 10.26.1 | `AbbreviationAsWordInName`, `ArrayTypeStyle`, `AvoidStarImport`, `BooleanExpressionComplexity`, `CommentsIndentation`, `ConstantName`, `LineLength`, `LocalVariableName`, `MethodName`, `ModifierOrder`, `PackageName`, `RedundantModifier`, `RegexpSingleline`, `TypeName`, `UnusedImports`, `WhitespaceAround` |
| `errorprone` | 2.50.0 | `JavaLocalDateTimeGetNano`, `MissingCasesInEnumSwitch`, `SystemOut`, `ThrowSpecificExceptions` |
| `spotbugs` | 4.9.3 + findsecbugs 1.14.0 | `DE_MIGHT_IGNORE`, `REC_CATCH_EXCEPTION` (spotbugs); `ECB_MODE`, `PREDICTABLE_RANDOM`, `WEAK_MESSAGE_DIGEST_MD5`, `WEAK_MESSAGE_DIGEST_SHA1` (findsecbugs) |
| `ruff` | 0.16.6 | `ASYNC210`, `ASYNC230`, `ASYNC251`, `B006`, `B909`, `BLE001`, `DTZ001`, `DTZ005`, `E722`, `E741`, `ERA001`, `F401`, `F403`, `G003`, `I001`, `N801`, `N802`, `N806`, `PGH003`, `PGH004`, `PLW1508`, `PTH118`, `RUF006`, `S305`, `S311`, `S324`, `S608`, `SIM108`, `SIM115`, `T201`, `TID252`, `UP007`, `UP032` |
| `eslint` | 9.39.5, typescript-eslint 8.69.0, plugin-import 2.x | ядро: `complexity`, `eqeqeq`, `no-console`, `no-empty`, `no-restricted-imports`, `no-restricted-properties`, `no-unused-vars`, `no-var`, `require-await`; `@typescript-eslint/`: `ban-ts-comment`, `explicit-module-boundary-types`, `naming-convention`, `no-explicit-any`, `no-floating-promises`, `no-misused-promises`, `no-non-null-assertion`, `no-unsafe-argument`, `prefer-readonly`; `import/`: `no-cycle`, `order`, `no-default-export`; `n/`: `no-process-env` |
| `golangci-lint` | 2.13.2 | `containedctx`, `contextcheck`, `depguard`, `errcheck`, `errorlint`, `exhaustive`, `forbidigo`, `gocritic`, `gosec`, `govet`, `lll`, `nilnil`, `revive`, `staticcheck`, `wsl`; `goimports` — **форматтер**, включается разделом `formatters`, не `linters` |
| `squawk` | 2.64.0 | `adding-required-field`, `ban-drop-column`, `changing-column-type`, `constraint-missing-not-valid`, `require-concurrent-index-creation`, `require-concurrent-index-deletion`, `transaction-nesting` |
| `mypy`, `gitleaks`, `trivy` | — | ссылок на отдельные правила нет: требования называют режим (`strict`, набор по умолчанию, `config` / `image`), а не имя правила |

**Что сверка изменила.** Шесть имён не существовали в актуальных версиях, и
требования, на них ссылавшиеся, были закрыты только на бумаге:

| Имя | Что с ним | Как поправлено |
| --- | --- | --- |
| `ruff:ASYNC101` | удалено, блокирующие вызовы разнесены по `ASYNC2xx` | гейт перечисляет `ASYNC210`, `ASYNC230`, `ASYNC251` |
| `ruff:ASYNC102` | удалено; правила против проглоченной отмены в ruff нет | требование вернулось к `ревью`, покрытие `нет` |
| `golangci-lint:loopclosure` | убран в v2, анализатор живёт внутри `govet` | гейт — `govet` |
| `golangci-lint:stylecheck` | убран в v2, слит в `staticcheck` | гейт — `staticcheck` |
| `spotbugs:WEAK_MESSAGE_DIGEST` | единого имени нет, есть по алгоритмам | гейт — `WEAK_MESSAGE_DIGEST_MD5` и `..._SHA1` |
| `errorprone:StringConcatToLogger` | такого правила не существует | java-часть требования вернулась к `ревью` |

**Имена в eslint неполны без префикса плагина.** `no-default-export` живёт
только как `import/no-default-export`, `naming-convention` — только как
`@typescript-eslint/naming-convention`. Голое имя в конфигурации не сработает.

Правило, которого в пинуемой версии не оказалось, заменяется на собственную
проверку из каталога выше либо требование возвращается к гейту `ревью` —
третьего варианта нет. Версии выше — те, на которых сверялось; при обновлении
инструмента сверку повторяют.

## Как это подключается

`ucp-bootstrap-design` (и языковые варианты) генерируют три скрипта из этого
каталога, привязывают их к общей задаче проверки и добавляют джобы `ddl:check`,
`config:check`, `manifest:check` в конвейер. Проверка, не сгенерированная
в проекте, означает, что требования, на неё ссылающиеся, фактически держатся
ревью — это состояние обнаруживается ревью-скиллом домена, который сверяет
обещанный гейт с содержимым проекта.
