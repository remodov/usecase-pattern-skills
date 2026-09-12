# Backend-трек — карта требований

Требования backend-трека, переведённые на openspec-форму. Таблица собирается
`spec_sync.py` из `spec.md` каждого домена и руками не редактируется: правка
потеряется при следующей пересборке, а `spec_check.py` покраснеет раньше.

Реестр доменов — `_meta/migrated-domains.md`.

<!-- BEGIN:ucp-requirements -->

| Требование | Гейт | Покрытие |
| --- | --- | --- |
| [async/async-native-libraries](.claude/docs/backend/python/async/spec.md) — На горячем пути используются асинхронные библиотеки | ревью | нет |
| [async/background-task-owned-by-lifespan](.claude/docs/backend/python/async/spec.md) — Фоновая задача создаётся в жизненном цикле приложения и хранит ссылку | ruff:RUF006 | частичное |
| [async/cancellation-propagates](.claude/docs/backend/python/async/spec.md) — Отмена доходит до верха | ревью | нет |
| [async/external-waits-have-timeouts](.claude/docs/backend/python/async/spec.md) — Внешние ожидания ограничены по времени | ревью | нет |
| [async/no-blocking-in-event-loop](.claude/docs/backend/python/async/spec.md) — Блокирующая работа выносится из цикла событий | ruff:ASYNC210, ruff:ASYNC230, ruff:ASYNC251 | частичное |
| [async/no-fire-and-forget-for-important-work](.claude/docs/backend/python/async/spec.md) — Важная работа не запускается по принципу «запустил и забыл» | ревью | нет |
| [async/no-nested-event-loop](.claude/docs/backend/python/async/spec.md) — Новый цикл событий внутри работающего не создаётся | ревью | нет |
| [async/no-shared-resource-across-tasks](.claude/docs/backend/python/async/spec.md) — Асинхронный ресурс не делится между задачами | ревью | нет |
| [async/resources-via-context-manager](.claude/docs/backend/python/async/spec.md) — Асинхронные ресурсы освобождаются контекстным менеджером | ruff:SIM115 | частичное |
| [async/structured-concurrency](.claude/docs/backend/python/async/spec.md) — Параллельные ожидания структурированы | ревью | нет |
| [auth-patterns/401-not-403](.claude/docs/backend/auth-patterns/spec.md) — Неаутентифицированный и недостаточно прав различаются | test:integration | частичное |
| [auth-patterns/admin-bypass-is-audited](.claude/docs/backend/auth-patterns/spec.md) — Административный обход прав всегда попадает в журнал действий | ревью | нет |
| [auth-patterns/admin-commands-write-audit-log](.claude/docs/backend/auth-patterns/spec.md) — Изменяющие команды администратора пишут журнал действий | ревью | нет |
| [auth-patterns/checks-split-by-layer](.claude/docs/backend/auth-patterns/spec.md) — Проверки разнесены по слоям | ревью | нет |
| [auth-patterns/error-response-hides-cause](.claude/docs/backend/auth-patterns/spec.md) — Ответ об ошибке не раскрывает причину | ревью | нет |
| [auth-patterns/every-endpoint-has-role-check](.claude/docs/backend/auth-patterns/spec.md) — У каждого эндпоинта есть проверка роли | java: archunit:ControllersHaveAuthorizationTest · python: test:integration · go: ревью · node: ревью | частичное |
| [auth-patterns/money-commands-need-idempotency-key](.claude/docs/backend/auth-patterns/spec.md) — Денежные команды требуют ключ идемпотентности | test:integration | частичное |
| [auth-patterns/no-pii-in-logs-and-events](.claude/docs/backend/auth-patterns/spec.md) — Персональные данные не покидают своего места | ревью | нет |
| [auth-patterns/no-secrets-in-repository](.claude/docs/backend/auth-patterns/spec.md) — Секретов в репозитории нет | gitleaks:default, ci:secret-scan | частичное |
| [auth-patterns/ownership-checked-in-domain](.claude/docs/backend/auth-patterns/spec.md) — Доступ по владению проверяется в домене и в одном месте | ревью | нет |
| [auth-patterns/refresh-token-rotation](.claude/docs/backend/auth-patterns/spec.md) — Токены обновления вращаются | ревью | нет |
| [auth-patterns/roles-from-token-claims](.claude/docs/backend/auth-patterns/spec.md) — Роли приезжают из токена через конвертер | ревью | нет |
| [auth-patterns/service-to-service-authenticated](.claude/docs/backend/auth-patterns/spec.md) — Межсервисные вызовы аутентифицированы | ревью | нет |
| [auth-patterns/token-in-httponly-cookie](.claude/docs/backend/auth-patterns/spec.md) — Токен на клиенте живёт в защищённой куке | ревью | нет |
| [auth-patterns/token-validated-by-library](.claude/docs/backend/auth-patterns/spec.md) — Токен проверяется библиотекой, а не руками | java: archunit:NoManualJwtParsingTest · python: ревью · go: ревью · node: ревью | частичное |
| [caching/cache-aside-is-default](.claude/docs/backend/caching/spec.md) — Основной паттерн — чтение через кеш со сбросом на записи | ревью | нет |
| [caching/cache-metrics-enabled](.claude/docs/backend/caching/spec.md) — Метрики кеша включены и наблюдаются | ci:metrics-check | частичное |
| [caching/cache-name-is-namespace](.claude/docs/backend/caching/spec.md) — Имя кеша задаёт пространство имён | script:config-check | частичное |
| [caching/cache-projections-not-aggregates](.claude/docs/backend/caching/spec.md) — Кешируются проекции чтения, а не агрегаты | ревью | нет |
| [caching/cache-read-heavy-stable-data](.claude/docs/backend/caching/spec.md) — Кешируются часто читаемые и редко меняющиеся данные | ревью | нет |
| [caching/cache-settings-are-typed](.claude/docs/backend/caching/spec.md) — Настройки кеша типизированы и проверяются при старте | test:integration | частичное |
| [caching/custom-key-generator-when-needed](.claude/docs/backend/caching/spec.md) — Собственный генератор ключей — только для сложных случаев | ревью | нет |
| [caching/distributed-cache-in-production](.claude/docs/backend/caching/spec.md) — В промышленной среде кеш распределённый | script:config-check | частичное |
| [caching/distributed-invalidation-is-built-in](.claude/docs/backend/caching/spec.md) — Распределённый сброс обеспечивает само хранилище | ревью | нет |
| [caching/eviction-logged-at-debug](.claude/docs/backend/caching/spec.md) — Сброс записей журналируется отладочным уровнем | ревью | нет |
| [caching/explicit-cache-key](.claude/docs/backend/caching/spec.md) — Ключ задаётся явно | ревью | нет |
| [caching/explicit-ttl-per-cache](.claude/docs/backend/caching/spec.md) — У каждого кеша свой срок жизни, заданный настройкой | script:config-check | частичное |
| [caching/invalidate-on-domain-event](.claude/docs/backend/caching/spec.md) — Сброс по доменному событию не зависит от сценария | ревью | нет |
| [caching/money-data-needs-explicit-invalidation](.claude/docs/backend/caching/spec.md) — Денежные данные кешируются только с явной стратегией сброса | ревью | нет |
| [caching/no-cache-on-write-path](.claude/docs/backend/caching/spec.md) — На пути записи кеша нет | java: archunit:NoCacheableOnCommandsTest · python: ревью · go: ревью · node: ревью | частичное |
| [caching/no-cache-without-manager](.claude/docs/backend/caching/spec.md) — Кеш без настроенного менеджера не заводится | test:integration | частичное |
| [caching/no-caching-authorization-results](.claude/docs/backend/caching/spec.md) — Результаты проверки прав не кешируются | java: archunit:NoCacheOnAuthorizationTest · python: ревью · go: ревью · node: ревью | частичное |
| [caching/no-routine-full-flush](.claude/docs/backend/caching/spec.md) — Полный сброс кеша не применяется как обычная операция | ревью | нет |
| [caching/no-sensitive-data-in-keys](.claude/docs/backend/caching/spec.md) — Чувствительные данные в ключе не хранятся открыто | ревью | нет |
| [caching/staleness-is-declared](.claude/docs/backend/caching/spec.md) — Возможная устарелость объявлена в контракте | ревью | нет |
| [caching/stampede-protection](.claude/docs/backend/caching/spec.md) — Одновременные промахи по горячему ключу не бьют в хранилище | ревью | нет |
| [caching/tests-use-real-cache](.claude/docs/backend/caching/spec.md) — Тесты работают с настоящим кешем | ревью | нет |
| [caching/ttl-is-not-consistency](.claude/docs/backend/caching/spec.md) — Срок жизни не заменяет согласованность | ревью | нет |
| [caching/ttl-matches-data-nature](.claude/docs/backend/caching/spec.md) — Срок жизни соответствует природе данных и не переживает релиз | ревью | нет |
| [caching/values-serialized-as-json](.claude/docs/backend/caching/spec.md) — Значения хранятся в текстовом формате обмена | script:config-check | частичное |
| [caching/write-evicts-affected-caches](.claude/docs/backend/caching/spec.md) — Запись сбрасывает затронутые кеши | ревью | нет |
| [codegen/generated-files-not-edited](.claude/docs/backend/python/codegen/spec.md) — Сгенерированное не правится руками | ci:codegen-check | частичное |
| [codegen/generation-settings](.claude/docs/backend/python/codegen/spec.md) — Настройки генерации задают форму схем | ci:codegen-check | частичное |
| [codegen/orm-draft-is-finished-by-hand](.claude/docs/backend/python/codegen/spec.md) — Черновик моделей доводится до требований слоя хранения | import-linter:layers | частичное |
| [codegen/precise-orm-types](.claude/docs/backend/python/codegen/spec.md) — Типы моделей хранения точные | ревью | нет |
| [codegen/precise-schema-types](.claude/docs/backend/python/codegen/spec.md) — Типы в схемах точные | mypy:strict | частичное |
| [codegen/schema-pipeline](.claude/docs/backend/python/codegen/spec.md) — Схема базы описывается одним источником и проходит полный конвейер | ci:codegen-check | частичное |
| [codegen/schemas-generated-from-contract](.claude/docs/backend/python/codegen/spec.md) — Схемы границы генерируются из описания контракта | ci:codegen-check | частичное |
| [codegen/shared-base-model](.claude/docs/backend/python/codegen/spec.md) — Общая базовая модель задаёт поведение сериализации | ревью | нет |
| [codegen/single-source-of-schema-truth](.claude/docs/backend/python/codegen/spec.md) — Источник правды по схеме один | ревью | нет |
| [cqrs/command-changes-one-aggregate](.claude/docs/backend/cqrs/spec.md) — Команда меняет один агрегат | ревью | нет |
| [cqrs/command-handler-does-not-query](.claude/docs/backend/cqrs/spec.md) — Обработчик команды не читает ради чтения | ревью | нет |
| [cqrs/command-returns-minimum](.claude/docs/backend/cqrs/spec.md) — Команда возвращает минимум | ревью | нет |
| [cqrs/events-not-coupled-to-write-schema](.claude/docs/backend/cqrs/spec.md) — События не привязаны к схеме записи | ревью | нет |
| [cqrs/eventual-consistency-declared](.claude/docs/backend/cqrs/spec.md) — Отложенная согласованность объявлена в контракте | ревью | нет |
| [cqrs/evolution-is-one-way](.claude/docs/backend/cqrs/spec.md) — Эволюция идёт в одну сторону | ревью | нет |
| [cqrs/lightweight-first-full-on-evidence](.claude/docs/backend/cqrs/spec.md) — Лёгкое разделение обязательно, тяжёлое — по показаниям | ревью | нет |
| [cqrs/projection-has-no-logic-or-backflow](.claude/docs/backend/cqrs/spec.md) — В проекции нет бизнес-логики и обратной синхронизации | ревью | нет |
| [cqrs/query-is-read-only](.claude/docs/backend/cqrs/spec.md) — Запрос только читает | java: archunit:QueryHandlersAreReadOnlyTest · python: ревью · go: ревью · node: ревью | частичное |
| [cqrs/query-returns-read-model](.claude/docs/backend/cqrs/spec.md) — Запрос возвращает модель чтения, а не агрегат | java: archunit:QueriesReturnReadModelsTest · python: ревью · go: ревью · node: ревью | частичное |
| [cqrs/read-model-consumer-is-idempotent](.claude/docs/backend/cqrs/spec.md) — Потребитель обновлений проекции идемпотентен | ревью | нет |
| [cqrs/read-model-is-rebuildable](.claude/docs/backend/cqrs/spec.md) — Модель чтения восстановима из данных записи | ревью | нет |
| [cqrs/read-model-storage-and-schema](.claude/docs/backend/cqrs/spec.md) — Модель чтения живёт там, где выгодно читать | ревью | нет |
| [cqrs/read-model-synced-by-events](.claude/docs/backend/cqrs/spec.md) — Модель чтения обновляется событиями, а не в транзакции записи | ревью | нет |
| [cqrs/read-via-projection-not-aggregate](.claude/docs/backend/cqrs/spec.md) — Чтение идёт через проекцию, а не через загрузку агрегата | ревью | нет |
| [cqrs/split-matches-maturity-level](.claude/docs/backend/cqrs/spec.md) — Уровень разделения соответствует уровню зрелости | ревью | нет |
| [cqrs/validation-split-edge-and-aggregate](.claude/docs/backend/cqrs/spec.md) — Проверки распределены между границей и агрегатом | ревью | нет |
| [ddd-tactical/aggregate-root-is-single-entry](.claude/docs/backend/ddd-tactical/spec.md) — Корень агрегата — единственная точка входа | java: archunit:AggregateRootIsEntryPointTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/aggregate-stays-small](.claude/docs/backend/ddd-tactical/spec.md) — Агрегат не разрастается | ревью | нет |
| [ddd-tactical/collections-in-values-are-protected](.claude/docs/backend/ddd-tactical/spec.md) — Изменяемые коллекции внутри значения обёрнуты | ревью | нет |
| [ddd-tactical/domain-does-not-know-operations](.claude/docs/backend/ddd-tactical/spec.md) — Домен не знает о слое операций | java: archunit:DomainDoesNotDependOnUseCasesTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/domain-service-only-across-aggregates](.claude/docs/backend/ddd-tactical/spec.md) — Доменный сервис появляется только для нескольких агрегатов | ревью | нет |
| [ddd-tactical/entity-constructor-validates](.claude/docs/backend/ddd-tactical/spec.md) — Конструктор сущности проверяет инварианты | java: archunit:EntitiesHaveNoSettersTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/entity-equality-by-identity](.claude/docs/backend/ddd-tactical/spec.md) — Сущность равна себе по идентификатору | java: archunit:EntitiesUseIdentityEqualityTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/event-carries-business-context](.claude/docs/backend/ddd-tactical/spec.md) — Событие несёт бизнес-контекст, а не ссылки | java: archunit:EventsHaveNoAggregateRefsTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/event-is-immutable-record](.claude/docs/backend/ddd-tactical/spec.md) — Событие — неизменяемый тип с базовыми полями | java: archunit:EventsAreImmutableTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/event-named-in-past-tense](.claude/docs/backend/ddd-tactical/spec.md) — Имя события — свершившийся факт | ревью | нет |
| [ddd-tactical/events-published-after-save](.claude/docs/backend/ddd-tactical/spec.md) — События публикуются после сохранения и очищаются | ревью | нет |
| [ddd-tactical/events-registered-by-root](.claude/docs/backend/ddd-tactical/spec.md) — События регистрирует корень | java: archunit:EventsRegisteredByRootTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/factory-only-when-needed](.claude/docs/backend/ddd-tactical/spec.md) — Агрегат создаётся через единственную точку, которая проверяет инварианты | java: archunit:AggregateBuildersUsedOnlyByFactoriesTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/identity-is-immutable](.claude/docs/backend/ddd-tactical/spec.md) — Идентификатор стабилен и неизменяем | java: archunit:EntityIdIsFinalTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/model-is-not-anemic](.claude/docs/backend/ddd-tactical/spec.md) — Модель богата поведением | ревью | нет |
| [ddd-tactical/no-after-commit-for-critical-effects](.claude/docs/backend/ddd-tactical/spec.md) — Критичные эффекты не доставляются после фиксации напрямую | ревью | нет |
| [ddd-tactical/no-object-references-across-aggregates](.claude/docs/backend/ddd-tactical/spec.md) — Сущность не хранит ссылок на чужие агрегаты | java: archunit:AggregatesReferenceByIdTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/no-primitive-obsession](.claude/docs/backend/ddd-tactical/spec.md) — Доменные понятия не выражаются примитивами | ревью | нет |
| [ddd-tactical/packages-grouped-by-domain](.claude/docs/backend/ddd-tactical/spec.md) — Пакеты core группируются по роли элемента, единообразно | java: archunit:CoreStructureTest · python: import-linter:layers · go: golangci-lint:depguard · node: dependency-cruiser:no-layer-violation | частичное |
| [ddd-tactical/repository-per-aggregate-root](.claude/docs/backend/ddd-tactical/spec.md) — Один репозиторий — один корень агрегата | ревью | нет |
| [ddd-tactical/repository-port-in-domain](.claude/docs/backend/ddd-tactical/spec.md) — Порт репозитория объявлен в домене | java: archunit:RepositoryPortsInDomainTest · python: import-linter:core-independence · go: golangci-lint:depguard · node: dependency-cruiser:no-core-to-adapter | частичное |
| [ddd-tactical/repository-speaks-domain](.claude/docs/backend/ddd-tactical/spec.md) — Методы репозитория названы в терминах домена | java: archunit:RepositoriesReturnDomainTypesTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/specification-for-reuse](.claude/docs/backend/ddd-tactical/spec.md) — Спецификация вводится при повторном использовании | ревью | нет |
| [ddd-tactical/specification-is-not-a-query-builder](.claude/docs/backend/ddd-tactical/spec.md) — Спецификация не генерирует запросы к хранилищу | ревью | нет |
| [ddd-tactical/transaction-boundary-equals-aggregate](.claude/docs/backend/ddd-tactical/spec.md) — Граница транзакции совпадает с границей агрегата | ревью | нет |
| [ddd-tactical/value-equality-by-all-fields](.claude/docs/backend/ddd-tactical/spec.md) — Значение равно по всем значимым полям | java: archunit:ValueObjectsUseValueEqualityTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/value-has-no-identity](.claude/docs/backend/ddd-tactical/spec.md) — Значение не имеет идентификатора и жизненного цикла | java: archunit:ValueObjectsHaveNoIdTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/value-object-is-immutable](.claude/docs/backend/ddd-tactical/spec.md) — Значение помечено как значение и неизменяемо | java: archunit:ValueObjectsAreImmutableTest · python: ревью · go: ревью · node: ревью | частичное |
| [ddd-tactical/value-validates-on-creation](.claude/docs/backend/ddd-tactical/spec.md) — Значение проверяет инварианты при создании | ревью | нет |
| [distributed-patterns/bounded-and-declared-staleness](.claude/docs/backend/distributed-patterns/spec.md) — Отложенная согласованность объявлена и ограничена | ревью | нет |
| [distributed-patterns/compensation-is-semantic-and-idempotent](.claude/docs/backend/distributed-patterns/spec.md) — Компенсация идемпотентна и оставляет след | ревью | нет |
| [distributed-patterns/database-is-source-of-truth](.claude/docs/backend/distributed-patterns/spec.md) — Источник правды — база сервиса, брокер — транспорт | ревью | нет |
| [distributed-patterns/every-step-has-compensation](.claude/docs/backend/distributed-patterns/spec.md) — У каждого шага процесса есть компенсация | ревью | нет |
| [distributed-patterns/failed-compensation-goes-to-review](.claude/docs/backend/distributed-patterns/spec.md) — Отказ компенсации имеет план | ревью | нет |
| [distributed-patterns/http-idempotency-record](.claude/docs/backend/distributed-patterns/spec.md) — Команда по протоколу запрос-ответ дедуплицируется по ключу и содержимому | ревью | нет |
| [distributed-patterns/idempotency-key-per-operation](.claude/docs/backend/distributed-patterns/spec.md) — Ключ идемпотентности принадлежит операции, а не запросу | ревью | нет |
| [distributed-patterns/inbox-for-critical-messages](.claude/docs/backend/distributed-patterns/spec.md) — Для критичных входящих применяется таблица входящих | ревью | нет |
| [distributed-patterns/message-has-unique-id](.claude/docs/backend/distributed-patterns/spec.md) — Каждое межсервисное сообщение имеет уникальный идентификатор | ревью | нет |
| [distributed-patterns/money-double-protection](.claude/docs/backend/distributed-patterns/spec.md) — Денежные операции защищены с двух сторон | ревью | нет |
| [distributed-patterns/no-two-phase-commit](.claude/docs/backend/distributed-patterns/spec.md) — Распределённых транзакций не бывает | java: archunit:NoChainedTransactionManagerTest · python: ревью · go: ревью · node: ревью | частичное |
| [distributed-patterns/orchestration-versus-choreography](.claude/docs/backend/distributed-patterns/spec.md) — Способ ведения последовательности выбирается по сложности | ревью | нет |
| [distributed-patterns/ordering-by-version](.claude/docs/backend/distributed-patterns/spec.md) — Порядок применения событий контролируется версией | ревью | нет |
| [distributed-patterns/outbox-for-outgoing-events](.claude/docs/backend/distributed-patterns/spec.md) — Исходящие события идут через таблицу исходящих | java: archunit:NoDirectBrokerSendInHandlersTest · python: ревью · go: ревью · node: ревью | частичное |
| [distributed-patterns/patterns-only-when-crossing-services](.claude/docs/backend/distributed-patterns/spec.md) — Распределённый паттерн вводится, только когда операция не помещается в одну транзакцию | ревью | нет |
| [distributed-patterns/read-your-writes-when-required](.claude/docs/backend/distributed-patterns/spec.md) — Чтение собственных записей обеспечивается явно | ревью | нет |
| [distributed-patterns/receiver-deduplicates](.claude/docs/backend/distributed-patterns/spec.md) — Получатель хранит отметки обработанного | ревью | нет |
| [distributed-patterns/saga-separate-from-use-cases](.claude/docs/backend/distributed-patterns/spec.md) — Процесс отделён от бизнес-операций | ревью | нет |
| [distributed-patterns/saga-state-is-persistent](.claude/docs/backend/distributed-patterns/spec.md) — Состояние процесса хранится в базе и имеет сквозной идентификатор | ревью | нет |
| [error-handling/alert-on-patterns-not-exceptions](.claude/docs/backend/error-handling/spec.md) — Оповещения строятся на образцах, а не на каждом исключении | ревью | нет |
| [error-handling/catch-does-not-swallow](.claude/docs/backend/error-handling/spec.md) — Перехват не глушит и не подменяет тип | java: spotbugs:DE_MIGHT_IGNORE · python: ruff:BLE001 · go: golangci-lint:errcheck · node: eslint:no-empty | частичное |
| [error-handling/catch-in-three-places-only](.claude/docs/backend/error-handling/spec.md) — Перехват допустим в четырёх местах | java: archunit:NoTryCatchInHandlersTest · python: ревью · go: ревью · node: ревью | частичное |
| [error-handling/domain-and-validation-mapping](.claude/docs/backend/error-handling/spec.md) — Доменные и валидационные ошибки отображаются в свои коды | test:integration | частичное |
| [error-handling/domain-exception-named-by-meaning](.claude/docs/backend/error-handling/spec.md) — Имя исключения говорит о бизнес-смысле | ревью | нет |
| [error-handling/errors-counted-by-kind](.claude/docs/backend/error-handling/spec.md) — Ошибки считаются метрикой с видом и типом | ci:metrics-check | частичное |
| [error-handling/exception-carries-context](.claude/docs/backend/error-handling/spec.md) — Исключение фиксирует контекст в конструкторе | ревью | нет |
| [error-handling/exceptions-are-part-of-contract](.claude/docs/backend/error-handling/spec.md) — Исключение объявлено в контракте операции | java: spotbugs:REC_CATCH_EXCEPTION · python: ruff:BLE001 · go: golangci-lint:errcheck · node: eslint:no-empty | частичное |
| [error-handling/four-exception-kinds](.claude/docs/backend/error-handling/spec.md) — Исключения группируются семействами — на агрегат и на внешнюю систему | ревью | нет |
| [error-handling/integration-and-technical-mapping](.claude/docs/backend/error-handling/spec.md) — Интеграционные и технические ошибки не раскрывают внутренностей | ревью | нет |
| [error-handling/integration-exception-names-system](.claude/docs/backend/error-handling/spec.md) — Интеграционные исключения различают систему | ревью | нет |
| [error-handling/log-level-matches-kind](.claude/docs/backend/error-handling/spec.md) — Уровень записи в журнал соответствует виду ошибки | ревью | нет |
| [error-handling/log-once-with-exception](.claude/docs/backend/error-handling/spec.md) — Ошибка записывается один раз и с объектом исключения | ревью | нет |
| [error-handling/no-bare-base-exceptions](.claude/docs/backend/error-handling/spec.md) — Базовые типы языка не бросаются | java: errorprone:ThrowSpecificExceptions · python: ревью · go: ревью · node: ревью | частичное |
| [error-handling/no-retry-at-edge](.claude/docs/backend/error-handling/spec.md) — На границе повторов нет | java: archunit:NoRetryAtEdgeTest · python: ревью · go: ревью · node: ревью | частичное |
| [error-handling/no-success-code-for-failure](.claude/docs/backend/error-handling/spec.md) — Отказ не маскируется успешным кодом | ревью | нет |
| [error-handling/result-type-is-local-choice](.claude/docs/backend/error-handling/spec.md) — Объект-результат применяется точечно | ревью | нет |
| [error-handling/retry-semantics-by-kind](.claude/docs/backend/error-handling/spec.md) — Повтор допустим только для ошибок, которые могут пройти | ревью | нет |
| [error-handling/throw-where-detected](.claude/docs/backend/error-handling/spec.md) — Бросать можно везде, где нужно | ревью | нет |
| [error-handling/trace-span-marked-error](.claude/docs/backend/error-handling/spec.md) — Отрезок трассировки помечается отказом | ревью | нет |
| [go-bootstrap/background-goroutines-awaited](.claude/docs/backend/go/go-bootstrap/spec.md) — Фоновые горутины завершаются по общей отмене | ревью | нет |
| [go-bootstrap/clock-and-ids-behind-interfaces](.claude/docs/backend/go/go-bootstrap/spec.md) — Источники недетерминизма скрыты за интерфейсами | ревью | нет |
| [go-bootstrap/config-is-typed-and-validated](.claude/docs/backend/go/go-bootstrap/spec.md) — Три состояния конфигурации задаются окружением и проверяются при старте | test:integration | частичное |
| [go-bootstrap/correlation-id-in-context](.claude/docs/backend/go/go-bootstrap/spec.md) — Корреляционный идентификатор проходит через контекст | ревью | нет |
| [go-bootstrap/dependencies-via-constructors](.claude/docs/backend/go/go-bootstrap/spec.md) — Зависимости собираются конструкторами, глобальных ресурсов нет | ревью | нет |
| [go-bootstrap/graceful-shutdown](.claude/docs/backend/go/go-bootstrap/spec.md) — Остановка плавная, готовность выключается первой | ревью | нет |
| [go-bootstrap/health-routes-first](.claude/docs/backend/go/go-bootstrap/spec.md) — Проверки состояния регистрируются раньше бизнес-маршрутов | ревью | нет |
| [go-bootstrap/lint-and-format-required](.claude/docs/backend/go/go-bootstrap/spec.md) — Линтер и форматирование обязательны | golangci-lint:default, ci:lint | полное |
| [go-bootstrap/liveness-and-readiness-split](.claude/docs/backend/go/go-bootstrap/spec.md) — Проверки живости и готовности разделены | test:integration | частичное |
| [go-bootstrap/local-quickstart-documented](.claude/docs/backend/go/go-bootstrap/spec.md) — Локальный запуск описан | ревью | нет |
| [go-bootstrap/main-only-starts](.claude/docs/backend/go/go-bootstrap/spec.md) — Точка входа только запускает | ревью | нет |
| [go-bootstrap/metrics-and-tracing-initialized-once](.claude/docs/backend/go/go-bootstrap/spec.md) — Метрики и трассировка инициализируются один раз | ревью | нет |
| [go-bootstrap/middleware-order](.claude/docs/backend/go/go-bootstrap/spec.md) — Перехватчики зарегистрированы в правильном порядке | ревью | нет |
| [go-bootstrap/no-pii-log-once](.claude/docs/backend/go/go-bootstrap/spec.md) — Персональных данных в журнале нет, ошибка пишется один раз | ревью | нет |
| [go-bootstrap/package-layout-directs-inward](.claude/docs/backend/go/go-bootstrap/spec.md) — Раскладка пакетов направляет зависимости внутрь | golangci-lint:depguard | частичное |
| [go-bootstrap/pool-and-migrations](.claude/docs/backend/go/go-bootstrap/spec.md) — Пул соединений один, миграции идут отдельно | ревью | нет |
| [go-bootstrap/profile-from-environment](.claude/docs/backend/go/go-bootstrap/spec.md) — Профиль выбирается окружением | ревью | нет |
| [go-bootstrap/recover-at-edge](.claude/docs/backend/go/go-bootstrap/spec.md) — Аварийное завершение перехватывается на границе | ревью | нет |
| [go-bootstrap/single-config-object](.claude/docs/backend/go/go-bootstrap/spec.md) — Настройки читаются одним объектом | ревью | нет |
| [go-bootstrap/structured-logging](.claude/docs/backend/go/go-bootstrap/spec.md) — Журналирование структурное и настроено один раз | golangci-lint:forbidigo | частичное |
| [go-style/concurrency-primitives](.claude/docs/backend/go/go-style/spec.md) — Разделяемое состояние защищено, параллелизм ограничен | golangci-lint:govet | частичное |
| [go-style/context-carries-cross-cutting-data](.claude/docs/backend/go/go-style/spec.md) — В контексте передаются только сквозные данные | ревью | нет |
| [go-style/context-is-first-argument](.claude/docs/backend/go/go-style/spec.md) — Контекст — первый аргумент и передаётся во все вызовы ввода-вывода | golangci-lint:containedctx, golangci-lint:contextcheck | частичное |
| [go-style/control-flow-stays-flat](.claude/docs/backend/go/go-style/spec.md) — Управляющие структуры плоские | golangci-lint:gocritic, golangci-lint:exhaustive | частичное |
| [go-style/doc-comments-on-exported-only](.claude/docs/backend/go/go-style/spec.md) — Публичные символы документированы, внутренних комментариев нет | golangci-lint:revive | частичное |
| [go-style/domain-errors-are-typed](.claude/docs/backend/go/go-style/spec.md) — Доменная ошибка типизирована и несёт вид | ревью | нет |
| [go-style/errors-are-values-and-checked](.claude/docs/backend/go/go-style/spec.md) — Ошибки — значения, и каждая проверяется | golangci-lint:errcheck, golangci-lint:errorlint | полное |
| [go-style/formatting-and-lint-enforced](.claude/docs/backend/go/go-style/spec.md) — Форматирование и линтер обязательны | golangci-lint:default, ci:lint | полное |
| [go-style/formatting-conventions](.claude/docs/backend/go/go-style/spec.md) — Форматирование единообразно | golangci-lint:lll, golangci-lint:wsl | частичное |
| [go-style/goroutines-are-owned](.claude/docs/backend/go/go-style/spec.md) — Горутина завершается вместе с сервисом | ревью | нет |
| [go-style/idiomatic-over-clever](.claude/docs/backend/go/go-style/spec.md) — Идиома важнее краткости | ревью | нет |
| [go-style/imports-are-grouped-and-explicit](.claude/docs/backend/go/go-style/spec.md) — Импорты сгруппированы и явные | golangci-lint:goimports, golangci-lint:revive | полное |
| [go-style/init-only-for-registration](.claude/docs/backend/go/go-style/spec.md) — Функция инициализации применяется только для регистрации | ревью | нет |
| [go-style/internal-packages-are-a-barrier](.claude/docs/backend/go/go-style/spec.md) — Внутренние пакеты остаются внутренними | golangci-lint:depguard | частичное |
| [go-style/lint-config-is-mandatory](.claude/docs/backend/go/go-style/spec.md) — Конфигурация линтера обязательна и не ослабляется | golangci-lint:default, ci:lint | частичное |
| [go-style/long-loops-check-cancellation](.claude/docs/backend/go/go-style/spec.md) — Долгие циклы проверяют отмену | ревью | нет |
| [go-style/loops-have-exit-condition](.claude/docs/backend/go/go-style/spec.md) — Бесконечные циклы имеют условие выхода | ревью | нет |
| [go-style/naming-conventions](.claude/docs/backend/go/go-style/spec.md) — Именование следует конвенции языка | golangci-lint:revive, golangci-lint:staticcheck | частичное |
| [go-style/no-empty-interface-or-alias](.claude/docs/backend/go/go-style/spec.md) — Пустой интерфейс и лишние псевдонимы не используются | ревью | нет |
| [go-style/no-loop-variable-capture](.claude/docs/backend/go/go-style/spec.md) — Переменная цикла не захватывается горутиной | golangci-lint:govet | частичное |
| [go-style/no-panic-as-control-flow](.claude/docs/backend/go/go-style/spec.md) — Аварийное завершение не используется как управление потоком | golangci-lint:revive | частичное |
| [go-style/only-sender-closes-channel](.claude/docs/backend/go/go-style/spec.md) — В закрытый канал не пишут | ревью | нет |
| [go-style/packages-have-purpose](.claude/docs/backend/go/go-style/spec.md) — Пакеты имеют роль, имя типа не дублируется в методах | ревью | нет |
| [go-style/race-detector-in-ci](.claude/docs/backend/go/go-style/spec.md) — Детектор гонок включён в конвейере | ci:test-race | частичное |
| [go-style/small-interfaces](.claude/docs/backend/go/go-style/spec.md) — Интерфейсы малы, принимаются на входе | ревью | нет |
| [go-style/test-naming](.claude/docs/backend/go/go-style/spec.md) — Имя теста называет случай | ревью | нет |
| [go-style/tests-are-idiomatic](.claude/docs/backend/go/go-style/spec.md) — Тесты идиоматичны и изолированы | ревью | нет |
| [go-style/tests-avoid-sleep-and-shared-state](.claude/docs/backend/go/go-style/spec.md) — Тесты не полагаются на паузы и общее состояние | ревью | нет |
| [go-style/timeouts-before-io](.claude/docs/backend/go/go-style/spec.md) — Ограничение времени ставится перед вызовом внешней системы | ревью | нет |
| [go-style/value-types-are-precise](.claude/docs/backend/go/go-style/spec.md) — Значения неизменяемы, деньги и время выражены точными типами | ревью | нет |
| [go-test-strategy/assertions-split-by-severity](.claude/docs/backend/go/go-test-strategy/spec.md) — Утверждения разделены по фатальности | ревью | нет |
| [go-test-strategy/auth-is-faked-not-disabled](.claude/docs/backend/go/go-test-strategy/spec.md) — Авторизация подменяется, но не отключается | script:test-lint | частичное |
| [go-test-strategy/container-once-per-package](.claude/docs/backend/go/go-test-strategy/spec.md) — Контейнер поднимается один раз на пакет и закрывается явно | ревью | нет |
| [go-test-strategy/database-preparer-per-context](.claude/docs/backend/go/go-test-strategy/spec.md) — Подготовка базы идёт через отдельный компонент | ревью | нет |
| [go-test-strategy/external-calls-via-stub-server](.claude/docs/backend/go/go-test-strategy/spec.md) — Внешние вызовы подменяются сервером, заглушка проверяет запрос | ревью | нет |
| [go-test-strategy/integration-test-shape](.claude/docs/backend/go/go-test-strategy/spec.md) — Интеграционный тест поднимает сервер и настоящую базу | ревью | нет |
| [go-test-strategy/isolation-matches-parallelism](.claude/docs/backend/go/go-test-strategy/spec.md) — Изоляция тестов согласована с параллельностью | ревью | нет |
| [go-test-strategy/no-broker-or-cache](.claude/docs/backend/go/go-test-strategy/spec.md) — Брокер и кеш в интеграционных тестах не поднимаются | script:test-lint | частичное |
| [go-test-strategy/one-test-one-scenario](.claude/docs/backend/go/go-test-strategy/spec.md) — Один тест — один сценарий | ревью | нет |
| [go-test-strategy/requests-are-fully-controlled](.claude/docs/backend/go/go-test-strategy/spec.md) — Обращение идёт по протоколу с полным контролем | golangci-lint:staticcheck | частичное |
| [go-test-strategy/schema-once-data-cleaned](.claude/docs/backend/go/go-test-strategy/spec.md) — Схема ставится один раз, данные очищаются | script:test-lint | частичное |
| [go-test-strategy/test-layers-separated](.claude/docs/backend/go/go-test-strategy/spec.md) — Слои тестов разделены по назначению | ci:test-layers | частичное |
| [go-test-strategy/test-name-states-case](.claude/docs/backend/go/go-test-strategy/spec.md) — Имя теста называет случай и правило | script:test-lint | частичное |
| [go-test-strategy/test-server-helper](.claude/docs/backend/go/go-test-strategy/spec.md) — Тестовый сервер собирается вспомогательной функцией | ревью | нет |
| [go-test-strategy/tests-are-deterministic](.claude/docs/backend/go/go-test-strategy/spec.md) — Тесты детерминированы | script:test-lint | частичное |
| [graceful-shutdown/background-tasks-finish-iteration](.claude/docs/backend/graceful-shutdown/spec.md) — Фоновые задачи завершают текущую итерацию | script:config-check | частичное |
| [graceful-shutdown/connection-pool-closes-last](.claude/docs/backend/graceful-shutdown/spec.md) — Пул соединений закрывается последним | ревью | нет |
| [graceful-shutdown/consumer-finishes-batch](.claude/docs/backend/graceful-shutdown/spec.md) — Потребитель дожимает пакет и фиксирует смещение | script:config-check | частичное |
| [graceful-shutdown/in-flight-operations-are-retry-safe](.claude/docs/backend/graceful-shutdown/spec.md) — Прерываемые операции безопасны для повтора | ревью | нет |
| [graceful-shutdown/long-operations-are-async](.claude/docs/backend/graceful-shutdown/spec.md) — Длительные синхронные операции переносятся в асинхронные | ревью | нет |
| [graceful-shutdown/no-work-lost-on-sigterm](.claude/docs/backend/graceful-shutdown/spec.md) — По сигналу остановки работа доводится до конца | ревью | нет |
| [graceful-shutdown/outbox-relay-checks-readiness](.claude/docs/backend/graceful-shutdown/spec.md) — Цикл отправки исходящих проверяет готовность | ревью | нет |
| [graceful-shutdown/prestop-delay](.claude/docs/backend/graceful-shutdown/spec.md) — Перед остановкой выдерживается пауза | script:manifest-check | полное |
| [graceful-shutdown/readiness-off-first](.claude/docs/backend/graceful-shutdown/spec.md) — Готовность принимать трафик выключается первой | script:manifest-check | частичное |
| [graceful-shutdown/rolling-update-keeps-capacity](.claude/docs/backend/graceful-shutdown/spec.md) — Выкатка идёт без потери мощности | script:manifest-check | полное |
| [graceful-shutdown/shutdown-budget-is-explicit](.claude/docs/backend/graceful-shutdown/spec.md) — Общий бюджет остановки задан и распределён | script:config-check, script:manifest-check | частичное |
| [graceful-shutdown/shutdown-is-observable](.claude/docs/backend/graceful-shutdown/spec.md) — Остановка наблюдаема и не шумит в оповещениях | ревью | нет |
| [graceful-shutdown/transactions-finish-in-own-channel](.claude/docs/backend/graceful-shutdown/spec.md) — Транзакции завершаются по своему каналу | ревью | нет |
| [graceful-shutdown/web-server-graceful-enabled](.claude/docs/backend/graceful-shutdown/spec.md) — Плавная остановка веб-сервера включена | script:config-check | полное |
| [hexagonal/absence-is-not-error](.claude/docs/backend/hexagonal/spec.md) — Отсутствие значения и ошибка различаются в сигнатуре порта | ревью | нет |
| [hexagonal/adapter-maps-not-decides](.claude/docs/backend/hexagonal/spec.md) — Адаптер мапит, а не решает | ревью | нет |
| [hexagonal/adapter-structure](.claude/docs/backend/hexagonal/spec.md) — Структура адаптера задана | ревью | нет |
| [hexagonal/adapters-do-not-know-each-other](.claude/docs/backend/hexagonal/spec.md) — Адаптеры не знают друг о друге | java: archunit:AdaptersDoNotDependOnEachOtherTest · python: import-linter:adapters-independent · go: golangci-lint:depguard · node: dependency-cruiser:no-adapter-to-adapter | частичное |
| [hexagonal/architecture-test-required-check](.claude/docs/backend/hexagonal/spec.md) — Архитектурный тест — обязательная проверка в CI | ci:archtest | частичное |
| [hexagonal/architecture-tests-required](.claude/docs/backend/hexagonal/spec.md) — Архитектурные тесты проверяют границы | java: archunit:HexagonalLayersTest · python: import-linter:layers · go: golangci-lint:depguard · node: dependency-cruiser:no-layer-violation | частичное |
| [hexagonal/bootstrap-composition-only](.claude/docs/backend/hexagonal/spec.md) — bootstrap — только композиция | java: archunit:BootstrapHasNoBusinessLogicTest · python: import-linter:bootstrap · go: ревью · node: dependency-cruiser:bootstrap-only-composition | частичное |
| [hexagonal/composition-covers-all-adapters](.claude/docs/backend/hexagonal/spec.md) — Композиция покрывает все адаптеры | test:integration | частичное |
| [hexagonal/config-enters-core-via-interface](.claude/docs/backend/hexagonal/spec.md) — Конфигурация входит в core через интерфейс | java: archunit:CoreUsesOnlyWhitelistedFrameworkPackagesTest · python: ревью · go: ревью · node: ревью | частичное |
| [hexagonal/controller-dispatches-only](.claude/docs/backend/hexagonal/spec.md) — Контроллер реализует сгенерированный контракт и диспатчит | java: archunit:ControllersDoNotUseRepositoriesTest · python: import-linter:in-adapter · go: ревью · node: dependency-cruiser:no-controller-to-repository | частичное |
| [hexagonal/core-free-of-framework](.claude/docs/backend/hexagonal/spec.md) — core свободен от инфраструктуры, фреймворк — только по whitelist'у | java: archunit:CoreUsesOnlyWhitelistedFrameworkPackagesTest · python: import-linter:core-independence · go: golangci-lint:depguard · node: dependency-cruiser:no-core-to-adapter | частичное |
| [hexagonal/core-structure](.claude/docs/backend/hexagonal/spec.md) — Структура core задана | java: archunit:CoreStructureTest · python: ревью · go: ревью · node: ревью | частичное |
| [hexagonal/di-annotations-in-core](.claude/docs/backend/hexagonal/spec.md) — DI-аннотации в core — без фреймворка на runtime-classpath ядра | java: archunit:CoreUsesOnlyWhitelistedFrameworkPackagesTest · python: import-linter:core-independence · go: ревью · node: dependency-cruiser:no-core-to-adapter | частичное |
| [hexagonal/in-adapter-per-audience](.claude/docs/backend/hexagonal/spec.md) — Раздельные in-adapter'ы для разных аудиторий | ревью | нет |
| [hexagonal/inbound-port-is-use-case](.claude/docs/backend/hexagonal/spec.md) — Вход в core — use case, отдельного inbound-порта нет | ревью | нет |
| [hexagonal/level-three-only](.claude/docs/backend/hexagonal/spec.md) — Hexagonal берётся под Уровень 3, не раньше | ревью | нет |
| [hexagonal/module-per-part](.claude/docs/backend/hexagonal/spec.md) — Модуль сборки на каждую часть | java: gradle:project-dependencies · python: import-linter:contracts · go: golangci-lint:depguard · node: dependency-cruiser:no-cross-module | частичное |
| [hexagonal/no-generated-types-in-core](.claude/docs/backend/hexagonal/spec.md) — Сгенерированные типы инфраструктуры не бывают доменными | java: archunit:CoreUsesOnlyWhitelistedFrameworkPackagesTest · python: import-linter:core-independence · go: golangci-lint:depguard · node: dependency-cruiser:no-core-to-adapter | частичное |
| [hexagonal/no-partial-adoption](.claude/docs/backend/hexagonal/spec.md) — Частичного hexagonal не бывает | java: archunit:HexagonalLayersTest · python: import-linter:layers · go: golangci-lint:depguard · node: dependency-cruiser:no-layer-violation | частичное |
| [hexagonal/out-adapter-per-system](.claude/docs/backend/hexagonal/spec.md) — Модуль out-adapter на каждую внешнюю систему | java: archunit:AdapterImplementsPortTest · python: import-linter:adapters-independent · go: ревью · node: dependency-cruiser:no-adapter-to-adapter | частичное |
| [hexagonal/outbound-port-interface-in-core](.claude/docs/backend/hexagonal/spec.md) — Outbound-порт — интерфейс в core | java: archunit:PortsAreInterfacesTest · python: import-linter:ports · go: ревью · node: dependency-cruiser:ports-in-core | частичное |
| [hexagonal/port-exceptions-in-core](.claude/docs/backend/hexagonal/spec.md) — Исключения порта объявлены в core | java: archunit:CoreUsesOnlyWhitelistedFrameworkPackagesTest · python: import-linter:core-independence · go: golangci-lint:depguard · node: dependency-cruiser:no-core-to-adapter | частичное |
| [hexagonal/port-speaks-domain-types](.claude/docs/backend/hexagonal/spec.md) — Порт оперирует доменными типами | java: archunit:PortsUseDomainTypesTest · python: ревью · go: ревью · node: ревью | частичное |
| [hexagonal/rest-mapping-in-adapter](.claude/docs/backend/hexagonal/spec.md) — Маппинг REST ↔ домен живёт в отдельном классе in-adapter'а | java: archunit:ControllersReturnDtoTest · python: ревью · go: ревью · node: ревью | частичное |
| [hexagonal/rich-domain-model](.claude/docs/backend/hexagonal/spec.md) — Домен богатый, не анемичный | ревью | нет |
| [hexagonal/single-scan-root](.claude/docs/backend/hexagonal/spec.md) — Архитектурные тесты сканируют один корневой пакет | ревью | нет |
| [java-style/abbreviation-casing](.claude/docs/backend/java/java-style/spec.md) — Аббревиатуры оформляются единообразно | checkstyle:AbbreviationAsWordInName | частичное |
| [java-style/boilerplate-is-generated](.claude/docs/backend/java/java-style/spec.md) — Шаблонный код генерируется, а не пишется | ревью | нет |
| [java-style/builder-used-sparingly](.claude/docs/backend/java/java-style/spec.md) — Построитель — для объектов переноса, на агрегате — только проводка фабрики | java: archunit:AggregateBuildersUsedOnlyByFactoriesTest | частичное |
| [java-style/deviation-requires-justification](.claude/docs/backend/java/java-style/spec.md) — Отступление от правила объясняется читаемостью | ревью | нет |
| [java-style/exhaustive-switch-on-sealed](.claude/docs/backend/java/java-style/spec.md) — Закрытые иерархии разбираются исчерпывающим переключением | java: errorprone:MissingCasesInEnumSwitch | частичное |
| [java-style/expressions-stay-simple](.claude/docs/backend/java/java-style/spec.md) — Выражения остаются простыми и явными | checkstyle:BooleanExpressionComplexity, checkstyle:ArrayTypeStyle, checkstyle:ModifierOrder, checkstyle:RedundantModifier | полное |
| [java-style/formatting-rules](.claude/docs/backend/java/java-style/spec.md) — Форматирование единообразно | checkstyle:LineLength, checkstyle:WhitespaceAround | частичное |
| [java-style/generation-setup-is-uniform](.claude/docs/backend/java/java-style/spec.md) — Настройка генерации одинакова во всех модулях | gradle:build-config-check | частичное |
| [java-style/guard-clauses-preferred](.claude/docs/backend/java/java-style/spec.md) — Ранний выход вместо вложенных условий | ревью | нет |
| [java-style/imports-are-explicit](.claude/docs/backend/java/java-style/spec.md) — Импорты точные и используемые | checkstyle:AvoidStarImport, checkstyle:UnusedImports | полное |
| [java-style/lambdas-stay-short](.claude/docs/backend/java/java-style/spec.md) — Лямбды короткие, длинная логика именована | ревью | нет |
| [java-style/mechanical-versus-semantic-split](.claude/docs/backend/java/java-style/spec.md) — Граница между машинной и смысловой проверкой объявлена | ревью | нет |
| [java-style/member-naming](.claude/docs/backend/java/java-style/spec.md) — Имена методов, переменных и констант следуют конвенции | checkstyle:MethodName, checkstyle:LocalVariableName, checkstyle:ConstantName | частичное |
| [java-style/no-comments-in-code](.claude/docs/backend/java/java-style/spec.md) — Комментариев в коде нет | checkstyle:CommentsIndentation | частичное |
| [java-style/no-generation-on-records](.claude/docs/backend/java/java-style/spec.md) — Генерация не дублирует запись и не добавляет изменяемости | java: gradle:compile | частичное |
| [java-style/no-javadoc-artifacts](.claude/docs/backend/java/java-style/spec.md) — Документирующие артефакты не собираются | gradle:build-config-check | частичное |
| [java-style/no-rule-codes-or-history-in-code](.claude/docs/backend/java/java-style/spec.md) — Коды правил и история изменений в коде не цитируются | ревью | нет |
| [java-style/package-and-type-naming](.claude/docs/backend/java/java-style/spec.md) — Имена пакетов и типов следуют конвенции | checkstyle:PackageName, checkstyle:TypeName | частичное |
| [java-style/prefer-modern-constructs](.claude/docs/backend/java/java-style/spec.md) — Современные конструкции применяются там, где короче | ревью | нет |
| [java-style/style-check-is-enforced](.claude/docs/backend/java/java-style/spec.md) — Статическая проверка стиля подключена и не терпит предупреждений | gradle:checkstyle, ci:lint | частичное |
| [java-style/test-method-naming](.claude/docs/backend/java/java-style/spec.md) — Имя теста отражает суть случая | checkstyle:MethodName | частичное |
| [jooq/absence-and-existence-are-explicit](.claude/docs/backend/java/jooq/spec.md) — Отсутствие записи и проверка наличия выражаются точно | ревью | нет |
| [jooq/batch-fetch-for-many-parents](.claude/docs/backend/java/jooq/spec.md) — На больших выборках вложенность заменяется двумя запросами | ревью | нет |
| [jooq/codegen-from-live-schema](.claude/docs/backend/java/jooq/spec.md) — Типы генерируются поверх живой схемы | gradle:jooq-codegen | частичное |
| [jooq/codegen-settings](.claude/docs/backend/java/jooq/spec.md) — Настройки генерации заданы под маппинг | gradle:jooq-codegen | частичное |
| [jooq/constructor-injection](.claude/docs/backend/java/jooq/spec.md) — Зависимости внедряются через конструктор | java: archunit:NoFieldInjectionTest | частичное |
| [jooq/dsl-context-is-singleton-bean](.claude/docs/backend/java/jooq/spec.md) — Контекст доступа — единственный бин | java: archunit:NoAdHocDslContextTest | частичное |
| [jooq/enums-and-documents-mapping](.claude/docs/backend/java/jooq/spec.md) — Перечисления и документы преобразуются единообразно | ревью | нет |
| [jooq/fetch-and-update-forms](.claude/docs/backend/java/jooq/spec.md) — Способ выборки соответствует цели | ревью | нет |
| [jooq/filters-extracted-to-builder](.claude/docs/backend/java/jooq/spec.md) — Сложные условия вынесены в отдельный построитель | ревью | нет |
| [jooq/generated-code-not-in-vcs](.claude/docs/backend/java/jooq/spec.md) — Сгенерированный код не хранится в репозитории | gradle:jooq-codegen | частичное |
| [jooq/keyset-pagination-for-feeds](.claude/docs/backend/java/jooq/spec.md) — Для часто меняющихся данных применяется выдача по курсору | ревью | нет |
| [jooq/locking-select-inside-transaction](.claude/docs/backend/java/jooq/spec.md) — Блокирующая выборка идёт внутри транзакции | ревью | нет |
| [jooq/mapper-is-explicit-class](.claude/docs/backend/java/jooq/spec.md) — Маппинг записей в домен выполняет отдельный класс | ревью | нет |
| [jooq/mappers-delegate](.claude/docs/backend/java/jooq/spec.md) — Мапперы делегируют, а не наследуют | java: archunit:MappersStayInPersistenceTest | частичное |
| [jooq/nested-collections-in-one-query](.claude/docs/backend/java/jooq/spec.md) — Вложенные коллекции читаются одним запросом | ревью | нет |
| [jooq/no-business-logic-in-repository](.claude/docs/backend/java/jooq/spec.md) — Бизнес-логики в репозитории нет | ревью | нет |
| [jooq/no-generated-daos](.claude/docs/backend/java/jooq/spec.md) — Сгенерированные объекты доступа не используются | java: archunit:NoGeneratedDaoUsageTest | частичное |
| [jooq/no-other-persistence-frameworks](.claude/docs/backend/java/jooq/spec.md) — Иных механизмов доступа к базе не применяется | java: archunit:NoOtherPersistenceApisTest | частичное |
| [jooq/optimistic-locking-via-version-column](.claude/docs/backend/java/jooq/spec.md) — Оптимистическая блокировка выражена колонкой версии | ревью | нет |
| [jooq/pagination-returns-domain-view](.claude/docs/backend/java/jooq/spec.md) — Постраничная выдача возвращает доменное представление | ревью | нет |
| [jooq/query-parts-extracted](.claude/docs/backend/java/jooq/spec.md) — Сложные части запроса вынесены в приватные методы | ревью | нет |
| [jooq/repository-integration-tested](.claude/docs/backend/java/jooq/spec.md) — Репозиторий покрыт интеграционным тестом против настоящей базы | ci:test-layers | частичное |
| [jooq/repository-interface-in-domain](.claude/docs/backend/java/jooq/spec.md) — Реализация репозитория отделена от доменного интерфейса | java: archunit:RepositoryPortsInDomainTest | частичное |
| [jooq/repository-speaks-domain-types](.claude/docs/backend/java/jooq/spec.md) — Публичные методы репозитория говорят доменными типами | java: archunit:RepositoriesReturnDomainTypesTest | частичное |
| [jooq/select-mode-parameter](.claude/docs/backend/java/jooq/spec.md) — Режим блокировки — параметр метода чтения | ревью | нет |
| [jooq/transaction-on-handler](.claude/docs/backend/java/jooq/spec.md) — Транзакция объявляется на обработчике | java: archunit:TransactionalOnHandlersOnlyTest | частичное |
| [jooq/type-safe-query-building](.claude/docs/backend/java/jooq/spec.md) — Запросы строятся типобезопасно | java: archunit:NoPlainSqlTest | частичное |
| [jooq/view-repository-separate](.claude/docs/backend/java/jooq/spec.md) — Проекции чтения живут в отдельном репозитории | ревью | нет |
| [kafka/concurrency-and-poll-interval](.claude/docs/backend/kafka/spec.md) — Параллелизм и время обработки согласованы с топиком | ревью | нет |
| [kafka/consumer-group-per-purpose](.claude/docs/backend/kafka/spec.md) — У каждого потребителя своя группа с говорящим именем | ревью | нет |
| [kafka/consumer-is-idempotent](.claude/docs/backend/kafka/spec.md) — Обработчик идемпотентен по идентификатору события | ревью | нет |
| [kafka/consumer-lag-alerting](.claude/docs/backend/kafka/spec.md) — Отставание потребителя под оповещением | ci:metrics-check | частичное |
| [kafka/deserialization-allow-list](.claude/docs/backend/kafka/spec.md) — Десериализация ограничена явным списком или явным типом | script:config-check | частичное |
| [kafka/dlq-monitored-and-manually-replayed](.claude/docs/backend/kafka/spec.md) — Неразобранные сообщения под наблюдением | ревью | нет |
| [kafka/earliest-offset-for-critical-consumers](.claude/docs/backend/kafka/spec.md) — Чтение с начала для критичных потребителей | script:config-check | частичное |
| [kafka/event-named-in-past-tense](.claude/docs/backend/kafka/spec.md) — Имя события — свершившийся факт | ревью | нет |
| [kafka/event-payload-hygiene](.claude/docs/backend/kafka/spec.md) — Полезная нагрузка события не содержит внутренних объектов и персональных данных | ревью | нет |
| [kafka/event-schema-forward-compatible](.claude/docs/backend/kafka/spec.md) — Схема события развивается совместимо | ревью | нет |
| [kafka/listener-does-not-block-poll-loop](.claude/docs/backend/kafka/spec.md) — Обработчик не блокирует цикл опроса | java: archunit:NoThreadSleepInListenersTest · python: ревью · go: ревью · node: ревью | частичное |
| [kafka/manual-offset-commit](.claude/docs/backend/kafka/spec.md) — Смещение подтверждается только после обработки записи | script:config-check | частичное |
| [kafka/missing-topics-are-fatal](.claude/docs/backend/kafka/spec.md) — Отсутствие ожидаемого топика останавливает старт | script:config-check | частичное |
| [kafka/money-operations-double-protected](.claude/docs/backend/kafka/spec.md) — Денежные операции защищены дважды | ревью | нет |
| [kafka/no-swallowing-in-listener](.claude/docs/backend/kafka/spec.md) — Исключение в обработчике не проглатывается | java: spotbugs:REC_CATCH_EXCEPTION · python: ruff:BLE001 · go: golangci-lint:errcheck · node: eslint:no-empty | частичное |
| [kafka/outbox-relay-reads-in-batches](.claude/docs/backend/kafka/spec.md) — Процесс отправки читает пакетами и пропускает занятые записи | ревью | нет |
| [kafka/outbox-table-shape](.claude/docs/backend/kafka/spec.md) — Таблица исходящих сообщений отмечает отправку и индексирована под выборку | ревью | нет |
| [kafka/partition-key-required](.claude/docs/backend/kafka/spec.md) — У бизнес-события есть ключ разделения | ревью | нет |
| [kafka/processed-record-in-same-transaction](.claude/docs/backend/kafka/spec.md) — Отметка обработки и результат пишутся одной транзакцией | ревью | нет |
| [kafka/producer-is-idempotent](.claude/docs/backend/kafka/spec.md) — Публикация идемпотентна и с полным подтверждением | script:config-check | частичное |
| [kafka/publish-via-outbox](.claude/docs/backend/kafka/spec.md) — Доменные события публикуются через надёжную публикацию | java: archunit:NoDirectKafkaSendInHandlersTest · python: ревью · go: ревью · node: ревью | частичное |
| [kafka/reference-data-backfilled-via-api](.claude/docs/backend/kafka/spec.md) — Справочные данные из шины наливаются через API источника | ревью | нет |
| [kafka/retry-only-transient-failures](.claude/docs/backend/kafka/spec.md) — Повторяются только временные отказы | ревью | нет |
| [kafka/retry-topics-with-limits](.claude/docs/backend/kafka/spec.md) — Повторы ограничены попытками и заканчиваются очередью неразобранных | ревью | нет |
| [kafka/serialization-format](.claude/docs/backend/kafka/spec.md) — Формат сообщения выбран осознанно | ревью | нет |
| [kafka/settings-are-typed-and-external](.claude/docs/backend/kafka/spec.md) — Настройки клиента типизированы и не содержат адресов в коде | script:config-check, test:integration | частичное |
| [kafka/trace-context-in-headers](.claude/docs/backend/kafka/spec.md) — Контекст трассировки передаётся через заголовки сообщения | ревью | нет |
| [kafka/transport-security-and-acls](.claude/docs/backend/kafka/spec.md) — Соединение с кластером защищено, доступ ограничен по сервисам | script:config-check | частичное |
| [nest-bootstrap/api-docs-outside-production](.claude/docs/backend/node/nest-bootstrap/spec.md) — Документация интерфейса публикуется вне промышленной среды | ревью | нет |
| [nest-bootstrap/broker-and-cache-are-conditional](.claude/docs/backend/node/nest-bootstrap/spec.md) — Брокер и кеш подключаются условно | test:integration | частичное |
| [nest-bootstrap/clock-and-ids-behind-tokens](.claude/docs/backend/node/nest-bootstrap/spec.md) — Источники недетерминизма скрыты за токенами | ревью | нет |
| [nest-bootstrap/config-validated-at-startup](.claude/docs/backend/node/nest-bootstrap/spec.md) — Три состояния конфигурации задаются окружением и проверяются при старте | test:integration | частичное |
| [nest-bootstrap/datasource-and-migrations](.claude/docs/backend/node/nest-bootstrap/spec.md) — Хранилище подключается фабрикой, миграции идут отдельно | script:config-check | частичное |
| [nest-bootstrap/inject-by-port-tokens](.claude/docs/backend/node/nest-bootstrap/spec.md) — Зависимости внедряются через токены портов | dependency-cruiser:no-core-to-adapter | частичное |
| [nest-bootstrap/layout-directs-dependencies-inward](.claude/docs/backend/node/nest-bootstrap/spec.md) — Раскладка направляет зависимости внутрь | dependency-cruiser:no-core-to-adapter, ci:lint | частичное |
| [nest-bootstrap/liveness-and-readiness-split](.claude/docs/backend/node/nest-bootstrap/spec.md) — Проверки живости и готовности разделены | test:integration | частичное |
| [nest-bootstrap/local-quickstart-documented](.claude/docs/backend/node/nest-bootstrap/spec.md) — Локальный запуск описан | ревью | нет |
| [nest-bootstrap/no-blocking-in-request-path](.claude/docs/backend/node/nest-bootstrap/spec.md) — Блокирующие вызовы не выполняются в пути запроса | ревью | нет |
| [nest-bootstrap/profile-from-typed-config](.claude/docs/backend/node/nest-bootstrap/spec.md) — Профиль читается из типизированной конфигурации | eslint:no-process-env | частичное |
| [nest-bootstrap/root-module-is-composition-only](.claude/docs/backend/node/nest-bootstrap/spec.md) — Корневой модуль — только композиция | ревью | нет |
| [nest-bootstrap/shutdown-hooks-enabled](.claude/docs/backend/node/nest-bootstrap/spec.md) — Остановка закрывает ресурсы | ревью | нет |
| [nest-bootstrap/starts-locally-without-externals](.claude/docs/backend/node/nest-bootstrap/spec.md) — Сервис поднимается локально без живых внешних систем | ревью | нет |
| [node-style/async-await-not-chains](.claude/docs/backend/node/node-style/spec.md) — Асинхронность выражается ожиданием, а не цепочками | eslint:require-await | частичное |
| [node-style/deviation-requires-justification](.claude/docs/backend/node/node-style/spec.md) — Отступление от правила объясняется читаемостью | ревью | нет |
| [node-style/explicit-return-types](.claude/docs/backend/node/node-style/spec.md) — Публичные сигнатуры аннотированы | eslint:explicit-module-boundary-types | полное |
| [node-style/immutability-in-types](.claude/docs/backend/node/node-style/spec.md) — Неизменяемость выражается в типах | eslint:prefer-readonly | частичное |
| [node-style/imports-are-ordered-and-explicit](.claude/docs/backend/node/node-style/spec.md) — Импорты упорядочены и точные | eslint:import/order, eslint:no-unused-vars, eslint:import/no-cycle | частичное |
| [node-style/lint-and-format-enforced](.claude/docs/backend/node/node-style/spec.md) — Линтер и форматирование обязательны и едины | ci:lint, ci:typecheck | полное |
| [node-style/mechanical-versus-semantic-split](.claude/docs/backend/node/node-style/spec.md) — Граница между машинной и смысловой проверкой объявлена | ревью | нет |
| [node-style/named-exports-only](.claude/docs/backend/node/node-style/spec.md) — Экспорт именованный | eslint:no-default-export | полное |
| [node-style/naming-conventions](.claude/docs/backend/node/node-style/spec.md) — Именование следует конвенции | eslint:naming-convention | частичное |
| [node-style/no-comments-in-code](.claude/docs/backend/node/node-style/spec.md) — Комментариев в коде нет | ревью | нет |
| [node-style/no-floating-promises](.claude/docs/backend/node/node-style/spec.md) — Каждое обещание ожидается или обрабатывается | eslint:no-floating-promises, eslint:no-misused-promises | полное |
| [node-style/no-legacy-constructs](.claude/docs/backend/node/node-style/spec.md) — Устаревшие конструкции языка не используются | eslint:no-var, eslint:eqeqeq | частичное |
| [node-style/precise-money-and-time](.claude/docs/backend/node/node-style/spec.md) — Деньги и время выражены точными типами | ревью | нет |
| [node-style/simple-control-flow](.claude/docs/backend/node/node-style/spec.md) — Управляющие структуры плоские, выражения простые | eslint:complexity | частичное |
| [node-style/strict-compiler-settings](.claude/docs/backend/node/node-style/spec.md) — Компилятор настроен строго | ci:typecheck | частичное |
| [node-style/suppressions-are-justified](.claude/docs/backend/node/node-style/spec.md) — Подавления содержат код правила и обоснование | eslint:ban-ts-comment | частичное |
| [node-style/test-naming](.claude/docs/backend/node/node-style/spec.md) — Имя теста говорящее | ревью | нет |
| [node-style/unknown-not-any](.claude/docs/backend/node/node-style/spec.md) — Неизвестные данные типизируются как неизвестные | eslint:no-explicit-any, eslint:no-non-null-assertion | полное |
| [node-test-strategy/builders-and-time-precision](.claude/docs/backend/node/node-test-strategy/spec.md) — Объекты собираются построителями с разумными умолчаниями | ревью | нет |
| [node-test-strategy/database-preparer-per-context](.claude/docs/backend/node/node-test-strategy/spec.md) — Подготовка базы идёт через отдельный компонент | ревью | нет |
| [node-test-strategy/external-calls-are-stubbed](.claude/docs/backend/node/node-test-strategy/spec.md) — Внешние вызовы подменяются, стабы живут в тесте | ревью | нет |
| [node-test-strategy/integration-test-shape](.claude/docs/backend/node/node-test-strategy/spec.md) — Интеграционный тест поднимает приложение и настоящую базу | ревью | нет |
| [node-test-strategy/no-broker-or-cache](.claude/docs/backend/node/node-test-strategy/spec.md) — Брокер и кеш в интеграционных тестах не поднимаются | script:test-lint | частичное |
| [node-test-strategy/no-mocking-business-logic](.claude/docs/backend/node/node-test-strategy/spec.md) — Бизнес-логика в интеграционном тесте не подменяется | script:test-lint | частичное |
| [node-test-strategy/one-test-one-scenario](.claude/docs/backend/node/node-test-strategy/spec.md) — Один тест — один сценарий | ревью | нет |
| [node-test-strategy/schema-once-data-cleaned](.claude/docs/backend/node/node-test-strategy/spec.md) — Схема ставится один раз миграциями | script:test-lint | частичное |
| [node-test-strategy/setup-runs-once](.claude/docs/backend/node/node-test-strategy/spec.md) — Инфраструктура прогона поднимается один раз | ревью | нет |
| [node-test-strategy/test-auth-single-source](.claude/docs/backend/node/node-test-strategy/spec.md) — Тестовая авторизация собрана в одном месте | script:test-lint | частичное |
| [node-test-strategy/test-layers-separated](.claude/docs/backend/node/node-test-strategy/spec.md) — Слои тестов разделены по назначению | ci:test-layers | частичное |
| [node-test-strategy/test-name-states-scenario](.claude/docs/backend/node/node-test-strategy/spec.md) — Имя теста называет сценарий и правило | script:test-lint | частичное |
| [node-test-strategy/test-uses-shared-helper](.claude/docs/backend/node/node-test-strategy/spec.md) — Тест использует общий помощник и ходит по протоколу | ревью | нет |
| [node-test-strategy/tests-are-deterministic](.claude/docs/backend/node/node-test-strategy/spec.md) — Тесты детерминированы | script:test-lint | частичное |
| [observability/alerts-have-runbooks](.claude/docs/backend/observability/spec.md) — У каждого оповещения есть инструкция | ревью | нет |
| [observability/burn-rate-alerting](.claude/docs/backend/observability/spec.md) — Оповещения строятся на скорости сжигания бюджета | ревью | нет |
| [observability/context-propagated-to-async](.claude/docs/backend/observability/spec.md) — Контекст передаётся в асинхронные задачи | ревью | нет |
| [observability/context-set-at-edge-and-cleared](.claude/docs/backend/observability/spec.md) — Контекст заполняется на границе и обязательно очищается | ревью | нет |
| [observability/health-check-is-technical](.claude/docs/backend/observability/spec.md) — Проверка состояния не выполняет бизнес-операций | ревью | нет |
| [observability/health-indicator-per-system](.claude/docs/backend/observability/spec.md) — Каждая критичная внешняя система имеет свою проверку готовности | ревью | нет |
| [observability/liveness-and-readiness-split](.claude/docs/backend/observability/spec.md) — Проверки живости и готовности разделены | ревью | нет |
| [observability/log-levels-and-noise](.claude/docs/backend/observability/spec.md) — Уровни журнала используются по назначению | ревью | нет |
| [observability/logger-declared-uniformly](.claude/docs/backend/observability/spec.md) — Логгер объявляется единообразно | ревью | нет |
| [observability/logs-linked-to-traces](.claude/docs/backend/observability/spec.md) — Записи журнала связаны с трассировкой | ревью | нет |
| [observability/low-cardinality-labels](.claude/docs/backend/observability/spec.md) — Признаки метрик имеют низкую мощность | ревью | нет |
| [observability/management-endpoints-restricted](.claude/docs/backend/observability/spec.md) — Эндпоинты обслуживания закрыты и ограничены | script:config-check | частичное |
| [observability/manual-spans-are-closed](.claude/docs/backend/observability/spec.md) — Ручные отрезки закрываются и несут бизнес-контекст | ревью | нет |
| [observability/metric-naming](.claude/docs/backend/observability/spec.md) — Имена метрик единообразны и содержат единицу | ревью | нет |
| [observability/metrics-are-exported](.claude/docs/backend/observability/spec.md) — Метрики экспортируются в согласованном формате | ci:metrics-check | частичное |
| [observability/no-direct-stdout-logging](.claude/docs/backend/observability/spec.md) — Вывод в поток процесса не используется | java: errorprone:SystemOut · python: ruff:T201 · go: golangci-lint:forbidigo · node: eslint:no-console | полное |
| [observability/no-pii-in-logs](.claude/docs/backend/observability/spec.md) — Персональные данные и тела запросов не попадают в журнал | ревью | нет |
| [observability/parameterized-log-messages](.claude/docs/backend/observability/spec.md) — Записи журнала параметризованы и несут исключение целиком | java: ревью · python: ruff:G003 · go: ревью · node: ревью | частичное |
| [observability/red-and-use-metrics](.claude/docs/backend/observability/spec.md) — Покрыты частота, ошибки, задержка и ресурсы | ревью | нет |
| [observability/request-context-in-every-record](.claude/docs/backend/observability/spec.md) — В каждой записи есть контекст запроса | ревью | нет |
| [observability/sampling-strategy](.claude/docs/backend/observability/spec.md) — Доля собираемых трассировок ограничена, ошибки собираются полностью | ревью | нет |
| [observability/separate-management-port](.claude/docs/backend/observability/spec.md) — Порт обслуживания отделён от рабочего | script:config-check | полное |
| [observability/slo-with-error-budget](.claude/docs/backend/observability/spec.md) — У критичных операций есть цель уровня обслуживания с бюджетом ошибок | ревью | нет |
| [observability/standard-metric-dimensions](.claude/docs/backend/observability/spec.md) — Метрики размечены стандартным набором признаков | ревью | нет |
| [observability/structured-logs-in-production](.claude/docs/backend/observability/spec.md) — В промышленной среде журнал структурированный | script:config-check | частичное |
| [observability/tracing-auto-instrumented](.claude/docs/backend/observability/spec.md) — Трассировка включена автоматической обвязкой | ревью | нет |
| [payment-integration/act-only-if-not-terminal](.claude/docs/backend/payment-integration/spec.md) — Списание выполняется только для незавершённой операции | ревью | нет |
| [payment-integration/business-decline-is-terminal](.claude/docs/backend/payment-integration/spec.md) — Бизнес-отказ переводит операцию в конечное состояние | ревью | нет |
| [payment-integration/concurrent-attempts-serialized](.claude/docs/backend/payment-integration/spec.md) — Одновременные попытки оплаты одного заказа сериализуются | ревью | нет |
| [payment-integration/domain-values-outside-adapter](.claude/docs/backend/payment-integration/spec.md) — Наружу отдаются доменные значения | java: archunit:GeneratedDtoStaysInAdapterTest · python: ревью · go: ревью · node: ревью | частичное |
| [payment-integration/idempotent-by-natural-key](.claude/docs/backend/payment-integration/spec.md) — Операция идемпотентна по естественному ключу | ревью | нет |
| [payment-integration/money-is-decimal](.claude/docs/backend/payment-integration/spec.md) — Суммы считаются точным десятичным типом | ревью | нет |
| [payment-integration/money-operations-leave-trace](.claude/docs/backend/payment-integration/spec.md) — Денежная операция оставляет след | ci:metrics-check | частичное |
| [payment-integration/no-sensitive-payment-data-in-logs](.claude/docs/backend/payment-integration/spec.md) — Чувствительные данные не покидают адаптер | gitleaks:default | частичное |
| [payment-integration/partial-update-of-domain-record](.claude/docs/backend/payment-integration/spec.md) — Обновление доменной записи частичное | ревью | нет |
| [payment-integration/read-before-write](.claude/docs/backend/payment-integration/spec.md) — Перед созданием операции проверяется её наличие | ревью | нет |
| [payment-integration/reconciliation-pass](.claude/docs/backend/payment-integration/spec.md) — Незавершённые операции добираются фоновым проходом | ревью | нет |
| [payment-integration/single-status-mapper](.claude/docs/backend/payment-integration/spec.md) — Коды провайдера интерпретируются в одном месте | ревью | нет |
| [payment-integration/stale-operations-closed-by-ttl](.claude/docs/backend/payment-integration/spec.md) — Зависшие операции закрываются по сроку | ревью | нет |
| [payment-integration/transport-and-business-errors-differ](.claude/docs/backend/payment-integration/spec.md) — Транспорт и бизнес различаются типом ошибки | java: spotbugs:REC_CATCH_EXCEPTION · python: ruff:BLE001 · go: golangci-lint:errcheck · node: eslint:no-empty | частичное |
| [payment-integration/transport-error-keeps-operation-retryable](.claude/docs/backend/payment-integration/spec.md) — Транспортная ошибка не финализирует платёж | ревью | нет |
| [pg-indexes/brin-for-append-only](.claude/docs/backend/pg-indexes/spec.md) — Блочно-диапазонный индекс — для больших упорядоченных таблиц | ревью | нет |
| [pg-indexes/btree-by-default](.claude/docs/backend/pg-indexes/spec.md) — Обычное дерево — выбор по умолчанию | ревью | нет |
| [pg-indexes/composite-left-prefix](.claude/docs/backend/pg-indexes/spec.md) — Составной индекс работает на левый префикс | ревью | нет |
| [pg-indexes/condition-must-be-index-key](.claude/docs/backend/pg-indexes/spec.md) — Важное условие обязано быть ключом, а не фильтром | ревью | нет |
| [pg-indexes/covering-index-include](.claude/docs/backend/pg-indexes/spec.md) — Покрывающий индекс несёт дополнительные колонки в листьях | ревью | нет |
| [pg-indexes/equality-first-range-last](.claude/docs/backend/pg-indexes/spec.md) — Первым в индексе — поле равенства, диапазоны последними | ревью | нет |
| [pg-indexes/estimate-versus-actual](.claude/docs/backend/pg-indexes/spec.md) — Оценка сверяется с фактом, время умножается на число проходов | ревью | нет |
| [pg-indexes/explain-is-not-monitoring](.claude/docs/backend/pg-indexes/spec.md) — План не заменяет наблюдение за базой | ревью | нет |
| [pg-indexes/explain-with-analyze-and-buffers](.claude/docs/backend/pg-indexes/spec.md) — План снимается с выполнением и с буферами | ревью | нет |
| [pg-indexes/extended-statistics-for-correlated-columns](.claude/docs/backend/pg-indexes/spec.md) — Неравномерные и коррелирующие данные требуют расширенной статистики | ревью | нет |
| [pg-indexes/functional-index-matches-expression](.claude/docs/backend/pg-indexes/spec.md) — Функциональный индекс совпадает с выражением запроса | ревью | нет |
| [pg-indexes/gin-for-documents-and-search](.claude/docs/backend/pg-indexes/spec.md) — Обратный индекс — для документов, массивов и текстового поиска | ревью | нет |
| [pg-indexes/gist-for-ranges-and-geometry](.claude/docs/backend/pg-indexes/spec.md) — Индекс для интервалов и геометрии — свой вид | ревью | нет |
| [pg-indexes/heap-fetches-mean-stale-visibility-map](.claude/docs/backend/pg-indexes/spec.md) — Обращения к таблице при индексном чтении означают устаревшую карту видимости | ревью | нет |
| [pg-indexes/index-foreign-keys](.claude/docs/backend/pg-indexes/spec.md) — Внешний ключ индексируется, если по нему ходят | script:ddl-check | частичное |
| [pg-indexes/keep-statistics-fresh](.claude/docs/backend/pg-indexes/spec.md) — Статистика поддерживается в актуальном состоянии | ревью | нет |
| [pg-indexes/no-redundant-prefix-index](.claude/docs/backend/pg-indexes/spec.md) — Дублирующие индексы не заводятся | script:ddl-check | частичное |
| [pg-indexes/order-by-matches-index](.claude/docs/backend/pg-indexes/spec.md) — Сортировка совпадает с порядком индекса | ревью | нет |
| [pg-indexes/parallel-plan-needs-volume](.claude/docs/backend/pg-indexes/spec.md) — Параллельный план оправдан объёмом | ревью | нет |
| [pg-indexes/partial-index-for-subset](.claude/docs/backend/pg-indexes/spec.md) — Частичный индекс — когда нужен не весь набор | ревью | нет |
| [pg-indexes/random-page-cost-matches-storage](.claude/docs/backend/pg-indexes/spec.md) — Стоимость случайного чтения соответствует носителю | ревью | нет |
| [pg-indexes/selectivity-decides](.claude/docs/backend/pg-indexes/spec.md) — Селективность решает, будет ли индекс использован | ревью | нет |
| [pg-indexes/work-mem-signals](.claude/docs/backend/pg-indexes/spec.md) — Признаки нехватки рабочей памяти читаются в плане | ревью | нет |
| [pg-migrations/add-column-not-null](.claude/docs/backend/pg-migrations/spec.md) — ADD COLUMN NOT NULL — только с DEFAULT или через expand-contract | squawk:adding-required-field | частичное |
| [pg-migrations/alter-type-rewrites-table](.claude/docs/backend/pg-migrations/spec.md) — ALTER TYPE переписывает таблицу целиком | squawk:changing-column-type | частичное |
| [pg-migrations/backfill-job-not-migration](.claude/docs/backend/pg-migrations/spec.md) — Backfill больших таблиц живёт в коде, не в миграции | ревью | нет |
| [pg-migrations/batched-data-migration](.claude/docs/backend/pg-migrations/spec.md) — Массовые UPDATE идут батчами | script:ddl-check | частичное |
| [pg-migrations/breaking-change-definition](.claude/docs/backend/pg-migrations/spec.md) — Breaking-изменение опознаётся до написания миграции | ревью | нет |
| [pg-migrations/canary-rollout](.claude/docs/backend/pg-migrations/spec.md) — Миграция катится канареечно | ревью | нет |
| [pg-migrations/drop-column-after-code](.claude/docs/backend/pg-migrations/spec.md) — DROP COLUMN — после того, как код перестал её упоминать | squawk:ban-drop-column | частичное |
| [pg-migrations/enum-add-value-separate-changeset](.claude/docs/backend/pg-migrations/spec.md) — ALTER TYPE ADD VALUE идёт отдельным changeset'ом | squawk:transaction-nesting | частичное |
| [pg-migrations/enum-rename-value](.claude/docs/backend/pg-migrations/spec.md) — Переименование enum-значения координируется с кодом | ревью | нет |
| [pg-migrations/enum-value-removal-via-shadow-type](.claude/docs/backend/pg-migrations/spec.md) — Enum-значение удаляется через теневой тип | ревью | нет |
| [pg-migrations/expand-contract-three-releases](.claude/docs/backend/pg-migrations/spec.md) — Breaking-изменение режется на три и более релиза | ревью | нет |
| [pg-migrations/fk-not-valid-then-validate](.claude/docs/backend/pg-migrations/spec.md) — FK добавляется как NOT VALID, затем валидируется | squawk:constraint-missing-not-valid | частичное |
| [pg-migrations/index-concurrently](.claude/docs/backend/pg-migrations/spec.md) — Индексы создаются и удаляются CONCURRENTLY | squawk:require-concurrent-index-creation, squawk:require-concurrent-index-deletion | частичное |
| [pg-migrations/lock-queue-stall](.claude/docs/backend/pg-migrations/spec.md) — Долгий SELECT превращает ALTER TABLE в остановку сервиса | ревью | нет |
| [pg-migrations/lock-timeout-required](.claude/docs/backend/pg-migrations/spec.md) — lock_timeout в каждой миграции с ALTER TABLE | script:ddl-check | частичное |
| [pg-migrations/migration-linter-required](.claude/docs/backend/pg-migrations/spec.md) — Линтер миграций стоит в pre-commit и в CI | ci:lint-migrations | частичное |
| [pg-migrations/n-minus-one-ci-check](.claude/docs/backend/pg-migrations/spec.md) — Совместимость проверяется джобой CI | ci:n-minus-one | частичное |
| [pg-migrations/n-minus-one-compatibility](.claude/docs/backend/pg-migrations/spec.md) — N-1 совместимость с предыдущей версией кода | squawk:adding-required-field | частичное |
| [pg-migrations/no-down-migrations](.claude/docs/backend/pg-migrations/spec.md) — Down-миграций на проде не бывает | script:ddl-check | частичное |
| [pg-migrations/rename-column-expand-contract](.claude/docs/backend/pg-migrations/spec.md) — RENAME COLUMN не бывает одним коммитом | script:ddl-check | частичное |
| [pg-migrations/rewriting-operations-known](.claude/docs/backend/pg-migrations/spec.md) — Операции, переписывающие таблицу, названы явно | squawk:changing-column-type, squawk:constraint-missing-not-valid | частичное |
| [pg-migrations/rollback-is-forward-fix](.claude/docs/backend/pg-migrations/spec.md) — Настоящий откат — forward-fix | ревью | нет |
| [pg-migrations/set-not-null-via-check](.claude/docs/backend/pg-migrations/spec.md) — SET NOT NULL через CHECK NOT VALID | ревью | нет |
| [pg-migrations/table-drop-after-release](.claude/docs/backend/pg-migrations/spec.md) — DROP и RENAME TABLE — вторым релизом | script:ddl-check | частичное |
| [pg-naming/audit-columns-set](.claude/docs/backend/pg-naming/spec.md) — Набор колонок аудита единый | ревью | нет |
| [pg-naming/boolean-column-prefix](.claude/docs/backend/pg-naming/spec.md) — Булева колонка названа вопросом | script:ddl-check | частичное |
| [pg-naming/count-column-suffix](.claude/docs/backend/pg-naming/spec.md) — Размер коллекции называется счётчиком | ревью | нет |
| [pg-naming/document-column-meaningful-name](.claude/docs/backend/pg-naming/spec.md) — Имя документа говорит о содержимом | script:ddl-check | частичное |
| [pg-naming/domain-schema-split](.claude/docs/backend/pg-naming/spec.md) — Крупная схема разделена по доменам | ревью | нет |
| [pg-naming/duration-unit-in-name](.claude/docs/backend/pg-naming/spec.md) — Длительность называет единицу измерения | script:ddl-check | частичное |
| [pg-naming/enum-column-plain-name](.claude/docs/backend/pg-naming/spec.md) — Колонка перечисления называется по смыслу | ревью | нет |
| [pg-naming/fk-column-names-parent](.claude/docs/backend/pg-naming/spec.md) — Внешний ключ называет родителя | ревью | нет |
| [pg-naming/index-constraint-prefix](.claude/docs/backend/pg-naming/spec.md) — Индексы и ограничения названы по типу | script:ddl-check | частичное |
| [pg-naming/index-name-reflects-shape](.claude/docs/backend/pg-naming/spec.md) — Имя индекса отражает его устройство | ревью | нет |
| [pg-naming/junction-table-name](.claude/docs/backend/pg-naming/spec.md) — Связующая таблица называется обеими сущностями | ревью | нет |
| [pg-naming/money-column-suffix](.claude/docs/backend/pg-naming/spec.md) — Денежная колонка называет назначение | ревью | нет |
| [pg-naming/no-reserved-words](.claude/docs/backend/pg-naming/spec.md) — Зарезервированные слова не берутся в имена | script:ddl-check, test:integration | частичное |
| [pg-naming/pk-named-id](.claude/docs/backend/pg-naming/spec.md) — Ключ таблицы называется id | ревью | нет |
| [pg-naming/short-names-consistent-abbreviations](.claude/docs/backend/pg-naming/spec.md) — Имена короткие и сокращения единые | script:ddl-check | частичное |
| [pg-naming/snake-case-no-quotes](.claude/docs/backend/pg-naming/spec.md) — Один регистр, без кавычек | script:ddl-check | частичное |
| [pg-naming/soft-delete-keeps-moment](.claude/docs/backend/pg-naming/spec.md) — Мягкое удаление хранит момент | script:ddl-check | частичное |
| [pg-naming/table-singular-noun](.claude/docs/backend/pg-naming/spec.md) — Таблица — существительное в единственном числе | ревью | нет |
| [pg-naming/time-column-suffix](.claude/docs/backend/pg-naming/spec.md) — Время в имени, тип — в DDL | script:ddl-check | частичное |
| [pg-naming/view-suffix](.claude/docs/backend/pg-naming/spec.md) — Представления помечены суффиксом | script:ddl-check | частичное |
| [pg-partitioning/balanced-partitions](.claude/docs/backend/pg-partitioning/spec.md) — Нагрузка распределена по секциям сравнимо | ревью | нет |
| [pg-partitioning/create-partitions-ahead](.claude/docs/backend/pg-partitioning/spec.md) — Секции создаются заранее | ревью | нет |
| [pg-partitioning/drop-partition-not-delete](.claude/docs/backend/pg-partitioning/spec.md) — Старые данные удаляются отсоединением или удалением секции | ревью | нет |
| [pg-partitioning/foreign-key-directions](.claude/docs/backend/pg-partitioning/spec.md) — Направления внешних ключей учитывают ограничения | test:integration | частичное |
| [pg-partitioning/indexes-on-parent](.claude/docs/backend/pg-partitioning/spec.md) — Индексы объявляются на родительской таблице | ревью | нет |
| [pg-partitioning/key-present-in-queries](.claude/docs/backend/pg-partitioning/spec.md) — Ключ секционирования стоит в условии почти всех запросов | ревью | нет |
| [pg-partitioning/migrate-via-shadow-table](.claude/docs/backend/pg-partitioning/spec.md) — Существующая таблица переезжает через теневую | ревью | нет |
| [pg-partitioning/partition-key-immutable](.claude/docs/backend/pg-partitioning/spec.md) — Ключ секционирования неизменен | ревью | нет |
| [pg-partitioning/partition-only-when-justified](.claude/docs/backend/pg-partitioning/spec.md) — Партиционирование берётся по признакам, а не впрок | ревью | нет |
| [pg-partitioning/partition-size-range](.claude/docs/backend/pg-partitioning/spec.md) — Размер секции держится в рабочем диапазоне | ревью | нет |
| [pg-partitioning/partition-type-matches-data](.claude/docs/backend/pg-partitioning/spec.md) — Вид секционирования выбирается по природе данных | ревью | нет |
| [pg-partitioning/pk-includes-partition-key](.claude/docs/backend/pg-partitioning/spec.md) — Ключ секционирования входит в первичный ключ | script:ddl-check, test:integration | частичное |
| [pg-runtime/advisory-lock-for-singleton](.claude/docs/backend/pg-runtime/spec.md) — Одиночное выполнение обеспечивается рекомендательной блокировкой | ревью | нет |
| [pg-runtime/autovacuum-tuning-per-table](.claude/docs/backend/pg-runtime/spec.md) — Настройки фоновой очистки меняются точечно | script:ddl-check | частичное |
| [pg-runtime/bloat-monitoring](.claude/docs/backend/pg-runtime/spec.md) — Раздувание под наблюдением | ревью | нет |
| [pg-runtime/bulk-load-via-copy](.claude/docs/backend/pg-runtime/spec.md) — Массовая загрузка идёт потоковой командой, а не циклом вставок | ревью | нет |
| [pg-runtime/connection-budget-shared](.claude/docs/backend/pg-runtime/spec.md) — Бюджет соединений сервера поделен между всеми потребителями | ревью | нет |
| [pg-runtime/deadlock-prevention-by-order](.claude/docs/backend/pg-runtime/spec.md) — Взаимные блокировки лечатся порядком, а не повторами | ревью | нет |
| [pg-runtime/default-isolation-is-right](.claude/docs/backend/pg-runtime/spec.md) — Уровень изоляции по умолчанию не поднимают без причины | ревью | нет |
| [pg-runtime/fillfactor-for-hot-updates](.claude/docs/backend/pg-runtime/spec.md) — Обновляемые таблицы оставляют место на странице | script:ddl-check | частичное |
| [pg-runtime/idle-in-transaction-timeout](.claude/docs/backend/pg-runtime/spec.md) — Простаивающие транзакции убиваются сервером | ревью | нет |
| [pg-runtime/isolation-declared-per-operation](.claude/docs/backend/pg-runtime/spec.md) — Уровень изоляции объявляется на конкретной операции | ревью | нет |
| [pg-runtime/isolation-is-not-a-constraint](.claude/docs/backend/pg-runtime/spec.md) — Изоляция не заменяет ограничений схемы | ревью | нет |
| [pg-runtime/leak-detection-enabled](.claude/docs/backend/pg-runtime/spec.md) — Обнаружение утечек соединений включено | script:config-check | полное |
| [pg-runtime/lock-timeout-for-critical-operations](.claude/docs/backend/pg-runtime/spec.md) — Критичные операции ограничены временем ожидания блокировки | ревью | нет |
| [pg-runtime/locking-select-needs-index-and-limit](.claude/docs/backend/pg-runtime/spec.md) — Блокирующая выборка ограничена индексом и числом строк | ревью | нет |
| [pg-runtime/no-dangling-prepared-transactions](.claude/docs/backend/pg-runtime/spec.md) — Подготовленные транзакции не остаются висеть | ревью | нет |
| [pg-runtime/no-vacuum-full-in-production](.claude/docs/backend/pg-runtime/spec.md) — Полная перестройка таблицы не применяется на проде | script:ddl-check | частичное |
| [pg-runtime/nowait-for-bounded-latency](.claude/docs/backend/pg-runtime/spec.md) — Там, где ждать нельзя, блокировка отказывает сразу | ревью | нет |
| [pg-runtime/pessimistic-versus-optimistic](.claude/docs/backend/pg-runtime/spec.md) — Выбор между пессимистичной и оптимистичной блокировкой обоснован | ревью | нет |
| [pg-runtime/pool-metrics-observed](.claude/docs/backend/pg-runtime/spec.md) — Метрики пула наблюдаются | ci:metrics-check | частичное |
| [pg-runtime/pool-settings-complete](.claude/docs/backend/pg-runtime/spec.md) — Пул настроен полностью и предсказуемо | script:config-check | частичное |
| [pg-runtime/pool-size-is-calculated](.claude/docs/backend/pg-runtime/spec.md) — Размер пула соединений считается, а не увеличивается наугад | ревью | нет |
| [pg-runtime/pool-sizing-with-pooler](.claude/docs/backend/pg-runtime/spec.md) — С посредником пул приложения может быть шире | ревью | нет |
| [pg-runtime/pooler-transaction-mode-constraints](.claude/docs/backend/pg-runtime/spec.md) — Транзакционный режим посредника накладывает ограничения | ревью | нет |
| [pg-runtime/pooler-when-justified](.claude/docs/backend/pg-runtime/spec.md) — Посредник соединений берётся по показаниям | ревью | нет |
| [pg-runtime/read-replica-separate-datasource](.claude/docs/backend/pg-runtime/spec.md) — Реплика для чтения — отдельный источник данных | ревью | нет |
| [pg-runtime/repeatable-read-for-consistent-snapshot](.claude/docs/backend/pg-runtime/spec.md) — Повторяемое чтение — для согласованного среза | ревью | нет |
| [pg-runtime/replication-slots-watched](.claude/docs/backend/pg-runtime/spec.md) — Слоты репликации под наблюдением | ревью | нет |
| [pg-runtime/retry-on-serialization-failure](.claude/docs/backend/pg-runtime/spec.md) — На повышенном уровне обязателен повтор транзакции | ревью | нет |
| [pg-runtime/row-lock-inside-transaction](.claude/docs/backend/pg-runtime/spec.md) — Блокировка строки берётся осознанно и внутри транзакции | ревью | нет |
| [pg-runtime/serializable-for-cross-row-invariants](.claude/docs/backend/pg-runtime/spec.md) — Полная изоляция — для инвариантов, не выразимых иначе | ревью | нет |
| [pg-runtime/short-transactions](.claude/docs/backend/pg-runtime/spec.md) — Транзакции короткие, внешних вызовов внутри нет | java: archunit:NoExternalCallInTransactionTest · python: ревью · go: ревью · node: ревью | частичное |
| [pg-runtime/single-pool-per-database](.claude/docs/backend/pg-runtime/spec.md) — Одно приложение — один пул на базу | script:config-check | частичное |
| [pg-runtime/skip-locked-for-queues](.claude/docs/backend/pg-runtime/spec.md) — Очередь и рассылка событий пропускают занятые строки | ревью | нет |
| [pg-runtime/synchronous-commit-scope](.claude/docs/backend/pg-runtime/spec.md) — Ослабление гарантий фиксации — только для данных, которые можно потерять | ревью | нет |
| [pg-runtime/toast-large-values-separately](.claude/docs/backend/pg-runtime/spec.md) — Большие значения хранятся отдельно и не переписываются зря | ревью | нет |
| [pg-runtime/unlogged-for-disposable-data](.claude/docs/backend/pg-runtime/spec.md) — Данные, которые не жалко потерять, не пишутся в журнал | ревью | нет |
| [pg-runtime/vacuum-analyze-after-bulk-change](.claude/docs/backend/pg-runtime/spec.md) — После массового изменения данных запускается очистка и сбор статистики | ревью | нет |
| [pg-types/array-for-simple-scalars](.claude/docs/backend/pg-types/spec.md) — Массив — для простых скаляров без идентичности | ревью | нет |
| [pg-types/boolean-is-boolean](.claude/docs/backend/pg-types/spec.md) — Булево — это boolean | script:ddl-check | частичное |
| [pg-types/business-time-is-timestamptz](.claude/docs/backend/pg-types/spec.md) — Бизнес-время — timestamptz | script:ddl-check | частичное |
| [pg-types/case-insensitive-via-citext](.claude/docs/backend/pg-types/spec.md) — Регистронезависимые поля — типом или индексом | ревью | нет |
| [pg-types/enum-vs-reference-table](.claude/docs/backend/pg-types/spec.md) — Перечисление — тип, справочник или ограничение по смыслу | ревью | нет |
| [pg-types/exclude-constraint-for-overlap](.claude/docs/backend/pg-types/spec.md) — Непересечение интервалов держит ограничение исключения | ревью | нет |
| [pg-types/float-only-for-inexact](.claude/docs/backend/pg-types/spec.md) — Плавающая точка — только там, где неточность уместна | ревью | нет |
| [pg-types/index-fk-under-uuid-pk](.claude/docs/backend/pg-types/spec.md) — Под UUID-ключом внешние ключи индексируются явно | ревью | нет |
| [pg-types/intervals-not-magic-seconds](.claude/docs/backend/pg-types/spec.md) — Смещения во времени — интервалом, не числом | ревью | нет |
| [pg-types/jsonb-for-peripheral-attributes](.claude/docs/backend/pg-types/spec.md) — JSON — для периферийных атрибутов, не для основных полей | ревью | нет |
| [pg-types/jsonb-index-matches-query](.claude/docs/backend/pg-types/spec.md) — Индекс под JSON соответствует виду запроса | ревью | нет |
| [pg-types/jsonb-not-json](.claude/docs/backend/pg-types/spec.md) — Двоичный JSON, а не текстовый | ревью | нет |
| [pg-types/money-is-numeric](.claude/docs/backend/pg-types/spec.md) — Деньги — numeric с явной точностью | script:ddl-check | частичное |
| [pg-types/no-binary-in-jsonb](.claude/docs/backend/pg-types/spec.md) — В JSON не кладут двоичные данные и длинные тексты | ревью | нет |
| [pg-types/no-premature-column-split](.claude/docs/backend/pg-types/spec.md) — Таблицу не делят ради длинного текста | ревью | нет |
| [pg-types/now-vs-clock-timestamp](.claude/docs/backend/pg-types/spec.md) — Функции текущего времени различаются осознанно | ревью | нет |
| [pg-types/pk-bigint-identity](.claude/docs/backend/pg-types/spec.md) — Первичный ключ — bigint с identity | script:ddl-check | частичное |
| [pg-types/range-for-intervals](.claude/docs/backend/pg-types/spec.md) — Интервал — типом интервала, а не парой колонок | ревью | нет |
| [pg-types/smallint-only-for-short-scale](.claude/docs/backend/pg-types/spec.md) — smallint — только для короткой шкалы | ревью | нет |
| [pg-types/text-by-default](.claude/docs/backend/pg-types/spec.md) — Строка без доменного ограничения — text | script:ddl-check | частичное |
| [pg-types/time-mapping-keeps-zone](.claude/docs/backend/pg-types/spec.md) — Отображение времени в код не теряет зону | gradle:jooq-codegen | частичное |
| [pg-types/time-through-clock-service](.claude/docs/backend/pg-types/spec.md) — Время в коде идёт через подменяемый источник | ревью | нет |
| [pg-types/typed-enum-in-code](.claude/docs/backend/pg-types/spec.md) — В коде перечисление типизировано | gradle:jooq-codegen | частичное |
| [pg-types/utf8-cluster](.claude/docs/backend/pg-types/spec.md) — Кластер в UTF8 | ревью | нет |
| [pg-types/uuid-is-uuid-type](.claude/docs/backend/pg-types/spec.md) — UUID хранится типом uuid | script:ddl-check | частичное |
| [pg-types/uuid-only-when-justified](.claude/docs/backend/pg-types/spec.md) — UUID берётся по делу, а не по умолчанию | ревью | нет |
| [pg-types/uuid-v7-for-keys](.claude/docs/backend/pg-types/spec.md) — Ключи на UUID — версии, упорядоченной по времени | ревью | нет |
| [pg-types/varchar-when-domain-rule](.claude/docs/backend/pg-types/spec.md) — varchar и char — когда длина есть доменное правило | ревью | нет |
| [python-bootstrap/app-factory](.claude/docs/backend/python/python-bootstrap/spec.md) — Приложение собирается фабрикой | ревью | нет |
| [python-bootstrap/clock-and-ids-behind-protocols](.claude/docs/backend/python/python-bootstrap/spec.md) — Источники недетерминизма скрыты за интерфейсами | ruff:DTZ005 | частичное |
| [python-bootstrap/explicit-di-composition](.claude/docs/backend/python/python-bootstrap/spec.md) — Зависимости собираются явной композицией | ревью | нет |
| [python-bootstrap/layout-directs-dependencies-inward](.claude/docs/backend/python/python-bootstrap/spec.md) — Раскладка направляет зависимости внутрь | import-linter:layers | частичное |
| [python-bootstrap/liveness-and-readiness-split](.claude/docs/backend/python/python-bootstrap/spec.md) — Проверки живости и готовности разделены | test:integration | частичное |
| [python-bootstrap/local-quickstart-documented](.claude/docs/backend/python/python-bootstrap/spec.md) — Локальный запуск описан | ревью | нет |
| [python-bootstrap/no-blocking-in-async-handlers](.claude/docs/backend/python/python-bootstrap/spec.md) — Блокирующие вызовы не выполняются в асинхронных обработчиках | ruff:ASYNC210, ruff:ASYNC230, ruff:ASYNC251 | частичное |
| [python-bootstrap/observability-configured-in-factory](.claude/docs/backend/python/python-bootstrap/spec.md) — Наблюдаемость настраивается в фабрике | ревью | нет |
| [python-bootstrap/persistence-wiring](.claude/docs/backend/python/python-bootstrap/spec.md) — Хранилище подключается асинхронно, миграции идут отдельно | ревью | нет |
| [python-bootstrap/profile-from-environment](.claude/docs/backend/python/python-bootstrap/spec.md) — Профиль выбирается окружением, а не кодом | ревью | нет |
| [python-bootstrap/resources-in-lifespan](.claude/docs/backend/python/python-bootstrap/spec.md) — Ресурсы живут в жизненном цикле приложения | ревью | нет |
| [python-bootstrap/server-and-shutdown](.claude/docs/backend/python/python-bootstrap/spec.md) — Сервер и остановка настроены | ревью | нет |
| [python-bootstrap/single-settings-object](.claude/docs/backend/python/python-bootstrap/spec.md) — Разрозненное чтение окружения не применяется | ruff:PLW1508 | частичное |
| [python-bootstrap/three-env-profiles](.claude/docs/backend/python/python-bootstrap/spec.md) — Три состояния конфигурации задаются окружением | test:integration | частичное |
| [python-style/decimal-money-aware-datetime](.claude/docs/backend/python/python-style/spec.md) — Деньги и время выражаются точными типами | ruff:DTZ005 | частичное |
| [python-style/deviation-requires-justification](.claude/docs/backend/python/python-style/spec.md) — Отступление от правила объясняется читаемостью | ревью | нет |
| [python-style/docstrings-add-contract](.claude/docs/backend/python/python-style/spec.md) — Строка документации добавляет контракт, а не пересказ | ревью | нет |
| [python-style/eafp-versus-lbyl](.claude/docs/backend/python/python-style/spec.md) — Выбор между попыткой и проверкой осознан | ревью | нет |
| [python-style/expressions-stay-simple](.claude/docs/backend/python/python-style/spec.md) — Выражения простые и явные | ruff:SIM108, ruff:UP032, ruff:PTH118 | частичное |
| [python-style/formatting-by-tool](.claude/docs/backend/python/python-style/spec.md) — Форматирование выполняется инструментом | ruff:format, ci:lint | полное |
| [python-style/imports-are-absolute-and-explicit](.claude/docs/backend/python/python-style/spec.md) — Импорты абсолютные, точные и используемые | ruff:TID252, ruff:F403, ruff:F401, ruff:I001 | полное |
| [python-style/lint-and-types-are-enforced](.claude/docs/backend/python/python-style/spec.md) — Линтер и проверка типов обязательны и настроены в одном месте | ci:lint, mypy:strict | частичное |
| [python-style/mechanical-versus-semantic-split](.claude/docs/backend/python/python-style/spec.md) — Граница между машинной и смысловой проверкой объявлена | ревью | нет |
| [python-style/modern-constructs](.claude/docs/backend/python/python-style/spec.md) — Современные конструкции применяются по назначению | ruff:UP, ревью | частичное |
| [python-style/naming-conventions](.claude/docs/backend/python/python-style/spec.md) — Именование следует конвенции языка | ruff:N801, ruff:N802, ruff:N806 | частичное |
| [python-style/no-bare-except](.claude/docs/backend/python/python-style/spec.md) — Широкий перехват не остаётся без обработки | ruff:E722, ruff:BLE001 | частичное |
| [python-style/no-comments-in-code](.claude/docs/backend/python/python-style/spec.md) — Комментариев в коде нет | ruff:ERA001 | частичное |
| [python-style/no-mutable-default-argument](.claude/docs/backend/python/python-style/spec.md) — Изменяемое значение по умолчанию не используется | ruff:B006 | полное |
| [python-style/no-mutation-during-iteration](.claude/docs/backend/python/python-style/spec.md) — Коллекция не изменяется во время обхода | ruff:B909 | частичное |
| [python-style/no-silencing-type-checks](.claude/docs/backend/python/python-style/spec.md) — Проверка типов не заглушается | ruff:PGH003, mypy:strict | частичное |
| [python-style/no-type-in-name](.claude/docs/backend/python/python-style/spec.md) — Тип не выносится в имя | ревью | нет |
| [python-style/ports-via-protocols](.claude/docs/backend/python/python-style/spec.md) — Порты описываются структурной типизацией | ревью | нет |
| [python-style/privacy-and-short-names](.claude/docs/backend/python/python-style/spec.md) — Приватность и короткие имена используются по назначению | ruff:E741 | частичное |
| [python-style/suppressions-are-justified](.claude/docs/backend/python/python-style/spec.md) — Подавления линтера снабжены кодом и обоснованием | ruff:PGH004 | частичное |
| [python-style/test-naming](.claude/docs/backend/python/python-style/spec.md) — Имя теста называет сценарий | ревью | нет |
| [python-style/typed-public-signatures](.claude/docs/backend/python/python-style/spec.md) — Публичные сигнатуры аннотированы, проверка типов строгая | mypy:strict, ruff:UP007 | частичное |
| [python-test-strategy/builders-with-defaults](.claude/docs/backend/python/python-test-strategy/spec.md) — Объекты собираются построителями с разумными умолчаниями | ruff:DTZ001 | частичное |
| [python-test-strategy/database-preparer-per-context](.claude/docs/backend/python/python-test-strategy/spec.md) — Подготовка базы идёт через отдельный компонент | ревью | нет |
| [python-test-strategy/external-calls-via-stub-server](.claude/docs/backend/python/python-test-strategy/spec.md) — Внешние вызовы подменяются сервером, стабы живут в тесте | ревью | нет |
| [python-test-strategy/fixtures-are-layered](.claude/docs/backend/python/python-test-strategy/spec.md) — Фикстуры разложены по уровням, дорогое поднимается один раз | ревью | нет |
| [python-test-strategy/integration-test-shape](.claude/docs/backend/python/python-test-strategy/spec.md) — Интеграционный тест поднимает приложение и настоящую базу | ревью | нет |
| [python-test-strategy/no-broker-or-cache-in-integration-tests](.claude/docs/backend/python/python-test-strategy/spec.md) — Брокер и кеш в интеграционных тестах не поднимаются | script:test-lint | частичное |
| [python-test-strategy/no-mocking-business-logic](.claude/docs/backend/python/python-test-strategy/spec.md) — Бизнес-логика в интеграционном тесте не подменяется | script:test-lint | частичное |
| [python-test-strategy/one-test-one-scenario](.claude/docs/backend/python/python-test-strategy/spec.md) — Один тест — один сценарий | ревью | нет |
| [python-test-strategy/schema-once-data-cleaned](.claude/docs/backend/python/python-test-strategy/spec.md) — Схема ставится один раз миграциями | script:test-lint | частичное |
| [python-test-strategy/test-auth-single-source](.claude/docs/backend/python/python-test-strategy/spec.md) — Тестовая авторизация собрана в одном месте | script:test-lint | частичное |
| [python-test-strategy/test-layers-separated](.claude/docs/backend/python/python-test-strategy/spec.md) — Слои тестов разделены по назначению | ci:test-layers | частичное |
| [python-test-strategy/test-name-states-scenario](.claude/docs/backend/python/python-test-strategy/spec.md) — Имя теста называет сценарий и правило | script:test-lint | частичное |
| [python-test-strategy/test-uses-shared-fixtures](.claude/docs/backend/python/python-test-strategy/spec.md) — Тест использует общие фикстуры и ходит по протоколу | ревью | нет |
| [python-test-strategy/tests-are-deterministic](.claude/docs/backend/python/python-test-strategy/spec.md) — Тесты детерминированы | script:test-lint | частичное |
| [resilience/async-calls-need-time-limit](.claude/docs/backend/resilience/spec.md) — Асинхронный исходящий вызов ограничен по времени отдельно | ревью | нет |
| [resilience/breaker-on-adapter-method](.claude/docs/backend/resilience/spec.md) — Размыкатель стоит на публичном методе адаптера | java: archunit:ResilienceAnnotationsOnAdaptersTest · python: ревью · go: ревью · node: ревью | частичное |
| [resilience/breaker-window-and-thresholds](.claude/docs/backend/resilience/spec.md) — Размыкатель считает отказы по окну вызовов | ревью | нет |
| [resilience/bulkhead-is-semaphore-based](.claude/docs/backend/resilience/spec.md) — Ограничение одновременных вызовов стоит отдельно от пула | ревью | нет |
| [resilience/cached-health-probe-per-system](.claude/docs/backend/resilience/spec.md) — У каждой внешней системы есть кешируемая проверка доступности | ревью | нет |
| [resilience/client-generated-from-contract](.claude/docs/backend/resilience/spec.md) — Клиент внешней системы генерируется из её описания | gradle:openapi-generate | частичное |
| [resilience/client-per-external-system](.claude/docs/backend/resilience/spec.md) — На каждую внешнюю систему — свой клиент и свои пулы | ревью | нет |
| [resilience/declarative-configuration](.claude/docs/backend/resilience/spec.md) — Настройки устойчивости декларативны | ревью | нет |
| [resilience/durable-retry-via-task-queue](.claude/docs/backend/resilience/spec.md) — Длительные и переживающие перезапуск повторы идут через очередь заданий | ревью | нет |
| [resilience/external-systems-affect-readiness](.claude/docs/backend/resilience/spec.md) — Доступность внешних систем влияет на готовность, не на живость | ревью | нет |
| [resilience/fallback-does-not-fake-success](.claude/docs/backend/resilience/spec.md) — Запасной путь не подменяет отказ успехом | ревью | нет |
| [resilience/inbound-rate-limiting-at-edge](.claude/docs/backend/resilience/spec.md) — Ограничение частоты входящих запросов живёт на границе периметра | ревью | нет |
| [resilience/instance-names-match-system](.claude/docs/backend/resilience/spec.md) — Имена обвязок совпадают с именем системы | script:config-check | частичное |
| [resilience/mapper-between-client-and-port](.claude/docs/backend/resilience/spec.md) — Между сгенерированным клиентом и портом стоит отображение | java: archunit:GeneratedDtoStaysInAdapterTest · python: ревью · go: ревью · node: ревью | частичное |
| [resilience/no-custom-breaker](.claude/docs/backend/resilience/spec.md) — Собственный размыкатель не пишется | ревью | нет |
| [resilience/no-long-synchronous-waits](.claude/docs/backend/resilience/spec.md) — Синхронный вызов не ждёт дольше разумного | ревью | нет |
| [resilience/no-protection-around-local-operations](.claude/docs/backend/resilience/spec.md) — Локальные операции не оборачиваются защитой от отказов | ревью | нет |
| [resilience/open-breaker-maps-to-domain-error](.claude/docs/backend/resilience/spec.md) — Размыкание превращается в понятную ошибку | ревью | нет |
| [resilience/outbound-calls-fully-protected](.claude/docs/backend/resilience/spec.md) — Исходящие вызовы к внешним системам защищены полным набором | java: archunit:OutAdaptersAreProtectedTest · python: ревью · go: ревью · node: ревью | частичное |
| [resilience/pool-sizes-are-balanced](.claude/docs/backend/resilience/spec.md) — Размеры пулов согласованы между собой и с пулом хранилища | ревью | нет |
| [resilience/resilience-state-is-observable](.claude/docs/backend/resilience/spec.md) — Состояние защиты наблюдаемо | ci:metrics-check | частичное |
| [resilience/respect-remaining-time-budget](.claude/docs/backend/resilience/spec.md) — Оставшееся время запроса учитывается | ревью | нет |
| [resilience/retry-only-when-safe](.claude/docs/backend/resilience/spec.md) — Повтор допустим только для безопасных операций | ревью | нет |
| [resilience/retry-with-backoff-and-limit](.claude/docs/backend/resilience/spec.md) — Повтор ограничен числом попыток и растущей паузой | ревью | нет |
| [resilience/timeout-hierarchy](.claude/docs/backend/resilience/spec.md) — Тайм-ауты образуют непротиворечивую иерархию | script:config-check | частичное |
| [rest-api/action-endpoints-shape](.claude/docs/backend/rest-api/spec.md) — Действие оформляется ресурсом и глаголом | script:openapi-lint | частичное |
| [rest-api/arrays-as-repeated-parameters](.claude/docs/backend/rest-api/spec.md) — Массивы передаются повтором параметра | script:openapi-lint | частичное |
| [rest-api/batch-operations-shape](.claude/docs/backend/rest-api/spec.md) — Пакетные операции имеют закреплённую форму | ревью | нет |
| [rest-api/client-tolerates-unknown-values](.claude/docs/backend/rest-api/spec.md) — Клиент терпим к неизвестным значениям | ревью | нет |
| [rest-api/collection-response-shape](.claude/docs/backend/rest-api/spec.md) — Коллекция отдаётся с метаданными пагинации | script:openapi-lint | частичное |
| [rest-api/collections-plural-singletons-singular](.claude/docs/backend/rest-api/spec.md) — Коллекция во множественном числе, единичный ресурс в единственном | ревью | нет |
| [rest-api/contract-is-predictable](.claude/docs/backend/rest-api/spec.md) — Контракт предсказуем и стабилен | ревью | нет |
| [rest-api/deprecation-with-sunset](.claude/docs/backend/rest-api/spec.md) — Устаревание объявляется с датой отключения | script:openapi-lint | частичное |
| [rest-api/error-body-follows-standard](.claude/docs/backend/rest-api/spec.md) — Тело ошибки следует стандартному формату | script:openapi-lint | частичное |
| [rest-api/error-codes-enumerated](.claude/docs/backend/rest-api/spec.md) — Код ошибки перечислен в контракте | script:openapi-lint | частичное |
| [rest-api/error-examples-in-operations](.claude/docs/backend/rest-api/spec.md) — Ошибки перечислены примерами в описании операций | ревью | нет |
| [rest-api/error-status-codes-limited](.claude/docs/backend/rest-api/spec.md) — Список кодов ошибок ограничен согласованным набором | script:openapi-lint | частичное |
| [rest-api/error-type-is-stable-category](.claude/docs/backend/rest-api/spec.md) — Категория ошибки стабильна и машиночитаема | ревью | нет |
| [rest-api/explicit-null-in-patch-means-delete](.claude/docs/backend/rest-api/spec.md) — Явное отсутствие значения в запросе изменения — команда удаления | ревью | нет |
| [rest-api/file-upload-and-download](.claude/docs/backend/rest-api/spec.md) — Файлы загружаются вложенным ресурсом составным запросом | script:openapi-lint | частичное |
| [rest-api/filters-ranges-and-search](.claude/docs/backend/rest-api/spec.md) — Фильтры, диапазоны и поиск имеют закреплённую форму | ревью | нет |
| [rest-api/headers-standard-and-prefixed](.claude/docs/backend/rest-api/spec.md) — Стандартные заголовки используются по назначению | ревью | нет |
| [rest-api/idempotency-key-header](.claude/docs/backend/rest-api/spec.md) — Повторно безопасные операции принимают ключ идемпотентности | test:integration | частичное |
| [rest-api/json-field-naming](.claude/docs/backend/rest-api/spec.md) — Поля тела именуются единообразно | script:openapi-lint | частичное |
| [rest-api/localization-via-accept-language](.claude/docs/backend/rest-api/spec.md) — Язык ответа выбирается заголовком с умолчанием | ревью | нет |
| [rest-api/long-running-via-polling](.claude/docs/backend/rest-api/spec.md) — Длительные операции работают через опрос задачи | script:openapi-lint | частичное |
| [rest-api/me-alias-only-when-ambiguous](.claude/docs/backend/rest-api/spec.md) — Псевдоним текущего пользователя вводится по признаку | ревью | нет |
| [rest-api/methods-match-semantics](.claude/docs/backend/rest-api/spec.md) — Методы соответствуют семантике | ревью | нет |
| [rest-api/nesting-max-two-levels](.claude/docs/backend/rest-api/spec.md) — Вложенность не глубже двух уровней | script:openapi-lint | частичное |
| [rest-api/new-version-only-for-breaking-change](.claude/docs/backend/rest-api/spec.md) — Новая версия — только при ломающем изменении | ревью | нет |
| [rest-api/no-hateoas-links-in-body](.claude/docs/backend/rest-api/spec.md) — Навигация описывается контрактом, а не телом ответа | ревью | нет |
| [rest-api/no-internals-in-error-body](.claude/docs/backend/rest-api/spec.md) — Внутренние подробности не попадают в тело ошибки | ревью | нет |
| [rest-api/no-nulls-in-successful-response](.claude/docs/backend/rest-api/spec.md) — Пустых и отсутствующих значений в успешном ответе не бывает | script:openapi-lint | частичное |
| [rest-api/operation-has-summary](.claude/docs/backend/rest-api/spec.md) — У операции есть короткое описание | script:openapi-lint | частичное |
| [rest-api/operation-id-and-tags](.claude/docs/backend/rest-api/spec.md) — Каждая операция имеет уникальный идентификатор и группу | script:openapi-lint | частичное |
| [rest-api/operational-endpoints-outside-api](.claude/docs/backend/rest-api/spec.md) — Служебные эндпоинты живут вне версионированного пространства | ревью | нет |
| [rest-api/pagination-forms](.claude/docs/backend/rest-api/spec.md) — Пагинация имеет две закреплённые формы | script:openapi-lint | частичное |
| [rest-api/path-lowercase-kebab-case](.claude/docs/backend/rest-api/spec.md) — Путь в нижнем регистре через дефис | script:openapi-lint | частичное |
| [rest-api/path-parameter-naming](.claude/docs/backend/rest-api/spec.md) — Имя параметра пути задаётся контекстом | ревью | нет |
| [rest-api/query-parameter-naming](.claude/docs/backend/rest-api/spec.md) — Параметры запроса именуются единообразно | script:openapi-lint | частичное |
| [rest-api/rate-limit-headers](.claude/docs/backend/rest-api/spec.md) — Ограничение частоты сообщает клиенту, когда повторить | ревью | нет |
| [rest-api/resource-name-is-domain-term](.claude/docs/backend/rest-api/spec.md) — Имя ресурса — доменный термин | ревью | нет |
| [rest-api/single-resource-is-flat](.claude/docs/backend/rest-api/spec.md) — Единичный ресурс отдаётся плоским объектом | ревью | нет |
| [rest-api/singleton-aliases](.claude/docs/backend/rest-api/spec.md) — Временные и логические псевдонимы — для единичной выборки | ревью | нет |
| [rest-api/sorting-parameter](.claude/docs/backend/rest-api/spec.md) — Сортировка задаётся одним параметром | ревью | нет |
| [rest-api/status-codes-and-bodies](.claude/docs/backend/rest-api/spec.md) — Коды и тела ответов соответствуют операции | test:integration | частичное |
| [rest-api/trace-context-header](.claude/docs/backend/rest-api/spec.md) — Сквозная трассировка идёт стандартным заголовком | ревью | нет |
| [rest-api/unique-path-parameter-names](.claude/docs/backend/rest-api/spec.md) — Имена параметров пути в описании уникальны по контексту | script:openapi-lint | частичное |
| [rest-api/validation-errors-list-violations](.claude/docs/backend/rest-api/spec.md) — Ошибки валидации отдаются перечнем нарушений по полям | test:integration | частичное |
| [rest-api/version-in-path](.claude/docs/backend/rest-api/spec.md) — Версия — целым числом в пути, за обязательным префиксом | script:openapi-lint | частичное |
| [scheduler/bounded-retries-then-parking](.claude/docs/backend/scheduler/spec.md) — Повторы ограничены и заканчиваются очередью разбора | ревью | нет |
| [scheduler/job-is-idempotent](.claude/docs/backend/scheduler/spec.md) — Задание идемпотентно | ревью | нет |
| [scheduler/job-is-observable](.claude/docs/backend/scheduler/spec.md) — Задание наблюдаемо | ci:metrics-check | частичное |
| [scheduler/job-parameters-are-typed-config](.claude/docs/backend/scheduler/spec.md) — Параметры задания задаются типизированной конфигурацией | test:integration | частичное |
| [scheduler/mechanism-matches-work](.claude/docs/backend/scheduler/spec.md) — Механизм выбирается по природе работы | ревью | нет |
| [scheduler/read-before-write-by-natural-key](.claude/docs/backend/scheduler/spec.md) — Обращение к внешней системе идёт с проверкой по естественному ключу | ревью | нет |
| [scheduler/single-source-of-tick](.claude/docs/backend/scheduler/spec.md) — Периодический тик не размножается по репликам | java: archunit:ScheduledMethodsAreGuardedTest · python: ревью · go: ревью · node: ревью | частичное |
| [scheduler/stuck-claims-are-recovered](.claude/docs/backend/scheduler/spec.md) — Зависшие захваты возвращаются в работу | ревью | нет |
| [scheduler/time-is-timezone-aware](.claude/docs/backend/scheduler/spec.md) — Время считается в универсальном формате с зоной | java: errorprone:JavaLocalDateTimeGetNano · python: ruff:DTZ005 · go: golangci-lint:gosec · node: ревью | частичное |
| [scheduler/transient-versus-business-errors](.claude/docs/backend/scheduler/spec.md) — Временные и бизнес-ошибки различаются | ревью | нет |
| [scheduler/work-unit-claimed-atomically](.claude/docs/backend/scheduler/spec.md) — Единица работы захватывается атомарно | ревью | нет |
| [security/authenticated-encryption-only](.claude/docs/backend/security/spec.md) — Симметричное шифрование в режиме с проверкой целостности | java: spotbugs:ECB_MODE · python: ruff:S305 · go: golangci-lint:gosec · node: ревью | частичное |
| [security/baseline-blocks-new-findings](.claude/docs/backend/security/spec.md) — Блокируются новые находки, а не накопленный долг | ci:security-scan | частичное |
| [security/checks-layered-by-feedback-speed](.claude/docs/backend/security/spec.md) — Проверки расслоены по скорости обратной связи | ci:security-scan | частичное |
| [security/code-security-scanner-required](.claude/docs/backend/security/spec.md) — Анализ кода на уязвимости обязателен | ci:security-scan | частичное |
| [security/compile-time-analysis-enabled](.claude/docs/backend/security/spec.md) — Анализ на этапе компиляции подключён | java: errorprone:default · python: ruff:default · go: golangci-lint:default · node: eslint:default | частичное |
| [security/csprng-for-security-values](.claude/docs/backend/security/spec.md) — Случайность для безопасности берётся из криптографического источника | java: spotbugs:PREDICTABLE_RANDOM · python: ruff:S311 · go: golangci-lint:gosec · node: eslint:no-restricted-properties | частичное |
| [security/dependency-updates-automated](.claude/docs/backend/security/spec.md) — Обновление зависимостей автоматизировано | ci:dependency-check | частичное |
| [security/every-finding-gets-a-decision](.claude/docs/backend/security/spec.md) — Находка не остаётся без решения | ревью | нет |
| [security/high-severity-breaks-build](.claude/docs/backend/security/spec.md) — Находка высокой важности ломает сборку | ci:security-scan | частичное |
| [security/image-pinned-and-nonroot](.claude/docs/backend/security/spec.md) — Базовый образ закреплён и запускается не от суперпользователя | trivy:config, script:manifest-check | частичное |
| [security/image-scanning-before-push](.claude/docs/backend/security/spec.md) — Образы сканируются до публикации | trivy:image, ci:security-scan | частичное |
| [security/leaked-secret-rotated-first](.claude/docs/backend/security/spec.md) — Утёкший секрет сначала меняется | ревью | нет |
| [security/modern-tls-only](.claude/docs/backend/security/spec.md) — Транспорт защищён современной версией протокола | ревью | нет |
| [security/no-hardcoded-keys](.claude/docs/backend/security/spec.md) — Ключи и векторы не хранятся в коде | gitleaks:default | частичное |
| [security/no-secret-values-in-config](.claude/docs/backend/security/spec.md) — Секретов в файлах настроек нет | gitleaks:default | частичное |
| [security/passwords-hashed-with-kdf](.claude/docs/backend/security/spec.md) — Пароли хешируются стойкой функцией | java: spotbugs:WEAK_MESSAGE_DIGEST_MD5, spotbugs:WEAK_MESSAGE_DIGEST_SHA1 · python: ruff:S324 · go: golangci-lint:gosec · node: eslint:no-restricted-imports | частичное |
| [security/secret-scanning-before-push](.claude/docs/backend/security/spec.md) — Поиск секретов стоит до отправки изменений | gitleaks:default, ci:secret-scan | частичное |
| [security/suppressions-are-files-with-deadline](.claude/docs/backend/security/spec.md) — Исключения оформляются файлами со сроком | ci:suppression-audit | частичное |
| [security/token-validated-by-library](.claude/docs/backend/security/spec.md) — Токен проверяется библиотекой | java: archunit:NoManualJwtParsingTest · python: ревью · go: ревью · node: ревью | частичное |
| [spring-bootstrap/event-serialization-sees-record-fields](.claude/docs/backend/java/spring-bootstrap/spec.md) — Сериализация событий видит поля записей | script:config-check, test:integration | частичное |
| [spring-bootstrap/external-dtos-are-handcrafted](.claude/docs/backend/java/spring-bootstrap/spec.md) — Объекты внешних контрактов остаются рукописными | ревью | нет |
| [spring-bootstrap/image-follows-security-requirements](.claude/docs/backend/java/spring-bootstrap/spec.md) — Образ и его развёртывание подчиняются требованиям безопасности | trivy:config, ci:security-scan | частичное |
| [spring-bootstrap/migration-contexts-explicit](.claude/docs/backend/java/spring-bootstrap/spec.md) — Контекст миграций задан явно | ревью | нет |
| [spring-bootstrap/migrations-layout-and-versioning](.claude/docs/backend/java/spring-bootstrap/spec.md) — Миграции лежат на уровне репозитория и версионируются | test:integration | частичное |
| [spring-bootstrap/no-double-encoding-of-payload](.claude/docs/backend/java/spring-bootstrap/spec.md) — Полезная нагрузка события не кодируется дважды | script:config-check | частичное |
| [spring-bootstrap/prefer-generated-types](.claude/docs/backend/java/spring-bootstrap/spec.md) — Используется сгенерированное, рукописные дубликаты удаляются | gradle:jooq-codegen | частичное |
| [spring-bootstrap/profile-activated-externally](.claude/docs/backend/java/spring-bootstrap/spec.md) — Профиль активируется снаружи, а не кодом | java: archunit:NoProgrammaticProfileActivationTest | частичное |
| [spring-bootstrap/roles-extracted-centrally](.claude/docs/backend/java/spring-bootstrap/spec.md) — Роли извлекаются из токена в одном месте | ревью | нет |
| [spring-bootstrap/secret-scan-and-nvd-key](.claude/docs/backend/java/spring-bootstrap/spec.md) — Поиск секретов стоит до отправки, ключ доступа к базе уязвимостей задан | gitleaks:default, ci:security-scan | частичное |
| [spring-bootstrap/security-checks-split-by-task](.claude/docs/backend/java/spring-bootstrap/spec.md) — Набор проверок безопасности подключён и разделён по задачам | ci:security-scan | частичное |
| [spring-bootstrap/security-config-per-profile](.claude/docs/backend/java/spring-bootstrap/spec.md) — Промышленная конфигурация безопасности отделена от локальной | test:integration | частичное |
| [spring-bootstrap/service-starts-without-broker](.claude/docs/backend/java/spring-bootstrap/spec.md) — Без брокера сервис стартует, обработчики выключены | test:integration | частичное |
| [spring-bootstrap/single-persistence-mechanism](.claude/docs/backend/java/spring-bootstrap/spec.md) — Слой хранения — только выбранный механизм | java: archunit:NoOtherPersistenceApisTest | частичное |
| [spring-bootstrap/starts-locally-with-one-command](.claude/docs/backend/java/spring-bootstrap/spec.md) — Сервис поднимается локально одной командой | ревью | нет |
| [spring-bootstrap/stub-publisher-is-overridable](.claude/docs/backend/java/spring-bootstrap/spec.md) — Заглушка публикации перебивается настоящей реализацией | test:integration | частичное |
| [spring-bootstrap/style-check-wired-to-build](.claude/docs/backend/java/spring-bootstrap/spec.md) — Проверка стиля подключена к общей задаче сборки | gradle:checkstyle, ci:lint | частичное |
| [spring-bootstrap/three-profiles-only](.claude/docs/backend/java/spring-bootstrap/spec.md) — Профилей ровно три, и они не дублируют конфигурацию | ревью | нет |
| [spring-bootstrap/thresholds-are-not-weakened](.claude/docs/backend/java/spring-bootstrap/spec.md) — Пороги не ослабляются, подавления оформляются файлами | ci:security-scan, ci:suppression-audit | частичное |
| [spring-bootstrap/time-source-is-single-and-swappable](.claude/docs/backend/java/spring-bootstrap/spec.md) — Источник времени один на сервис и подменяем в тестах | checkstyle:RegexpSingleline, test:integration | частичное |
| [sqlalchemy/bulk-operations](.claude/docs/backend/python/sqlalchemy/spec.md) — Массовые операции выполняются пакетно | ревью | нет |
| [sqlalchemy/eager-load-relationships](.claude/docs/backend/python/sqlalchemy/spec.md) — Связи загружаются заранее, ленивая загрузка запрещена | ревью | нет |
| [sqlalchemy/explicit-mapper](.claude/docs/backend/python/sqlalchemy/spec.md) — Маппинг явный и живёт рядом с репозиторием | ревью | нет |
| [sqlalchemy/generated-changelog-is-reviewed](.claude/docs/backend/python/sqlalchemy/spec.md) — Сгенерированный набор изменений вычитывается | ревью | нет |
| [sqlalchemy/modern-query-style](.claude/docs/backend/python/sqlalchemy/spec.md) — Запросы пишутся в современном стиле | ревью | нет |
| [sqlalchemy/no-business-logic-in-repository](.claude/docs/backend/python/sqlalchemy/spec.md) — Бизнес-логики в репозитории нет | ревью | нет |
| [sqlalchemy/no-orm-access-after-commit](.claude/docs/backend/python/sqlalchemy/spec.md) — Объект хранения не используется после фиксации | ревью | нет |
| [sqlalchemy/orm-models-are-anemic-and-in-adapter](.claude/docs/backend/python/sqlalchemy/spec.md) — Модели хранения живут в адаптере и анемичны | import-linter:layers | частичное |
| [sqlalchemy/pagination-and-counting](.claude/docs/backend/python/sqlalchemy/spec.md) — Постраничная выдача ограничена и считает общее число запросом | ревью | нет |
| [sqlalchemy/port-in-core-implementation-in-adapter](.claude/docs/backend/python/sqlalchemy/spec.md) — Порт объявлен в ядре, реализация — в адаптере | import-linter:core-independence | частичное |
| [sqlalchemy/precise-column-types](.claude/docs/backend/python/sqlalchemy/spec.md) — Типы колонок точные | ревью | нет |
| [sqlalchemy/raw-sql-is-parameterized](.claude/docs/backend/python/sqlalchemy/spec.md) — Строковые запросы параметризуются | ruff:S608 | частичное |
| [sqlalchemy/repository-integration-tested](.claude/docs/backend/python/sqlalchemy/spec.md) — Репозиторий покрыт интеграционным тестом против настоящей базы | ci:test-layers | частичное |
| [sqlalchemy/repository-speaks-domain-types](.claude/docs/backend/python/sqlalchemy/spec.md) — Репозиторий говорит доменными типами | ревью | нет |
| [sqlalchemy/schema-via-migrations](.claude/docs/backend/python/sqlalchemy/spec.md) — Схема управляется отдельным инструментом миграций | ревью | нет |
| [sqlalchemy/session-is-injected-per-request](.claude/docs/backend/python/sqlalchemy/spec.md) — Сессия внедряется, а не создаётся внутри | ревью | нет |
| [sqlalchemy/transaction-boundary-on-handler](.claude/docs/backend/python/sqlalchemy/spec.md) — Граница транзакции — на обработчике | ревью | нет |
| [sqlalchemy/transaction-errors-propagate-with-context](.claude/docs/backend/python/sqlalchemy/spec.md) — Ошибка в транзакции не глотается и уходит с контекстом | ruff:BLE001 | частичное |
| [sqlalchemy/view-repository-for-projections](.claude/docs/backend/python/sqlalchemy/spec.md) — Проекции чтения живут в отдельном репозитории | ревью | нет |
| [sqlc/bulk-insert-not-row-by-row](.claude/docs/backend/go/sqlc/spec.md) — Массовая вставка идёт пакетом, а не построчно | golangci-lint:gosec | частичное |
| [sqlc/codegen-config-sets-types](.claude/docs/backend/go/sqlc/spec.md) — Генерация настроена под точные типы | ci:codegen-check | частичное |
| [sqlc/constraint-violations-become-domain-errors](.claude/docs/backend/go/sqlc/spec.md) — Нарушения ограничений отображаются в доменные ошибки | ревью | нет |
| [sqlc/dependencies-via-constructor](.claude/docs/backend/go/sqlc/spec.md) — Зависимости внедряются конструктором | ревью | нет |
| [sqlc/dsn-from-environment](.claude/docs/backend/go/sqlc/spec.md) — Строка подключения приходит из окружения | gitleaks:default | частичное |
| [sqlc/errors-wrapped-not-logged](.claude/docs/backend/go/sqlc/spec.md) — Ошибки оборачиваются с контекстом и не журналируются в репозитории | golangci-lint:errorlint | частичное |
| [sqlc/explicit-mapping](.claude/docs/backend/go/sqlc/spec.md) — Маппинг явный и без бизнес-логики | ревью | нет |
| [sqlc/generated-code-not-edited](.claude/docs/backend/go/sqlc/spec.md) — Сгенерированный код не правится руками | ci:codegen-check | частичное |
| [sqlc/no-business-logic-in-repository](.claude/docs/backend/go/sqlc/spec.md) — Бизнес-логики в репозитории нет | ревью | нет |
| [sqlc/no-query-per-row](.claude/docs/backend/go/sqlc/spec.md) — Вложенные сущности читаются без запроса на строку | ревью | нет |
| [sqlc/no-rows-becomes-domain-error](.claude/docs/backend/go/sqlc/spec.md) — Отсутствие строки превращается в доменную ошибку | golangci-lint:nilnil | частичное |
| [sqlc/ping-on-start-close-on-stop](.claude/docs/backend/go/sqlc/spec.md) — Доступность базы проверяется при старте, пул закрывается при остановке | test:integration | частичное |
| [sqlc/pool-is-singleton-and-configured](.claude/docs/backend/go/sqlc/spec.md) — Пул создаётся один раз и настраивается явно | ревью | нет |
| [sqlc/port-in-core-implementation-in-adapter](.claude/docs/backend/go/sqlc/spec.md) — Порт в ядре, реализация в адаптере | golangci-lint:depguard | частичное |
| [sqlc/queries-live-in-files](.claude/docs/backend/go/sqlc/spec.md) — Запросы живут в файлах и аннотированы | golangci-lint:gosec | частичное |
| [sqlc/reads-are-read-only](.claude/docs/backend/go/sqlc/spec.md) — Чтение идёт без пишущей транзакции | ревью | нет |
| [sqlc/repository-speaks-domain-types](.claude/docs/backend/go/sqlc/spec.md) — Репозиторий говорит доменными типами | ревью | нет |
| [sqlc/repository-tested-against-real-database](.claude/docs/backend/go/sqlc/spec.md) — Репозиторий тестируется против настоящей базы | ci:test-layers | частичное |
| [sqlc/rollback-deferred-commit-checked](.claude/docs/backend/go/sqlc/spec.md) — Откат отложен, фиксация проверяется | golangci-lint:errcheck | частичное |
| [sqlc/schema-via-migration-tool](.claude/docs/backend/go/sqlc/spec.md) — Схема управляется инструментом миграций | ci:codegen-check | частичное |
| [sqlc/tests-are-isolated-and-cover-errors](.claude/docs/backend/go/sqlc/spec.md) — Тесты изолированы и покрывают ошибки | ревью | нет |
| [sqlc/timeout-comes-from-context](.claude/docs/backend/go/sqlc/spec.md) — Ограничение времени приходит сверху | ревью | нет |
| [sqlc/transaction-passed-explicitly](.claude/docs/backend/go/sqlc/spec.md) — Транзакция открывается на обработчике и передаётся явно | ревью | нет |
| [sqlc/view-repository-for-projections](.claude/docs/backend/go/sqlc/spec.md) — Проекции чтения обслуживаются отдельным репозиторием | ревью | нет |
| [streaming/authenticate-on-handshake](.claude/docs/backend/streaming/spec.md) — Аутентификация выполняется при установлении соединения | ревью | нет |
| [streaming/authorize-per-subscription](.claude/docs/backend/streaming/spec.md) — Права проверяются на подписку, а не только на вход | ревью | нет |
| [streaming/backpressure-is-bounded](.claude/docs/backend/streaming/spec.md) — Медленный получатель не копит очередь без границ | ревью | нет |
| [streaming/connection-limit-per-instance](.claude/docs/backend/streaming/spec.md) — Число одновременных соединений ограничено | ревью | нет |
| [streaming/connections-observable-without-payloads](.claude/docs/backend/streaming/spec.md) — Потоковые соединения наблюдаемы, содержимое не журналируется | ci:metrics-check | частичное |
| [streaming/disconnect-cancels-work](.claude/docs/backend/streaming/spec.md) — Разрыв клиента отменяет серверную работу | ревью | нет |
| [streaming/fanout-works-across-instances](.claude/docs/backend/streaming/spec.md) — Рассылка работает при нескольких экземплярах | ревью | нет |
| [streaming/heartbeat-and-idle-timeout](.claude/docs/backend/streaming/spec.md) — Соединение проверяется поддержанием активности | ревью | нет |
| [streaming/large-response-is-streamed](.claude/docs/backend/streaming/spec.md) — Большой ответ не собирается в памяти | ревью | нет |
| [streaming/long-lived-connections-recheck-rights](.claude/docs/backend/streaming/spec.md) — Долгоживущее соединение переучитывает права | ревью | нет |
| [streaming/mechanism-matches-exchange](.claude/docs/backend/streaming/spec.md) — Механизм выбирается по природе обмена | ревью | нет |
| [streaming/no-resources-held-for-connection-lifetime](.claude/docs/backend/streaming/spec.md) — Тяжёлые ресурсы не удерживаются на всё соединение | ревью | нет |
| [test-strategy/async-effects-made-synchronous](.claude/docs/backend/java/test-strategy/spec.md) — Отложенные эффекты переводятся в синхронные | ревью | нет |
| [test-strategy/base-classes-layered](.claude/docs/backend/java/test-strategy/spec.md) — Базовые классы разложены по уровням | ревью | нет |
| [test-strategy/builders-with-defaults](.claude/docs/backend/java/test-strategy/spec.md) — Объекты собираются построителями с разумными умолчаниями | ревью | нет |
| [test-strategy/container-connection-is-automatic](.claude/docs/backend/java/test-strategy/spec.md) — Подключение к контейнеру настраивается штатным механизмом | ревью | нет |
| [test-strategy/database-preparer-per-context](.claude/docs/backend/java/test-strategy/spec.md) — Подготовка базы идёт через отдельный компонент | ревью | нет |
| [test-strategy/expensive-setup-runs-once](.claude/docs/backend/java/test-strategy/spec.md) — Экземпляр теста живёт весь класс, дорогая подготовка выполняется один раз | ревью | нет |
| [test-strategy/external-calls-via-stub-server](.claude/docs/backend/java/test-strategy/spec.md) — Внешние вызовы проверяются стендом со стабами в самом тесте | ревью | нет |
| [test-strategy/integration-test-shape](.claude/docs/backend/java/test-strategy/spec.md) — Интеграционный тест поднимает контекст и настоящую базу | ревью | нет |
| [test-strategy/no-broker-or-cache-in-integration-tests](.claude/docs/backend/java/test-strategy/spec.md) — Брокер и кеш в интеграционных тестах не поднимаются | script:test-lint | частичное |
| [test-strategy/one-test-one-scenario](.claude/docs/backend/java/test-strategy/spec.md) — Один тест — один сценарий | ревью | нет |
| [test-strategy/schema-once-data-cleaned](.claude/docs/backend/java/test-strategy/spec.md) — Схема создаётся один раз, между тестами чистятся данные | script:test-lint | частичное |
| [test-strategy/test-auth-single-source](.claude/docs/backend/java/test-strategy/spec.md) — Тестовая авторизация собрана в одном месте | script:test-lint | частичное |
| [test-strategy/test-layers-separated](.claude/docs/backend/java/test-strategy/spec.md) — Слои тестов разделены по назначению | ci:test-layers | частичное |
| [test-strategy/test-name-states-scenario](.claude/docs/backend/java/test-strategy/spec.md) — Имя теста называет сценарий и правило | script:test-lint | частичное |
| [test-strategy/test-uses-http-client](.claude/docs/backend/java/test-strategy/spec.md) — Тест наследует доменный базовый класс и ходит по протоколу | ревью | нет |
| [test-strategy/tests-are-synchronous-and-deterministic](.claude/docs/backend/java/test-strategy/spec.md) — Тесты синхронные и детерминированные | script:test-lint | частичное |
| [typeorm/bind-parameters-only](.claude/docs/backend/node/typeorm/spec.md) — Параметры запросов связываются, а не подставляются | eslint:no-unsafe-argument | частичное |
| [typeorm/entities-are-anemic-data-mapper](.claude/docs/backend/node/typeorm/spec.md) — Сущности хранения анемичны и живут в адаптере | dependency-cruiser:no-core-to-adapter | частичное |
| [typeorm/entity-manager-is-injected](.claude/docs/backend/node/typeorm/spec.md) — Менеджер сущностей внедряется | ревью | нет |
| [typeorm/explicit-mapper](.claude/docs/backend/node/typeorm/spec.md) — Маппинг явный и живёт рядом с репозиторием | ревью | нет |
| [typeorm/no-business-logic-in-repository](.claude/docs/backend/node/typeorm/spec.md) — Бизнес-логики в репозитории нет | ревью | нет |
| [typeorm/pagination-and-counting](.claude/docs/backend/node/typeorm/spec.md) — Постраничная выдача ограничена, число считается запросом | ревью | нет |
| [typeorm/port-in-core-implementation-in-adapter](.claude/docs/backend/node/typeorm/spec.md) — Порт в ядре, реализация в адаптере | dependency-cruiser:no-core-to-adapter | частичное |
| [typeorm/precise-column-types](.claude/docs/backend/node/typeorm/spec.md) — Типы колонок точные | ревью | нет |
| [typeorm/relations-are-explicit](.claude/docs/backend/node/typeorm/spec.md) — Связи в запросах перечисляются явно | ревью | нет |
| [typeorm/repository-integration-tested](.claude/docs/backend/node/typeorm/spec.md) — Репозиторий покрыт интеграционным тестом | ci:test-layers | частичное |
| [typeorm/repository-speaks-domain-types](.claude/docs/backend/node/typeorm/spec.md) — Репозиторий говорит доменными типами | ревью | нет |
| [typeorm/schema-via-reviewed-migrations](.claude/docs/backend/node/typeorm/spec.md) — Схема управляется миграциями с ручной вычиткой | script:config-check | частичное |
| [typeorm/transaction-on-handler](.claude/docs/backend/node/typeorm/spec.md) — Транзакция открывается на обработчике и доходит до репозитория | ревью | нет |
| [typeorm/update-full-aggregate-or-explicit](.claude/docs/backend/node/typeorm/spec.md) — Обновление идёт полным агрегатом или явным точечным запросом | ревью | нет |
| [typeorm/view-repository-for-projections](.claude/docs/backend/node/typeorm/spec.md) — Проекции чтения обслуживаются отдельным репозиторием | ревью | нет |
| [usecase-pattern/command-returns-minimum](.claude/docs/backend/usecase-pattern/spec.md) — Команда возвращает минимум | ревью | нет |
| [usecase-pattern/command-versus-query](.claude/docs/backend/usecase-pattern/spec.md) — Команда и запрос различаются в типе и в имени | java: archunit:CommandsAndQueriesAreNamedTest · python: ревью · go: ревью · node: ревью | частичное |
| [usecase-pattern/controller-maps-and-dispatches](.claude/docs/backend/usecase-pattern/spec.md) — Контроллер только отображает и диспатчит | java: archunit:ControllersHaveNoBusinessLogicTest · python: ревью · go: ревью · node: ревью | частичное |
| [usecase-pattern/entry-calls-dispatcher](.claude/docs/backend/usecase-pattern/spec.md) — Вход зовёт диспетчер, а не обработчик | java: archunit:ControllersUseDispatcherTest · python: import-linter:in-adapter · go: ревью · node: ревью | частичное |
| [usecase-pattern/explicit-mapper-between-layers](.claude/docs/backend/usecase-pattern/spec.md) — Отображение между слоями — выделенным маппером | ревью | нет |
| [usecase-pattern/explicit-result-type](.claude/docs/backend/usecase-pattern/spec.md) — Результат объявлен типом, пустой результат — явно | java: archunit:UseCasesDeclareResultTest · python: ревью · go: ревью · node: ревью | частичное |
| [usecase-pattern/handler-is-stateless](.claude/docs/backend/usecase-pattern/spec.md) — Обработчик без состояния, зависимости — через конструктор | java: archunit:HandlersAreStatelessTest · python: ревью · go: ревью · node: ревью | частичное |
| [usecase-pattern/handler-registered-in-container](.claude/docs/backend/usecase-pattern/spec.md) — Обработчик зарегистрирован в контейнере | test:integration | частичное |
| [usecase-pattern/handlers-do-not-call-handlers](.claude/docs/backend/usecase-pattern/spec.md) — Операции запускает только входящий адаптер | java: archunit:HandlersDoNotDependOnHandlersTest · python: import-linter:handlers · go: ревью · node: ревью | частичное |
| [usecase-pattern/infrastructure-errors-become-domain](.claude/docs/backend/usecase-pattern/spec.md) — Инфраструктурные ошибки не выходят из обработчика | ревью | нет |
| [usecase-pattern/layer-models-do-not-leak](.claude/docs/backend/usecase-pattern/spec.md) — На входе и выходе операции — объекты слоя границы | java: archunit:NoPersistenceTypesInApiTest · python: import-linter:layers · go: ревью · node: dependency-cruiser:no-layer-violation | частичное |
| [usecase-pattern/no-cyclic-mappers](.claude/docs/backend/usecase-pattern/spec.md) — Мапперы не образуют циклов | java: archunit:NoCyclicDependenciesTest · python: import-linter:layers · go: golangci-lint:depguard · node: dependency-cruiser:no-circular | частичное |
| [usecase-pattern/no-transport-objects-in-usecase](.claude/docs/backend/usecase-pattern/spec.md) — Транспортные объекты не попадают в операцию | java: archunit:UseCasesHaveNoTransportTypesTest · python: ревью · go: ревью · node: ревью | частичное |
| [usecase-pattern/one-handler-one-usecase](.claude/docs/backend/usecase-pattern/spec.md) — Обработчик объявляет свою операцию и обрабатывает только её | java: archunit:HandlersDeclareUseCaseTest · python: ревью · go: ревью · node: ревью | частичное |
| [usecase-pattern/one-usecase-many-inbound-adapters](.claude/docs/backend/usecase-pattern/spec.md) — Одна операция вызывается из разных входов | ревью | нет |
| [usecase-pattern/one-usecase-one-operation](.claude/docs/backend/usecase-pattern/spec.md) — Одна операция — один объект с говорящим именем | ревью | нет |
| [usecase-pattern/one-usecase-one-transaction](.claude/docs/backend/usecase-pattern/spec.md) — Одна операция — одна транзакция | ревью | нет |
| [usecase-pattern/publish-events-after-save](.claude/docs/backend/usecase-pattern/spec.md) — Доменные события публикуются после сохранения | ревью | нет |
| [usecase-pattern/query-does-not-mutate](.claude/docs/backend/usecase-pattern/spec.md) — Запрос не меняет состояние | java: archunit:QueryHandlersDoNotWriteTest · python: ревью · go: ревью · node: ревью | частичное |
| [usecase-pattern/reads-via-read-model](.claude/docs/backend/usecase-pattern/spec.md) — Чтение идёт через модель чтения, запись — через агрегат | ревью | нет |
| [usecase-pattern/single-dispatcher](.claude/docs/backend/usecase-pattern/spec.md) — Диспетчер один на приложение | ревью | нет |
| [usecase-pattern/step-for-reuse-only](.claude/docs/backend/usecase-pattern/spec.md) — Шаг вводится ради повторного использования | ревью | нет |
| [usecase-pattern/steps-flat-and-stateless](.claude/docs/backend/usecase-pattern/spec.md) — Шаги не вкладываются и не хранят состояние | java: archunit:StepsAreStatelessTest · python: ревью · go: ревью · node: ревью | частичное |
| [usecase-pattern/transaction-boundary-on-handler](.claude/docs/backend/usecase-pattern/spec.md) — Граница транзакции — на обработчике | ревью | нет |
| [usecase-pattern/usecase-implements-marker](.claude/docs/backend/usecase-pattern/spec.md) — Операция объявляет общий контракт с типом результата | java: archunit:UseCasesImplementMarkerTest · python: ревью · go: ревью · node: ревью | частичное |
| [usecase-pattern/usecase-is-immutable-carrier](.claude/docs/backend/usecase-pattern/spec.md) — Объект операции неизменяем и не содержит логики | java: archunit:UseCasesAreImmutableTest · python: ревью · go: ревью · node: ревью | частичное |
| [validation/config-validated-at-startup](.claude/docs/backend/validation/spec.md) — Конфигурация проверяется при старте | test:integration | частичное |
| [validation/constraint-is-stateless](.claude/docs/backend/validation/spec.md) — Проверка не имеет состояния | ревью | нет |
| [validation/controller-implements-generated-contract](.claude/docs/backend/validation/spec.md) — Контроллер реализует сгенерированный контракт | java: archunit:ControllersImplementGeneratedApiTest · python: ревью · go: ревью · node: ревью | частичное |
| [validation/cross-field-rules-on-object](.claude/docs/backend/validation/spec.md) — Правило по нескольким полям объявляется на объекте | ревью | нет |
| [validation/custom-constraint-is-reusable](.claude/docs/backend/validation/spec.md) — Собственная проверка — переиспользуемая единица в общем модуле | ревью | нет |
| [validation/custom-constraint-named-by-domain](.claude/docs/backend/validation/spec.md) — Собственная проверка названа доменным термином | ревью | нет |
| [validation/custom-constraint-null-safe](.claude/docs/backend/validation/spec.md) — Собственная проверка не падает на отсутствующем значении | test:unit | частичное |
| [validation/domain-invariants-in-aggregate](.claude/docs/backend/validation/spec.md) — Доменные инварианты живут в агрегате | java: archunit:NoValidationAnnotationsInDomainTest · python: import-linter:core-independence · go: ревью · node: ревью | частичное |
| [validation/generated-artifacts-immutable](.claude/docs/backend/validation/spec.md) — Сгенерированные артефакты не правятся руками | java: gradle:openapi-generate · python: ревью · go: ревью · node: ревью | частичное |
| [validation/generation-carries-constraints](.claude/docs/backend/validation/spec.md) — Генерация переносит ограничения контракта в объекты | java: gradle:openapi-generate · python: ревью · go: ревью · node: ревью | частичное |
| [validation/input-validated-at-edge](.claude/docs/backend/validation/spec.md) — Контракт входа проверяется на границе декларативно | java: archunit:ControllersValidateInputTest · python: ревью · go: ревью · node: ревью | частичное |
| [validation/message-in-user-language](.claude/docs/backend/validation/spec.md) — Сообщение написано на языке пользователя | ревью | нет |
| [validation/nested-validated-recursively](.claude/docs/backend/validation/spec.md) — Вложенные структуры проверяются рекурсивно | java: archunit:NestedFieldsAreValidatedTest · python: ревью · go: ревью · node: ревью | частичное |
| [validation/no-duplicated-messages](.claude/docs/backend/validation/spec.md) — Одинаковое сообщение не повторяется на каждом поле | ревью | нет |
| [validation/no-false-or-composite-constraints](.claude/docs/backend/validation/spec.md) — Ложных и составных проверок не бывает | ревью | нет |
| [validation/no-revalidation-after-edge](.claude/docs/backend/validation/spec.md) — Повторная проверка после границы не делается | ревью | нет |
| [validation/replica-is-stored-as-received](.claude/docs/backend/validation/spec.md) — Копия чужих данных сохраняется как пришла | ревью | нет |
| [validation/scenario-groups-are-narrow](.claude/docs/backend/validation/spec.md) — Сценарные наборы правил — только для одного объекта | ревью | нет |
| [validation/scenario-marker-documented](.claude/docs/backend/validation/spec.md) — Маркер сценария пустой и документированный | ревью | нет |
| [validation/single-source-of-truth](.claude/docs/backend/validation/spec.md) — Источник правды по входной валидации один | java: gradle:openapi-generate · python: ревью · go: ревью · node: ревью | частичное |
| [validation/standard-constraints-preferred](.claude/docs/backend/validation/spec.md) — Стандартные проверки берутся готовыми | ревью | нет |

<!-- END:ucp-requirements -->
