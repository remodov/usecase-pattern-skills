# Spring Boot Bootstrap — индекс правил

> **Что это.** Сжатый индекс правил `spring-bootstrap-style-guide.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с примерами конфигов, gradle-сниппетами и обоснованием — `spring-bootstrap-style-guide.md`**; открывай её
> точечно по нужному разделу, когда индекса не хватает.
> Коды: `BS-<N>` / `BS-LINT-<N>` / `BS-SEC-<N>` — обязательно, `BS-*-X<N>` — антипаттерн (запрещено).

Базовый принцип (`BS-1`): **сервис запускается локально одной командой, без живых внешних зависимостей** (кроме Postgres из docker-compose). Если для `bootRun` нужен живой Keycloak / Kafka / Catalog — это баг настройки.

## 1. Профили
**MUST:**
- **BS-2.** Ровно три состояния конфигурации: без профиля (production/staging), `local` (`bootRun`: Postgres docker-compose, security `permitAll`, Kafka off, dev-URL), `integration-test` (`@SpringBootTest`: Postgres, WireMock-стабы, schedulers off, security `permitAll`). Каждый профиль — отдельный `application-<profile>.yml`. Без `dev`/`staging`/`prod-readonly` без бизнес-обоснования.
- **BS-3.** Profile никогда не активируется кодом — только `--spring.profiles.active=` / `SPRING_PROFILES_ACTIVE`. Код с `@Profile("local")` не должен попасть в production случайно.
- **BS-4.** `application.yml` — production-defaults (реальная конфигурация через ENV); `application-local.yml` / `application-integration-test.yml` — только overrides, не дублирование всей конфигурации.

## 2. Service-beans (DateTimeService / UuidGenerator / Clock)
**MUST:**
- **BS-5.** Все источники недетерминизма (время, UUID, random, `InetAddress`) обёрнуты в интерфейс в `core` (требование `TS-7`); тесты подменяют через `@MockitoBean`.
- **BS-6.** Production-реализации этих интерфейсов обязательно регистрируются как beans в `bootstrap` (`ServiceBeansConfig`), каждая под `@ConditionalOnMissingBean`. Без этого context refresh падает `UnsatisfiedDependencyException` на старте — проверять первым делом, когда сервис не стартует.

## 3. Security
**MUST:**
- **BS-7.** Production `SecurityConfig` — OAuth2 Resource Server с JWT (`oauth2ResourceServer().jwt()`), JWK-set URL из IdP. Без живого IdP сервис не обрабатывает запросы, но **стартует** (JWK-fetch ленивый) — чтобы health-check видел корректный контекст.
- **BS-8.** Production-конфиг — `@Profile("!integration-test & !local")`; на `local`/`integration-test` — отдельные `SecurityFilterChain` с `permitAll()`. Локальный конфиг **не отключает** `@EnableMethodSecurity` — `@PreAuthorize` остаётся.
- **BS-9.** Извлечение ролей из JWT — централизованно через `JwtAuthenticationConverter`-bean (Keycloak: `realm_access.roles` с префиксом `ROLE_`), не размазано по контроллерам.

## 4. Liquibase
**MUST:**
- **BS-10.** Миграции в `migrations/db/` на уровне репо (не в `src/main/resources` модуля), чтобы гонять как Liquibase CLI; подключаются через `sourceSets.main.resources.srcDir(rootProject.file("migrations"))`.
- **BS-11.** `spring.liquibase.contexts` всегда явно задан (обычно `production`) — для context-фильтров dev-only / production-only ChangeSet'ов.
- **BS-12.** ChangeSet версионируются по релизам (`v-1.0/`, `v-1.1/`). Никогда не модифицировать уже применённый ChangeSet — только добавлять новый (иначе рассинхрон checksum в `databasechangelog`).

## 5. Kafka
**MUST:**
- **BS-13.** Без живой Kafka сервис **стартует**, но `@KafkaListener` — нет (`spring.kafka.listener.auto-startup: false` в local/integration-test). В тестах консьюмер вызывается напрямую `consumer.onMessage(record)`, без embedded broker.
- **BS-14.** Key/value serializers для outbox-events — `StringSerializer`/`StringDeserializer`; payload уже JSON-строка (формируется `EventPayloadSerializer`), повторное JSON-кодирование добавит кавычки.
- **BS-15.** `@ConditionalOnMissingBean(name = "kafkaExternalEventPublisher")` на logging-stub `ExternalEventPublisher` — чтобы Kafka-publisher из `adapter-out-kafka` автоматически перебивал стаб.

## 6. Jackson и события
**MUST:**
- **BS-16.** `DomainEvent` используют record-style accessors (`customerId()`), которых default Jackson visibility не видит — обязателен `JacksonConfig` с `Visibility.ANY` для полей. Иначе Outbox-relay публикует пустые события (тесты на `event_type`-колонку это не ловят — проверять содержимое payload).

## 7. Persistence — jOOQ и только generated классы
**MUST:**
- **BS-17.** Persistence-слой во всех сервисах — только jOOQ, независимо от уровня зрелости. Никаких JdbcTemplate / JPA / Hibernate / MyBatis / Spring Data JDBC. Перебивает любые «для CRUD проще». Подключаем `spring-boot-starter-jooq` + `nu.studer.jooq`.
- **BS-18.** Используем максимум сгенерённого: generated POJO / enum / table-references. Handcrafted POJO/entity, дублирующие строку БД, удаляются. VARCHAR с фиксированным набором → Postgres ENUM через Liquibase (jOOQ codegen создаст Java enum).
- **BS-20.** DTO внешних API остаются handcrafted — `BS-17/18` касаются только классов, дублирующих строку БД. JSON-DTO REST-клиентов, Kafka-payload, OpenAPI request/response — вне зоны действия.

**MUST NOT:**
- **BS-19.** Модификация generated-классов. Методы на enum (`isTerminal()`) — inline на use-sites или в отдельный utility-класс; добавленные в generated-enum пропадут при перегенерации.

## 7a. Lint enforcement (Checkstyle)
**MUST:**
- **BS-LINT-1.** Checkstyle обязателен в build (`JS-CS-1`); конфиг `config/checkstyle/checkstyle.xml` коммитится, шаблон — через `ucp-bootstrap-design`.
- **BS-LINT-2.** Привязан к default-таргету `check` (`JS-CS-4`), не к `checkSecurity` — `./gradlew check` падает на нейминге/импортах сразу.
- **BS-LINT-3.** `config/checkstyle/checkstyle-suppressions.xml` коммитится даже пустым (как `BS-SEC-4`).

**MUST NOT:**
- **BS-LINT-X1.** Checkstyle с `ignoreFailures = true` или `maxWarnings > 0` — нарушает `JS-CS-3`, превращает lint в дашборд-без-действий.

## 8. Security/SAST enforcement
> Полный набор инструментов и правил — в `security-style-guide.md` (`R-SEC-*`). Здесь — enforcement-уровень для `build.gradle` и CI.

**MUST:**
- **BS-SEC-1.** Mandatory plugin set: Error Prone (`R-SEC-SAST-1`), SpotBugs+FindSecBugs (`R-SEC-SAST-2`), OWASP Dependency-Check (`R-SEC-DEP-1`). Gitleaks и Trivy — на уровне CI, не gradle-плагины.
- **BS-SEC-2.** Разделение `check` / `checkSecurity` / `checkSupplyChain` (`R-SEC-2`): `check` лёгкий (тесты + Error Prone), `checkSecurity` (SpotBugs), `checkSupplyChain` (dependencyCheck — только release/nightly, не на PR и не локально).
- **BS-SEC-3.** `failOnError` / `failBuildOnCVSS=7.0` обязаны быть включены, не ослабляются без RFC-комментария.
- **BS-SEC-4.** Suppression-файлы (`spotbugs-exclude.xml`, `dependency-check-suppressions.xml`) коммитятся даже пустыми — чтобы ревьюер видел контекст первого suppression.
- **BS-SEC-5.** CI security-job параллелен тестам, не последовательный (`R-SEC-2`).
- **BS-SEC-5a.** `checkSupplyChain` — отдельный workflow (`security-supply-chain.yml`): push в main, nightly cron, release; не на `pull_request`. Падение создаёт issue с label `security`, не блокирует merge feature-веток.
- **BS-SEC-5b.** Pre-commit hook с Gitleaks обязателен (`R-SEC-2`), сканирует diff; CI gitleaks-step страховочный.
- **BS-SEC-6.** `NVD_API_KEY` обязателен в CI secrets — иначе `dependencyCheckAnalyze` упирается в rate-limit NVD.
- **BS-SEC-7.** Dockerfile и k8s подчиняются `R-SEC-IMG-*`: non-root (`USER 1000:1000`), base image с digest-pin (не `:latest`), `HEALTHCHECK`; Trivy в CI `severity: HIGH,CRITICAL exit-code: 1`.
- **BS-SEC-8.** `.gitleaks.toml` + pre-commit hook — главный; CI-step страховочный.

**MUST NOT:**
- **BS-SEC-X1.** `spotbugs { ignoreFailures = true }` / «отключим ради зелёной сборки» — нарушает `R-SEC-1`. Поломанные findings — конкретные suppressions с обоснованием, не глобальное отключение.
- **BS-SEC-X2.** Подавление Dependency-Check через `failBuildOnCVSS = 11` (фейк-thresholds) — нужен обход CVE → suppression с `until=` и `<notes>`.
- **BS-SEC-X3.** Security-job с `continue-on-error: true` — все findings игнорируются. Flaky-стадию — чинить, не маскировать.
