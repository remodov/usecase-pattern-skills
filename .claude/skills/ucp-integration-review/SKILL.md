---
name: ucp-integration-review
description: Ревью структуры outbound-интеграции в Java/Spring (требования resilience/*, usecase-pattern/*) — split client-generator/out-adapter, port в core/, ClientSettings/ClientConfig, exception-hierarchy, Mapper generated DTO ↔ domain, gradle patch.
when_to_use: Новый или изменённый *-out-adapter / *-client-generator модуль, port в core/**/port/out/, settings.gradle.kts.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(./gradlew*)
---

# Ревью outbound-интеграции — структурные аспекты

Ты ревьюишь модули `*-client-generator` и `*-out-adapter` на соответствие принятой структуре outbound-интеграции. Этот скилл — структурный двойник `ucp-resilience-review`: resilience-review проверяет таймауты/CB/retry/bulkhead/health, **этот** скилл — модульный split, port в core/, configuration properties, exception hierarchy, mapper-границы, gradle patch.

## Зависимости

- **`.claude/docs/backend/resilience/spec.md`** — `R-RES-OAS-*` (Mapper, generated DTO не утекает, openapi-generator target), `R-RES-ISO-*` (per-system bean isolation).
- **`.claude/docs/backend/usecase-pattern/spec.md`** — `usecase-pattern/explicit-mapper-between-layers` (MapStruct по умолчанию), `R-HEX-*` (порт в `core/port/out/client/`, зависимости направлены внутрь).
- **`.claude/docs/backend/java/spring-bootstrap/spec.md`** — `BS-*` (gradle multi-module, openapi-generator setup).
- **`.claude/docs/backend/auth-patterns/spec.md`** — `auth-patterns/service-to-service-authenticated`/`auth-patterns/service-to-service-authenticated` (выбор схемы аутентификации), `auth-patterns/no-secrets-in-repository` (секреты в Vault/SealedSecrets, не в `application.yml`).

## Инструкции

1. **Прочти требования по нужным разделам** — не весь файл, только то, на что ссылаешься в находках.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на недавно изменённые файлы в `*-out-adapter/`, `*-client-generator/`, `core/**/port/out/`.
   - Найди новые/изменённые `*Port.java`, `*ClientConfig.java`, `*ClientSettings.java`, `*ClientAdapter.java`, `*Mapper.java`, `*PortException.java`.
   - `settings.gradle.kts` (новые `include(":<system>-*")`).
   - `application.yml` (новые `client.<system>.*` блоки).

3. **Прогон по структурным правилам:**

   ### 3.1. Module split (BS-* + R-HEX-*)
   - **Два отдельных модуля**: `<system>-client-generator/` (только openapi-generator + сгенерированный код) и `<system>-out-adapter/` (config, adapter, mapper). Если в одном модуле и генерация, и adapter-код — `BS-MOD-X1`.
   - `<system>-out-adapter` зависит от `<system>-client-generator` (через `project(":<system>-client-generator")`) и от `:core`.
   - `<system>-client-generator` **не** зависит от `:core` (генератор не должен видеть domain).
   - Оба модуля прописаны в `settings.gradle.kts`.

   ### 3.2. Domain port (R-HEX-*)
   На **Уровне 3** обязательно:
   - Port-интерфейс в `core/src/main/java/<pkg>/core/port/out/client/<System>Port.java`. Расположение в `adapter/` или `application/` — `hexagonal/outbound-port-interface-in-core`.
   - Методы port'а используют **только** domain-типы: `Command`-record на вход, `Result`-record на выход. Generated DTO в сигнатуре port-метода — `R-RES-OAS-X3`.
   - `<Op>Command` и `<Op>Result` — records в `core/port/out/`.
   - Abstract base `<System>PortException extends RuntimeException` в `core/exception/`.
   - `core/` **не** импортирует `org.springframework.*`, `org.openapitools.*`, generated-пакеты — `hexagonal/core-free-of-framework`.

   На **Уровне 1–2** port-интерфейс не обязателен — `<System>Client` инжектится в `<Operation>CommandHandler` напрямую. Если на Уровне 1–2 видишь port-интерфейс без необходимости — это **не** нарушение, но в findings отметь как «преждевременная абстракция».

   ### 3.3. ClientSettings (@ConfigurationProperties record)
   - `@ConfigurationProperties("client.<system>")` + `@Validated` + Java `record`.
   - Поля типизированы: `Duration` для таймаутов (не `int millis`), `URL`/`String` для baseUrl, `int` для poolSize.
   - Bean Validation: `@NotNull` на обязательных полях, `@Min(1)` на размерах пулов.
   - **Секреты (`apiKey`)** — обычное поле String, **без значения по умолчанию**. Заполнение — через `${SYSTEM_API_KEY}` в `application.yml`, не commit'ить значение (`auth-patterns/no-secrets-in-repository`).
   - Файл лежит в `<system>-out-adapter/` (не в `bootstrap/` — это per-system, не cross-cutting).

   ### 3.4. ClientConfig (@Configuration)
   - `@Configuration` + `@RequiredArgsConstructor` + `@EnableConfigurationProperties(<System>ClientSettings.class)`.
   - `@Bean("<system>RestClient")` (или OkHttpClient) — `name` обязательно совпадает с system slug. Shared bean без `name` — `resilience/client-per-external-system`.
   - **Per-system pool**: connection pool настроен внутри bean'а (не `setDefault(...)` на shared instance), `resilience/client-per-external-system`.
   - Generated API-class бин: `@Bean <System>DefaultApi <system>Api(@Qualifier("<system>RestClient") RestClient rc)`.

   ### 3.5. ClientAdapter (implements <System>Port)
   - `@Component` + `@RequiredArgsConstructor` + `@Slf4j`.
   - `implements <System>Port` — на Уровне 3. На Уровне 1–2 — самостоятельный `@Component`.
   - Все методы возвращают **domain** Result (не generated DTO) — `R-RES-OAS-X3`.
   - Маппинг через `<System>Mapper`-bean, не вручную в теле метода (`usecase-pattern/explicit-mapper-between-layers`).
   - Generated DTO видны **только** внутри adapter-класса; импорта `generated.model.*` за пределами `<system>-out-adapter/` быть не должно.

   ### 3.6. Mapper (R-LAY-3)
   - **По умолчанию MapStruct**: `@Mapper(componentModel = "spring")` interface + `default`-методы для нетривиальных конверсий.
   - Hand-written `@Component`-маппер допустим **только** если маппинг stateful / DI-зависимый (например, нужен `DateTimeService` для конвертации времени). Иначе — `usecase-pattern/explicit-mapper-between-layers` нарушено.
   - Маппер живёт в `<system>-out-adapter/`, не в `core/`.
   - Возвращаемый тип — domain-объект; generated DTO — только параметр.

   ### 3.7. Exception hierarchy
   Иерархия (`core/exception/`):
   ```
   <System>PortException (abstract, extends RuntimeException) ── в core/
       └── <System>Exception ── в adapter/
                ├── <System>ClientException (4xx)
                └── <System>ServerException (5xx)
   ```
   - Abstract base в `core/` — domain видит только его (не concrete subclasses).
   - Concrete subclasses в `<system>-out-adapter/` — там же, где adapter.
   - В `ClientAdapter` catch'ятся `HttpClientErrorException` (→ `<System>ClientException`) и `HttpServerErrorException` (→ `<System>ServerException`). Catch `Exception` без преобразования — `usecase-pattern/infrastructure-errors-become-domain` (инфраструктурные исключения утекают).

   ### 3.8. HealthIndicator
   - `<System>HealthIndicator implements HealthIndicator` в `<system>-out-adapter/`.
   - Адресован в `ucp-resilience-review` (`R-RES-HC-*`) — здесь проверяй только **наличие** файла и регистрацию (`management.health.<system>.enabled: true` в `application.yml`).

   ### 3.9. application.yml patch
   - Блок `client.<system>:` — все поля из `ClientSettings`.
   - Блок `resilience4j.{circuitbreaker,bulkhead,retry}.instances.<system>` — настройки resilience (детали — `ucp-resilience-review`).
   - Блок `management.health.<system>.enabled: true`.
   - Все секреты (`api-key`, `client-secret`) — через `${ENV_VAR}`, не литералы (`auth-patterns/no-secrets-in-repository`).

   ### 3.10. Build patch
   - `settings.gradle.kts` содержит `include(":<system>-client-generator")` и `include(":<system>-out-adapter")`.
   - `bootstrap/build.gradle.kts` зависит от `<system>-out-adapter` (`implementation(project(":<system>-out-adapter"))`).
   - `<system>-client-generator/build.gradle.kts` имеет `id("org.openapi.generator")` и `generatorName = "spring-restclient"` (для нового кода — `resilience/client-generated-from-contract`).

4. **При ревью кода ищи паттерны-нарушения:**

   - `client-generator` и `out-adapter` склеены в один модуль — `BS-MOD-X1`.
   - `<System>Port` в `adapter/` или `application/` — `hexagonal/outbound-port-interface-in-core`.
   - `<System>Port.findX(SberGeneratedRequest)` — generated DTO в сигнатуре — `R-RES-OAS-X3`.
   - `ClientSettings` — обычный class с сеттерами (не record), без `@Validated` — отступление от шаблона.
   - `ClientSettings` хранит `int connectTimeoutMs` вместо `Duration` — стилистика; на ревью отметь как warning.
   - В `application.yml` `client.<system>.api-key: "<literal-secret>"` вместо `${SYSTEM_API_KEY}` — `auth-patterns/no-secrets-in-repository`.
   - `@Bean RestClient sharedRestClient` без `name` или с `name = "default"` — `resilience/client-per-external-system`.
   - `ClientAdapter` возвращает generated DTO (`SberRegisterResponse`) — `R-RES-OAS-X3`.
   - `core/` импортирует `org.springframework.web.client.*`, `org.openapitools.client.model.*` — `hexagonal/core-free-of-framework`.
   - Маппинг внутри `ClientAdapter` методом (без отдельного `Mapper`-bean) — `usecase-pattern/explicit-mapper-between-layers` (стиль), отметь как warning, если маппинг тривиален (1 поле), иначе critical.
   - Hand-written `@Component MapperImpl` для маппинга, который выражается MapStruct-аннотациями — `usecase-pattern/explicit-mapper-between-layers`.
   - `catch (Exception e) { throw new RuntimeException(e); }` без преобразования в `<System>ClientException` / `<System>ServerException` — `usecase-pattern/infrastructure-errors-become-domain`.
   - `<System>PortException` отсутствует — domain ловит concrete `<System>Exception` (из adapter) — `hexagonal/core-free-of-framework` (адаптер утекает в core).
   - Generated пакет (`<pkg>.<system>.generated.*`) импортируется из `bootstrap/` или другого `-out-adapter` — `R-RES-OAS-X3` (утечка границ).
   - `setting.gradle.kts` упоминает только `out-adapter`, без `client-generator` — модуль не подключён, сборка может работать только из-за зависимостей в IDE.

5. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md` (`review-format/*`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`R-RES-OAS-X3`, `hexagonal/core-free-of-framework`, `auth-patterns/no-secrets-in-repository`).

6. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — структурные нарушения, ведущие к утечке границ / невозможности заменить adapter:
     - Generated DTO в сигнатуре port-метода (`R-RES-OAS-X3`) — domain намертво привязан к внешней API.
     - Port в `adapter/` (`hexagonal/outbound-port-interface-in-core`) — гексагональность сломана.
     - `core/` импортирует Spring/openapitools (`hexagonal/core-free-of-framework`) — слой не изолирован.
     - Литеральный секрет в `application.yml` (`auth-patterns/no-secrets-in-repository`) — пойдёт в git history.
     - `<System>PortException` отсутствует — concrete adapter-exception утекают в domain.
   - **Предупреждение** — отклонения от конвенций:
     - Hand-written mapper для тривиального маппинга (`usecase-pattern/explicit-mapper-between-layers`).
     - `ClientSettings` не как record (`usecase-pattern/explicit-mapper-between-layers` extended).
     - Module split не сделан (`BS-MOD-X1`).
     - `ClientAdapter` без `@Slf4j` при наличии catch-блоков — нет логирования отказов.
   - **Замечание** — стилистика:
     - `int connectTimeoutMs` вместо `Duration connectTimeout`.
     - `@Bean(name = "...")` где `@Bean("...")` короче.
     - Имена beans не в snake-case slug формате (`sberApi` vs `sber-api` в `application.yml`).

## Что не входит

- Resilience-аспекты (timeouts, CB, retry, bulkhead, fallback, healthcheck-логика) — `ucp-resilience-review`.
- Тесты adapter'а (WireMock stub'ы) — `ucp-test-review`.
- Spring Security / OAuth2 / mTLS-конфиг — `ucp-auth-review`.
- REST API (наш inbound, не outbound) — `ucp-api-review`.
- Use Case / Handler, который дёргает port — `ucp-pattern-review`.
- jOOQ / persistence — `ucp-jooq-review`.
- Java-стиль (нейминг, импорты) — `ucp-java-style-review`.

После работы этого скилла **рекомендуется** запустить `ucp-resilience-review` на том же модуле — структурный и resilience-аспекты вместе дают полную картину.

$ARGUMENTS
