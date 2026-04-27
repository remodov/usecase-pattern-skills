# Spring Boot Bootstrap Style Guide

Правила боевой настройки Spring Boot-сервиса по Use Case Pattern: профили, бины, Security, Liquibase, Kafka. Каждое правило имеет код `BS-N` — скилл `ucp-bootstrap-design` цитирует их в ревью.

Базовый принцип (`BS-1`): **сервис должен запускаться локально одной командой, без живых внешних зависимостей** (кроме Postgres из docker-compose). Если для `bootRun` нужен живой Keycloak / Kafka / Catalog — это баг настройки, а не нормальное состояние dev-окружения.

---

## 1. Профили

`BS-2` На сервис заводятся ровно три состояния конфигурации:

| Профиль | Когда применять | Что включает |
|---|---|---|
| (без профиля) | Production / staging | Реальные внешние сервисы, IdP, Kafka, секьюрити |
| `local` | `./gradlew bootRun` для ручной разработки | Postgres из docker-compose, security `permitAll`, Kafka listeners выключены, Catalog/Payment URL-ы на dev-порты |
| `integration-test` | Только в `@SpringBootTest` | Postgres из docker-compose, WireMock-стабы для Catalog/Payment на фиксированных портах, schedulers заглушены, security `permitAll` |

Никаких `dev`, `staging`, `prod-readonly` сверху без явного бизнес-обоснования. Каждый профиль = отдельный `application-<profile>.yml` рядом с `application.yml`.

`BS-3` Profile **никогда не активируется кодом**. Активация — только через `--spring.profiles.active=local` либо `SPRING_PROFILES_ACTIVE`. Это значит: код, имеющий `@Profile("local")`, не должен включаться в production-сборку случайно.

`BS-4` `application.yml` — production-defaults (`localhost`/`9001`/`localhost:8081`-плейсхолдеры допустимы, но *настоящая* конфигурация прокидывается через ENV в Helm/деплоймент). `application-local.yml` и `application-integration-test.yml` — **только overrides** относительно базы. Не дублируйте всю конфигурацию.

---

## 2. Service-beans (DateTimeService / UuidGenerator / Clock)

`BS-5` Все «системные источники недетерминизма» (текущее время, UUID, случайные числа, сетевой `InetAddress`) **обёрнуты в интерфейс в core**. Это требование `TS-7` из test-strategy — тесты подменяют их через `@MockitoBean`. Интерфейсы пусты: `DateTimeService.now() : Instant`, `UuidGenerator.generate() : UUID`.

`BS-6` **Production-реализации этих интерфейсов обязательно регистрируются как beans** в `bootstrap`-модуле, обычно в `ServiceBeansConfig`. Без этого Spring не сможет собрать handler'ы (`UnsatisfiedDependencyException` на старте). Каждый под `@ConditionalOnMissingBean`, чтобы тесты могли подменять через `@MockitoBean`:

```java
@Configuration
public class ServiceBeansConfig {

    @Bean @ConditionalOnMissingBean
    public Clock systemClock() {
        return Clock.systemUTC();
    }

    @Bean @ConditionalOnMissingBean
    public DateTimeService dateTimeService(Clock clock) {
        return () -> Instant.now(clock);
    }

    @Bean @ConditionalOnMissingBean
    public UuidGenerator uuidGenerator() {
        return UUID::randomUUID;
    }
}
```

Типичная ошибка: интерфейс есть, тестовый `@MockitoBean` есть, в production контекста бина нет → context refresh падает на handler'е, который её инжектит. **Проверяй это первым делом, когда сервис не стартует.**

---

## 3. Security

`BS-7` Production `SecurityConfig` — **OAuth2 Resource Server с JWT** через `oauth2ResourceServer().jwt()`. JWK-set URL берётся из IdP (`spring.security.oauth2.resourceserver.jwt.jwk-set-uri`). Без живого IdP сервис не должен **обрабатывать запросы** в production — но **должен стартовать**, чтобы health-check показывал, что Spring контекст в порядке (JWK-fetch ленивый).

`BS-8` Production-конфиг помечается `@Profile("!integration-test & !local")`. На профилях `integration-test` и `local` — отдельные `SecurityFilterChain`-bean'ы с `permitAll()`, чтобы можно было вызывать API из Postman/curl без поднятия Keycloak. Локальная конфигурация **не отключает `@EnableMethodSecurity`** — `@PreAuthorize` остаётся; для проверки роле-зависимых сценариев в local используй `with(jwt())` в тестах или живой IdP.

`BS-9` Извлечение ролей из JWT — централизованно. Для Keycloak — из `realm_access.roles` с префиксом `ROLE_`. Реализуется как `JwtAuthenticationConverter`-bean, не размазывается по контроллерам.

---

## 4. Liquibase

`BS-10` Миграции живут на уровне репо в `migrations/db/` (не в `src/main/resources` модуля), так чтобы их можно было прогнать как Liquibase CLI без зависимости от Java-сборки. В `bootstrap`/`adapter-out-postgres` `build.gradle.kts` указывается `sourceSets.main.resources.srcDir(rootProject.file("migrations"))` — Liquibase по умолчанию ищет `classpath:db/changelog-master.yaml`.

`BS-11` `spring.liquibase.contexts` всегда явно задан (обычно `production`). Это даёт возможность использовать Liquibase `context`-фильтры для разделения dev-only / production-only ChangeSet'ов.

`BS-12` ChangeSet-файлы версионируются по релизам: `migrations/db/changelog/v-1.0/initial-schema.yaml`, `v-1.1/...`, и т.д. **Никогда не модифицируй уже применённый ChangeSet** — добавляй новый. Правка приведёт к рассинхрону checksum в `databasechangelog`.

---

## 5. Kafka

`BS-13` Без живой Kafka сервис должен **стартовать**, но `@KafkaListener`-консьюмеры — нет. Это решается одной строкой в `application-local.yml` и `application-integration-test.yml`:

```yaml
spring:
  kafka:
    listener:
      auto-startup: false
```

В тестах при необходимости консьюмер вызывается напрямую через `consumer.onMessage(record)` — не нужен embedded broker.

`BS-14` Producer/consumer key/value serializers — **`StringSerializer`/`StringDeserializer`** для outbox-events. Полезная нагрузка уже JSON-строка, повторное JSON-кодирование добавит лишние кавычки. JSON формируется в core через `EventPayloadSerializer` поверх Jackson.

`BS-15` `@ConditionalOnMissingBean(name = "kafkaExternalEventPublisher")` на logging-stub-имплементации `ExternalEventPublisher` — чтобы при подключении `adapter-out-kafka` Kafka-publisher автоматически перебивал стаб.

---

## 6. Jackson и события

`BS-16` `DomainEvent`-классы используют **record-style accessors** (`customerId()` вместо `getCustomerId()`). Default Jackson visibility их **не видит** — outbox payload получается с одними base-class полями. В `bootstrap` обязателен `JacksonConfig` с `Visibility.ANY` для полей:

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

## 7. Quickstart-чеклист

Когда сервис **не стартует**, проходим по этому списку перед глубоким копанием:

1. Все ли интерфейсы из `core/service/*` имеют production-реализацию (`BS-6`)?
2. Активен ли профиль (`local` для `bootRun`)? Без профиля security требует JWK от живого Keycloak.
3. Поднят ли Postgres из docker-compose? (`docker compose up -d postgres`)
4. Liquibase накатил миграции? Смотри лог `liquibase.util: UPDATE SUMMARY`.
5. На production-старте — есть ли `spring.security.oauth2.resourceserver.jwt.jwk-set-uri` в ENV?

Когда сервис стартует, но события не уходят в Kafka — проверь, что `adapter-out-kafka` подключён в `bootstrap/build.gradle.kts` и `KafkaExternalEventPublisher` подменил logging-stub (см. `BS-15`).
