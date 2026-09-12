# Spring Boot Bootstrap — реализация

Правила боевой настройки Spring Boot-сервиса по Use Case Pattern: профили, бины, Security, Liquibase, Kafka. Каждое правило имеет код `BS-N` — скилл `ucp-bootstrap-design` цитирует их в ревью.

Базовый принцип (`spring-bootstrap/starts-locally-with-one-command`): **сервис должен запускаться локально одной командой, без живых внешних зависимостей** (кроме Postgres из docker-compose). Если для `bootRun` нужен живой Keycloak / Kafka / Catalog — это баг настройки, а не нормальное состояние dev-окружения.

---

## 1. Профили

`spring-bootstrap/three-profiles-only` На сервис заводятся ровно три состояния конфигурации:

| Профиль | Когда применять | Что включает |
|---|---|---|
| (без профиля) | Production / staging | Реальные внешние сервисы, IdP, Kafka, секьюрити |
| `local` | `./gradlew bootRun` для ручной разработки | Postgres из docker-compose, security `permitAll`, Kafka listeners выключены, Catalog/Payment URL-ы на dev-порты |
| `integration-test` | Только в `@SpringBootTest` | Postgres из docker-compose, WireMock-стабы для Catalog/Payment на фиксированных портах, schedulers заглушены, security `permitAll` |

Никаких `dev`, `staging`, `prod-readonly` сверху без явного бизнес-обоснования. Каждый профиль = отдельный `application-<profile>.yml` рядом с `application.yml`.

`spring-bootstrap/profile-activated-externally` Profile **никогда не активируется кодом**. Активация — только через `--spring.profiles.active=local` либо `SPRING_PROFILES_ACTIVE`. Это значит: код, имеющий `@Profile("local")`, не должен включаться в production-сборку случайно.

`spring-bootstrap/three-profiles-only` `application.yml` — production-defaults (`localhost`/`9001`/`localhost:8081`-плейсхолдеры допустимы, но *настоящая* конфигурация прокидывается через ENV в Helm/деплоймент). `application-local.yml` и `application-integration-test.yml` — **только overrides** относительно базы. Не дублируйте всю конфигурацию.

---

## 2. Источник времени: два варианта, один на сервис

`spring-bootstrap/time-source-is-single-and-swappable` В сервисе ровно **один** источник текущего времени, подменяемый в тестах; прямые `OffsetDateTime.now()` / `Instant.now()` / `LocalDateTime.now()` в промышленном коде запрещены (`checkstyle:RegexpSingleline` по `core` и адаптерам). Оба варианта ниже законны — выбирается один на сервис, и скиллы следуют выбору проекта.

**Вариант A — статический `Clock` (эталон partnerapi-hub).** Время нужно агрегатам, событиям и фабрикам — местам без DI, поэтому источник статический, а подмена — сменой `Clock`:

```java
@UtilityClass
public class DateTimeUtil {

    private static volatile Clock clock = Clock.systemUTC();

    public OffsetDateTime currentDateTime() {
        return OffsetDateTime.now(clock).truncatedTo(ChronoUnit.MICROS);
    }

    public void setClock(Clock newClock) {
        clock = newClock;
    }

    public void resetClock() {
        clock = Clock.systemUTC();
    }
}
```

Усечение до микросекунд обязательно: это точность `timestamptz`, а JDK на Linux даёт наносекунды — без усечения объект в памяти и он же, прочитанный из БД, не равны. В тестах — `fixClock(moment)` → `setClock(Clock.fixed(...))` и `@AfterEach resetClock()` в базовом классе; параллельный запуск тест-классов с таким источником недопустим. Идентификаторы в этом варианте чеканят фабрики и события через `UUID.randomUUID()`; тесты их не фиксируют, а читают обратно.

**Вариант B — бины над `Clock`.** Интерфейсы в core пусты: `DateTimeService.now() : Instant`, `UuidGenerator.generate() : UUID`; время в агрегат передаётся параметром из handler'а. Production-реализации регистрируются в `bootstrap` (`ServiceBeansConfig`), каждая под `@ConditionalOnMissingBean`, чтобы тесты подменяли их через `@MockitoBean`. Реализация времени тоже усекает до микросекунд:

```java
@Configuration
public class ServiceBeansConfig {

    @Bean @ConditionalOnMissingBean
    public Clock systemClock() {
        return Clock.systemUTC();
    }

    @Bean @ConditionalOnMissingBean
    public DateTimeService dateTimeService(Clock clock) {
        return () -> Instant.now(clock).truncatedTo(ChronoUnit.MICROS);
    }

    @Bean @ConditionalOnMissingBean
    public UuidGenerator uuidGenerator() {
        return UUID::randomUUID;
    }
}
```

Типичная ошибка варианта B: интерфейс есть, тестовый `@MockitoBean` есть, в production контекста бина нет → context refresh падает на handler'е, который её инжектит. **Проверяй это первым делом, когда сервис не стартует.** Типичная ошибка варианта A: тест зафиксировал часы и не сбросил — следующий класс живёт в прошлом; `resetClock()` — в `@AfterEach` базового класса, не в каждом тесте.

---

## 3. Security

`spring-bootstrap/security-config-per-profile` Production `SecurityConfig` — **OAuth2 Resource Server с JWT** через `oauth2ResourceServer().jwt()`. JWK-set URL берётся из IdP (`spring.security.oauth2.resourceserver.jwt.jwk-set-uri`). Без живого IdP сервис не должен **обрабатывать запросы** в production — но **должен стартовать**, чтобы health-check показывал, что Spring контекст в порядке (JWK-fetch ленивый).

`spring-bootstrap/security-config-per-profile` Production-конфиг помечается `@Profile("!integration-test & !local")`. На профилях `integration-test` и `local` — отдельные `SecurityFilterChain`-bean'ы с `permitAll()`, чтобы можно было вызывать API из Postman/curl без поднятия Keycloak. Локальная конфигурация **не отключает `@EnableMethodSecurity`** — `@PreAuthorize` остаётся; для проверки роле-зависимых сценариев в local используй `with(jwt())` в тестах или живой IdP.

`spring-bootstrap/roles-extracted-centrally` Извлечение ролей из JWT — централизованно. Для Keycloak — из `realm_access.roles` с префиксом `ROLE_`. Реализуется как `JwtAuthenticationConverter`-bean, не размазывается по контроллерам.

---

## 4. Liquibase

`spring-bootstrap/migrations-layout-and-versioning` Миграции живут на уровне репо в `migrations/db/` (не в `src/main/resources` модуля), так чтобы их можно было прогнать как Liquibase CLI без зависимости от Java-сборки. В `bootstrap`/`adapter-out-postgres` `build.gradle.kts` указывается `sourceSets.main.resources.srcDir(rootProject.file("migrations"))` — Liquibase по умолчанию ищет `classpath:db/changelog-master.yaml`.

`spring-bootstrap/migration-contexts-explicit` `spring.liquibase.contexts` всегда явно задан (обычно `production`). Это даёт возможность использовать Liquibase `context`-фильтры для разделения dev-only / production-only ChangeSet'ов.

`spring-bootstrap/migrations-layout-and-versioning` ChangeSet-файлы версионируются по релизам: `migrations/db/changelog/v-1.0/initial-schema.yaml`, `v-1.1/...`, и т.д. **Никогда не модифицируй уже применённый ChangeSet** — добавляй новый. Правка приведёт к рассинхрону checksum в `databasechangelog`.

---

## 5. Kafka

`spring-bootstrap/service-starts-without-broker` Без живой Kafka сервис должен **стартовать**, но `@KafkaListener`-консьюмеры — нет. Это решается одной строкой в `application-local.yml` и `application-integration-test.yml`:

```yaml
spring:
  kafka:
    listener:
      auto-startup: false
```

В тестах при необходимости консьюмер вызывается напрямую через `consumer.onMessage(record)` — не нужен embedded broker.

`spring-bootstrap/no-double-encoding-of-payload` Producer/consumer key/value serializers — **`StringSerializer`/`StringDeserializer`** для outbox-events. Полезная нагрузка уже JSON-строка, повторное JSON-кодирование добавит лишние кавычки. JSON формируется в core через `EventPayloadSerializer` поверх Jackson.

`spring-bootstrap/stub-publisher-is-overridable` `@ConditionalOnMissingBean(name = "kafkaExternalEventPublisher")` на logging-stub-имплементации `ExternalEventPublisher` — чтобы при подключении `adapter-out-kafka` Kafka-publisher автоматически перебивал стаб.

---

## 6. Jackson и события

`spring-bootstrap/event-serialization-sees-record-fields` `DomainEvent`-классы используют **record-style accessors** (`customerId()` вместо `getCustomerId()`). Default Jackson visibility их **не видит** — outbox payload получается с одними base-class полями. В `bootstrap` обязателен `JacksonConfig` с `Visibility.ANY` для полей:

```java
@Bean
public Jackson2ObjectMapperBuilderCustomizer objectMapperCustomizer() {
    return builder -> builder.postConfigurer((ObjectMapper m) ->
        m.setVisibility(m.getSerializationConfig().getDefaultVisibilityChecker()
            .withFieldVisibility(JsonAutoDetect.Visibility.ANY)));
}
```

Без этого Outbox-relay будет публиковать пустые события — **и тесты на event_type-колонку этого не поймают**, нужно проверять содержимое payload.

---

## 7. Persistence — jOOQ и только generated классы

`spring-bootstrap/single-persistence-mechanism` **Persistence-слой во всех сервисах — только jOOQ.** Никаких альтернатив (JdbcTemplate, JPA/Hibernate, MyBatis, Spring Data JDBC), независимо от уровня зрелости сервиса. Это командное правило, оно перебивает любые обоснования вида «для CRUD JdbcTemplate проще» или «JPA даёт быстрый старт». Подключаем `spring-boot-starter-jooq` + `nu.studer.jooq` plugin для кодогенерации.

`spring-bootstrap/prefer-generated-types` **Используем максимум сгенерённого кода: generated POJO, generated enum'ы, generated table-references.** Handcrafted POJO/entity, дублирующие строку БД, удаляются. Цель — меньше кода и один источник правды (Liquibase-схема → jOOQ codegen → Java).

VARCHAR-колонки с фиксированным набором значений конвертируем в **Postgres ENUM types** через Liquibase (отдельный ChangeSet, обычно в `v-1.x/enum-types.yaml`):

```yaml
- changeSet:
    id: v-1.1-create-notification-channel-enum
    author: ...
    changes:
      - sql:
          sql: "CREATE TYPE notification_channel AS ENUM ('EMAIL','PUSH')"
          rollback: "DROP TYPE notification_channel"
      - sql:
          sql: |
            ALTER TABLE notifications
              ALTER COLUMN channel TYPE notification_channel
              USING channel::notification_channel
```

Тогда jOOQ codegen автоматически создаст Java enum (`NotificationChannel`) — handcrafted enum в `domain/` не нужен.

`spring-bootstrap/prefer-generated-types` **Generated-классы не модифицируем.** Если на enum нужны методы (например, `isTerminal()`, `canRetry()`) — inline'им проверку на use-sites (`status == NotificationStatus.FAILED`), либо кладём методы в отдельный utility-класс. Добавление методов в generated-enum нарушает «один источник правды»: при следующей перегенерации они пропадут.

`spring-bootstrap/external-dtos-are-handcrafted` **DTO внешних API остаются handcrafted.** Это касается только классов, дублирующих строку БД. JSON-DTO от REST-клиентов (`UserContact` от Customer BFF), Kafka-payload'ы, request/response DTO в OpenAPI-генерации — это не зона действия `BS-17/18`, они остаются ручными.

### Codegen из applied-схемы

Codegen в Gradle настроен так, что генерирует POJO/Records/Tables/Enums из **уже накатанной** Liquibase-схемы локального Postgres. Шаги local dev:

```bash
docker compose up -d postgres
./gradlew update              # liquibase update — накатывает миграции
./gradlew generateJooq        # jOOQ codegen из applied-схемы
./gradlew test                # generated-классы видны компилятору
```

Удобный shortcut — task `regenerate`, объединяющий `update + generateJooq`.

`build.gradle.kts` пример конфигурации (упрощённо):

```kotlin
jooq {
    configurations {
        create("main") {
            jooqConfiguration.apply {
                jdbc.apply { url = dbUrl; user = dbUser; password = dbPassword }
                generator.apply {
                    database.apply {
                        name = "org.jooq.meta.postgres.PostgresDatabase"
                        inputSchema = "public"
                        excludes = "databasechangelog|databasechangeloglock"
                    }
                    target.apply {
                        packageName = "<service>.generated"
                    }
                    generate.apply {
                        isPojos = true
                        isRecords = true
                    }
                }
            }
        }
    }
}
```

Сгенерированные файлы кладутся в `build/generated/jooq/` (в `.gitignore` через `**/generated/`) — на VCS не уходят, всегда регенерируются.

---

## 7a. Lint enforcement (Checkstyle)

`spring-bootstrap/style-check-wired-to-build` **Checkstyle обязателен** в `build.gradle` (`java-style/style-check-is-enforced` из `backend/java/java-style/references/implementation.md`). Конфиг `config/checkstyle/checkstyle.xml` коммитится в репо. Шаблон поставляется при создании сервиса через `ucp-bootstrap-design`.

`spring-bootstrap/style-check-wired-to-build` **Привязан к default-таргету `check`** (`java-style/style-check-is-enforced`), не к `checkSecurity`. Локально `./gradlew check` падает на нарушении nеи́минга/импортов сразу — разработчик не уезжает с пустяковыми нарушениями в PR.

```gradle
tasks.named('check') {
    dependsOn 'checkstyleMain', 'checkstyleTest'
}
```

`spring-bootstrap/style-check-wired-to-build` **`config/checkstyle/checkstyle-suppressions.xml`** коммитится даже пустым, по аналогии с `spring-bootstrap/thresholds-are-not-weakened`. Иначе при первом suppression PR разработчик создаёт файл с одним исключением, а ревьюер не видит контекста.

`spring-bootstrap/style-check-wired-to-build` ❌ Подключение Checkstyle с `ignoreFailures = true` или `maxWarnings > 0`. Эквивалент `spring-bootstrap/thresholds-are-not-weakened` для security: превращает lint в дашборд-без-действий, нарушает `java-style/style-check-is-enforced`.

---

## 8. Security/SAST enforcement

Полный набор security-инструментов и правил их использования — в `backend/security/references/java/implementation.md` (`R-SEC-*`). Здесь — enforcement-уровень: что обязано присутствовать в `build.gradle` и CI на старте сервиса.

`spring-bootstrap/security-checks-split-by-task` **Mandatory plugin set в `build.gradle`**. Сервис не считается готовым к деплою без всех пяти плагинов:

```gradle
plugins {
    id 'net.ltgt.errorprone' version '4.1.0'        // R-SEC-SAST-1
    id 'com.github.spotbugs' version '6.0.27'       // R-SEC-SAST-2 (FindSecBugs подтягивается через spotbugsPlugins)
    id 'org.owasp.dependencycheck' version '11.1.0' // R-SEC-DEP-1
}
```

Gitleaks и Trivy подключаются на уровне CI (отдельные actions/jobs), не gradle-плагинами — так корректнее, так как они сканируют артефакты вне Java-сборки.

`spring-bootstrap/security-checks-split-by-task` **Разделение `check` / `checkSecurity` / `checkSupplyChain`** — ключевое для скорости локальной итерации (`security/checks-layered-by-feedback-speed`). Обычный `./gradlew check` остаётся лёгким (тесты + Error Prone, ~30 сек), security-инструменты привязаны к отдельным task'ам:

```gradle
// Лёгкое SAST — на каждом PR, опционально локально перед push.
tasks.register('checkSecurity') {
    group = 'verification'
    description = 'SAST по коду: SpotBugs+FindSecBugs. На PR и опционально локально.'
    dependsOn 'spotbugsMain'
}

// Тяжёлое — supply chain. Только на merge в main / release / nightly. Локально не запускается.
tasks.register('checkSupplyChain') {
    group = 'verification'
    description = 'CVE в зависимостях. Только release/nightly — не на PR.'
    dependsOn 'dependencyCheckAnalyze'
}
```

Локально разработчик запускает `./gradlew check` (быстро) либо `./gradlew checkSecurity` (опционально, 30–90 сек). `dependencyCheckAnalyze` не запускается на dev-машине — у неё нет тёплого NVD-кэша, прогон уйдёт в 5–10 минут впустую.

В CI: `checkSecurity` параллельно тестам на каждом PR; `checkSupplyChain` — на merge в `main` + nightly + release-tag. PR-pipeline не вызывает `checkSupplyChain`.

`spring-bootstrap/thresholds-are-not-weakened` **`failOnError`/`failBuildOnCVSS` обязаны быть включены.** Конфиг ниже не подлежит ослаблению без явного RFC-комментария:

```gradle
spotbugs {
    ignoreFailures = false
    excludeFilter = file('config/spotbugs-exclude.xml')   // создаётся, даже если пустой
}
dependencyCheck {
    failBuildOnCVSS = 7.0                                 // HIGH/CRITICAL → break
    suppressionFile = 'config/dependency-check-suppressions.xml'
}
```

`spring-bootstrap/thresholds-are-not-weakened` **Suppression-файлы коммитятся в репо**, даже пустые (`config/spotbugs-exclude.xml`, `config/dependency-check-suppressions.xml`). Иначе при первом suppression PR разработчик создаёт файл с одним исключением, а ревьюер не видит контекста (история файла начинается «с нуля»).

`spring-bootstrap/security-checks-split-by-task` **CI security-job параллелен тестам, не последовательный.** `security/checks-layered-by-feedback-speed` — без параллельности security-стадия удлиняет PR-feedback-loop с 5 до 10 минут, что приводит к попыткам её отключения.

`spring-bootstrap/security-checks-split-by-task` **`checkSupplyChain` вынесен в отдельный workflow** (`security-supply-chain.yml`) с триггерами `push: branches: [main]`, `schedule: cron: '0 3 * * *'` (nightly), и `release`. Не запускается на `pull_request`. Падение этого workflow создаёт issue с label `security`, но не блокирует merge feature-веток.

`spring-bootstrap/secret-scan-and-nvd-key` **Pre-commit hook** с Gitleaks — обязателен (`security/checks-layered-by-feedback-speed`). Устанавливается через `pre-commit install` или `husky`, инструкция по установке в README. Без hook'а первый разработчик в команде закоммитит секрет → инцидент с rotation. Hook сканирует diff (0.5–2 сек), не historyю.

`spring-bootstrap/secret-scan-and-nvd-key` **`NVD_API_KEY` обязателен в CI secrets.** Без ключа `dependencyCheckAnalyze` упрётся в rate-limit NVD и будет валиться через раз. Получается на nvd.nist.gov бесплатно за 5 минут.

`spring-bootstrap/image-follows-security-requirements` **Dockerfile и k8s-манифесты подчиняются `R-SEC-IMG-*`.** Из bootstrap-перспективы критичные требования: non-root user (`USER 1000:1000`), base image с digest-pin (не `:latest`), `HEALTHCHECK`. Trivy в CI с `severity: HIGH,CRITICAL exit-code: 1` — без него нет cycle-замыкания.

`spring-bootstrap/secret-scan-and-nvd-key` **`.gitleaks.toml` и pre-commit hook**. Ловит секреты до того, как они уйдут в push. CI-step gitleaks страховочный — pre-commit главный.

`spring-bootstrap/thresholds-are-not-weakened` ❌ **`spotbugs { ignoreFailures = true }`** или эквивалентное «отключим, чтобы зелёная сборка». Security превращается в дашборд-без-действий — нарушает `security/high-severity-breaks-build`. Если поломанные SpotBugs-findings блокируют всю команду — добавляй конкретные suppressions с обоснованием в `config/spotbugs-exclude.xml`, не глобально отключай инструмент.

`spring-bootstrap/thresholds-are-not-weakened` ❌ **Подавление Dependency-Check через `failBuildOnCVSS = 11`** (фейк-thresholds). Если CVE требует обхода — добавляй suppression с `until=` и `<notes>` в `dependency-check-suppressions.xml`, не повышай порог.

`spring-bootstrap/thresholds-are-not-weakened` ❌ **Security-job в CI с `continue-on-error: true`**. Эквивалент пункту `spring-bootstrap/thresholds-are-not-weakened` на уровне CI — все findings игнорируются, никто не видит fail. Если стадия flaky — фиксируй причину flakyness, не маскируй.

При любом подозрении, что security-настройка ослаблена — запусти `ucp-security-review` для аудита.

---

## 9. Quickstart-чеклист

Когда сервис **не стартует**, проходим по этому списку перед глубоким копанием:

1. Все ли интерфейсы из `core/service/*` имеют production-реализацию (`spring-bootstrap/time-source-is-single-and-swappable`)?
2. Активен ли профиль (`local` для `bootRun`)? Без профиля security требует JWK от живого Keycloak.
3. Поднят ли Postgres из docker-compose? (`docker compose up -d postgres`)
4. Liquibase накатил миграции? Смотри лог `liquibase.util: UPDATE SUMMARY`.
5. Generated jOOQ-классы на месте? (`./gradlew generateJooq` после `update`)
6. На production-старте — есть ли `spring.security.oauth2.resourceserver.jwt.jwk-set-uri` в ENV?

Когда сервис стартует, но:
- События не уходят в Kafka — проверь, что `adapter-out-kafka` подключён в `bootstrap/build.gradle.kts` и `KafkaExternalEventPublisher` подменил logging-stub (см. `spring-bootstrap/stub-publisher-is-overridable`).
- В коде есть handcrafted POJO/enum, дублирующие БД, — это нарушение `spring-bootstrap/prefer-generated-types`. Замени на generated-классы и удали handcrafted, см. `BS-17/18/19`.
