---
name: ucp-integration-review
description: Ревью структуры outbound-интеграции в Java/Spring (коды R-RES-OAS-*, R-LAY-*, R-HEX-*, BS-*) — split client-generator/out-adapter, port в core/, ClientSettings/ClientConfig, exception-hierarchy, Mapper generated DTO ↔ domain, gradle patch.
when_to_use: Новый или изменённый *-out-adapter / *-client-generator модуль, port в core/**/port/out/, settings.gradle.kts.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(./gradlew*)
---

# Ревью outbound-интеграции — структурные аспекты

Ты ревьюишь модули `*-client-generator` и `*-out-adapter` на соответствие принятой структуре outbound-интеграции. Этот скилл — структурный двойник `ucp-resilience-review`: resilience-review проверяет таймауты/CB/retry/bulkhead/health, **этот** скилл — модульный split, port в core/, configuration properties, exception hierarchy, mapper-границы, gradle patch.

## Зависимости

- **`.claude/docs/backend/resilience/resilience-rules.md`** — `R-RES-OAS-*` (Mapper, generated DTO не утекает, openapi-generator target), `R-RES-ISO-*` (per-system bean isolation).
- **`.claude/docs/backend/usecase-pattern/usecase-pattern-rules.md`** — `R-LAY-3` (MapStruct по умолчанию), `R-HEX-*` (порт в `core/<bc>/port/`, зависимости направлены внутрь).
- **`.claude/docs/backend/java/spring-bootstrap/spring-bootstrap-rules.md`** — `BS-*` (gradle multi-module, openapi-generator setup).
- **`.claude/docs/backend/auth-patterns/auth-patterns-rules.md`** — `AUTH-13`/`AUTH-14` (выбор схемы аутентификации), `AUTH-17` (секреты в Vault/SealedSecrets, не в `application.yml`).

## Инструкции

1. **Прочти style-guide'ы по нужным секциям** — не весь файл, только разделы по кодам, цитируемым в findings.

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
   - Port-интерфейс в `core/src/main/java/<pkg>/domain/port/out/<system>/<System>Port.java`. Расположение в `adapter/` или `application/` — `R-HEX-X1`.
   - Методы port'а используют **только** domain-типы: `Command`-record на вход, `Result`-record на выход. Generated DTO в сигнатуре port-метода — `R-RES-OAS-X3`.
   - `<Op>Command` и `<Op>Result` — records в `core/.../port/out/<system>/{command,result}/`.
   - Abstract base `<System>PortException extends RuntimeException` в `core/.../port/out/<system>/exception/`.
   - `core/` **не** импортирует `org.springframework.*`, `org.openapitools.*`, generated-пакеты — `R-HEX-X2`.

   На **Уровне 1–2** port-интерфейс не обязателен — `<System>Client` инжектится в `<Operation>UseCaseHandler` напрямую. Если на Уровне 1–2 видишь port-интерфейс без необходимости — это **не** нарушение, но в findings отметь как «преждевременная абстракция».

   ### 3.3. ClientSettings (@ConfigurationProperties record)
   - `@ConfigurationProperties("client.<system>")` + `@Validated` + Java `record`.
   - Поля типизированы: `Duration` для таймаутов (не `int millis`), `URL`/`String` для baseUrl, `int` для poolSize.
   - Bean Validation: `@NotNull` на обязательных полях, `@Min(1)` на размерах пулов.
   - **Секреты (`apiKey`)** — обычное поле String, **без значения по умолчанию**. Заполнение — через `${SYSTEM_API_KEY}` в `application.yml`, не commit'ить значение (`AUTH-17`).
   - Файл лежит в `<system>-out-adapter/` (не в `bootstrap/` — это per-system, не cross-cutting).

   ### 3.4. ClientConfig (@Configuration)
   - `@Configuration` + `@RequiredArgsConstructor` + `@EnableConfigurationProperties(<System>ClientSettings.class)`.
   - `@Bean("<system>RestClient")` (или OkHttpClient) — `name` обязательно совпадает с system slug. Shared bean без `name` — `R-RES-ISO-X1`.
   - **Per-system pool**: connection pool настроен внутри bean'а (не `setDefault(...)` на shared instance), `R-RES-ISO-1`.
   - Generated API-class бин: `@Bean <System>DefaultApi <system>Api(@Qualifier("<system>RestClient") RestClient rc)`.

   ### 3.5. ClientAdapter (implements <System>Port)
   - `@Component` + `@RequiredArgsConstructor` + `@Slf4j`.
   - `implements <System>Port` — на Уровне 3. На Уровне 1–2 — самостоятельный `@Component`.
   - Все методы возвращают **domain** Result (не generated DTO) — `R-RES-OAS-X3`.
   - Маппинг через `<System>Mapper`-bean, не вручную в теле метода (`R-LAY-3`).
   - Generated DTO видны **только** внутри adapter-класса; импорта `generated.model.*` за пределами `<system>-out-adapter/` быть не должно.

   ### 3.6. Mapper (R-LAY-3)
   - **По умолчанию MapStruct**: `@Mapper(componentModel = "spring")` interface + `default`-методы для нетривиальных конверсий.
   - Hand-written `@Component`-маппер допустим **только** если маппинг stateful / DI-зависимый (например, нужен `DateTimeService` для конвертации времени). Иначе — `R-LAY-3` нарушено.
   - Маппер живёт в `<system>-out-adapter/`, не в `core/`.
   - Возвращаемый тип — domain-объект; generated DTO — только параметр.

   ### 3.7. Exception hierarchy
   Иерархия (`core/.../port/out/<system>/exception/`):
   ```
   <System>PortException (abstract, extends RuntimeException) ── в core/
       └── <System>Exception ── в adapter/
                ├── <System>ClientException (4xx)
                └── <System>ServerException (5xx)
   ```
   - Abstract base в `core/` — domain видит только его (не concrete subclasses).
   - Concrete subclasses в `<system>-out-adapter/` — там же, где adapter.
   - В `ClientAdapter` catch'ятся `HttpClientErrorException` (→ `<System>ClientException`) и `HttpServerErrorException` (→ `<System>ServerException`). Catch `Exception` без преобразования — `R-HND-X2` (инфраструктурные исключения утекают).

   ### 3.8. HealthIndicator
   - `<System>HealthIndicator implements HealthIndicator` в `<system>-out-adapter/`.
   - Адресован в `ucp-resilience-review` (`R-RES-HC-*`) — здесь проверяй только **наличие** файла и регистрацию (`management.health.<system>.enabled: true` в `application.yml`).

   ### 3.9. application.yml patch
   - Блок `client.<system>:` — все поля из `ClientSettings`.
   - Блок `resilience4j.{circuitbreaker,bulkhead,retry}.instances.<system>` — настройки resilience (детали — `ucp-resilience-review`).
   - Блок `management.health.<system>.enabled: true`.
   - Все секреты (`api-key`, `client-secret`) — через `${ENV_VAR}`, не литералы (`AUTH-17`).

   ### 3.10. Build patch
   - `settings.gradle.kts` содержит `include(":<system>-client-generator")` и `include(":<system>-out-adapter")`.
   - `bootstrap/build.gradle.kts` зависит от `<system>-out-adapter` (`implementation(project(":<system>-out-adapter"))`).
   - `<system>-client-generator/build.gradle.kts` имеет `id("org.openapi.generator")` и `generatorName = "spring-restclient"` (для нового кода — `R-RES-OAS-2`).

4. **При ревью кода ищи паттерны-нарушения:**

   - `client-generator` и `out-adapter` склеены в один модуль — `BS-MOD-X1`.
   - `<System>Port` в `adapter/` или `application/` — `R-HEX-X1`.
   - `<System>Port.findX(SberGeneratedRequest)` — generated DTO в сигнатуре — `R-RES-OAS-X3`.
   - `ClientSettings` — обычный class с сеттерами (не record), без `@Validated` — отступление от шаблона.
   - `ClientSettings` хранит `int connectTimeoutMs` вместо `Duration` — стилистика; на ревью отметь как warning.
   - В `application.yml` `client.<system>.api-key: "<literal-secret>"` вместо `${SYSTEM_API_KEY}` — `AUTH-17`.
   - `@Bean RestClient sharedRestClient` без `name` или с `name = "default"` — `R-RES-ISO-X1`.
   - `ClientAdapter` возвращает generated DTO (`SberRegisterResponse`) — `R-RES-OAS-X3`.
   - `core/` импортирует `org.springframework.web.client.*`, `org.openapitools.client.model.*` — `R-HEX-X2`.
   - Маппинг внутри `ClientAdapter` методом (без отдельного `Mapper`-bean) — `R-LAY-3` (стиль), отметь как warning, если маппинг тривиален (1 поле), иначе critical.
   - Hand-written `@Component MapperImpl` для маппинга, который выражается MapStruct-аннотациями — `R-LAY-3`.
   - `catch (Exception e) { throw new RuntimeException(e); }` без преобразования в `<System>ClientException` / `<System>ServerException` — `R-HND-X2`.
   - `<System>PortException` отсутствует — domain ловит concrete `<System>Exception` (из adapter) — `R-HEX-X2` (адаптер утекает в core).
   - Generated пакет (`<pkg>.<system>.generated.*`) импортируется из `bootstrap/` или другого `-out-adapter` — `R-RES-OAS-X3` (утечка границ).
   - `setting.gradle.kts` упоминает только `out-adapter`, без `client-generator` — модуль не подключён, сборка может работать только из-за зависимостей в IDE.

5. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-finding-format.md` (`RFF-1`..`RFF-16`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`R-RES-OAS-X3`, `R-HEX-X2`, `AUTH-17`).

6. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — структурные нарушения, ведущие к утечке границ / невозможности заменить adapter:
     - Generated DTO в сигнатуре port-метода (`R-RES-OAS-X3`) — domain намертво привязан к внешней API.
     - Port в `adapter/` (`R-HEX-X1`) — гексагональность сломана.
     - `core/` импортирует Spring/openapitools (`R-HEX-X2`) — слой не изолирован.
     - Литеральный секрет в `application.yml` (`AUTH-17`) — пойдёт в git history.
     - `<System>PortException` отсутствует — concrete adapter-exception утекают в domain.
   - **Предупреждение** — отклонения от конвенций:
     - Hand-written mapper для тривиального маппинга (`R-LAY-3`).
     - `ClientSettings` не как record (`R-LAY-3` extended).
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
