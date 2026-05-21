---
name: ucp-bootstrap-design
description: Спроектировать или починить bootstrap-конфигурацию Spring Boot для UCP-сервиса — профили (local / integration-test / production), production-бины для clock / UUID-интерфейсов, SecurityConfig per profile, Liquibase, jOOQ codegen + persistence только на сгенерированных типах, гейтинг Kafka-листенеров, видимость event-payload в Jackson. Применяется при шаблонировании нового сервиса или когда bootRun падает с UnsatisfiedDependencyException, ошибками fetch JWK-set, пустыми outbox-payload-ами, сервис отказывается стартовать без живого Keycloak / Kafka, или когда persistence-слой использует JdbcTemplate / JPA вместо jOOQ.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(docker compose*) Bash(curl*)
---

# Spring Boot Bootstrap — проектирование

Ты настраиваешь — или спасаешь — bootstrap-слой Spring Boot UCP-сервиса: профили, бины, безопасность, persistence, messaging. Этот скилл **не** про шаблонирование бизнес-логики (это `ucp-pattern-design`); он про то, чтобы сервис реально стартовал и работал локально и в проде с правильной конфигурацией.

## Когда вызывать

- Новый сервис: bootstrap-модуль пустой / профили отсутствуют.
- `./gradlew bootRun` падает с `UnsatisfiedDependencyException` на `DateTimeService` / `UuidGenerator` / похожем core-интерфейсе.
- Сервис не стартует без Keycloak (ошибки fetch JWK-set на загрузке).
- Outbox-события публикуются, но payload пустой / содержит только базовые поля (`id`, `aggregateId`, `aggregateType`, `createdAt`).
- `@KafkaListener`-консьюмеры бросают boot-ошибки, когда брокера нет.
- Пользователь просит профиль `local`, dev-quickstart или «почему сервис не стартует без docker-compose up everything».
- Persistence-слой использует JdbcTemplate / JPA / MyBatis или содержит ручные POJO / enum-классы, дублирующие строки БД — нарушение `BS-17/18` (только jOOQ, только сгенерированный).

## Инструкции

1. **Прочитай style guide** из `.claude/docs/spring-bootstrap-style-guide.md`. У каждого правила есть код `BS-N`; цитируй их в дизайне и review-заметках. На проектах Уровня 4 дополнительно прочитай `usecase-pattern-rules.md` для раскладки модулей.

2. **Диагностируй: это починка или с нуля.** Для починки сначала запусти и прочитай реальную ошибку:
   ```bash
   ./gradlew :bootstrap:bootRun --args='--spring.profiles.active=local'
   ```
   `Quickstart-чеклист` (§7 style guide) перечисляет самые частые сбои в порядке. Не рефактори весь bootstrap, пока не подтвердил конкретный симптом.

3. **Проверь или создай три файла-профиля.** По `BS-2`:
   - `application.yml` — production-дефолты (плейсхолдеры для IdP / Kafka / Catalog OK; реальные значения через ENV).
   - `application-local.yml` — оверрайды для локальной разработки (Postgres из docker-compose, `kafka.listener.auto-startup: false`, dev-port URL внешних сервисов).
   - `application-integration-test.yml` — оверрайды для `@SpringBootTest` (URL стабов WireMock, cron-расписания «никогда», auto-startup off).

   Не дублируй весь конфиг в profile-файлах — только оверрайды. Если видишь один и тот же ключ в трёх файлах с одним значением — удали из профиля.

4. **Зарегистрируй production-бины для каждого core service-интерфейса.** По `BS-5/BS-6`: любой `core/service/*`-интерфейс (`DateTimeService`, `UuidGenerator` и т.п.) нуждается в не-test-бине. Положи их в `bootstrap/.../config/ServiceBeansConfig`, всё под `@ConditionalOnMissingBean`, чтобы `@MockitoBean` мог переопределить в тестах:
   ```java
   @Bean @ConditionalOnMissingBean
   public DateTimeService dateTimeService(Clock clock) { return () -> Instant.now(clock); }
   ```
   Это причина №1 «сервис не стартует» — интерфейс есть, тесты работают, потому что `@MockitoBean` даёт бин, а в проде ничего нет.

5. **Раздели `SecurityConfig` по профилю.** По `BS-7/BS-8`:
   - Production-`SecurityConfig` — `@Profile("!integration-test & !local")`, использует `oauth2ResourceServer().jwt()`.
   - `LocalSecurityConfig` — `@Profile("local")` с `permitAll()` — оставь `@EnableMethodSecurity`, чтобы `@PreAuthorize`-аннотации остались активными для test-jwt-пути.
   - `TestJwtConfiguration` — `@Profile("integration-test")` с `permitAll()`.

   Три маленьких класса — это правильно. Не пытайся сделать один универсальный конфиг, переключающийся через ENV; система профилей Spring уже даёт тебе гейтинг.

6. **Гейтуй Kafka-листенеры по профилю.** По `BS-13`: и в `local`, и в `integration-test` ставь `spring.kafka.listener.auto-startup: false`. Консьюмеры на `@KafkaListener` стартуют только когда явно возобновлены. В тестах вызывай `consumer.onMessage(record)` напрямую с собранным руками `ConsumerRecord` — намного проще, чем embedded broker.

7. **Добавь Jackson visibility-кастомайзер, если события используют record-style accessors.** По `BS-16`: типичный сабкласс `DomainEvent` объявляет поля и выставляет их через `customerId()`-style accessors. Дефолтная видимость Jackson их игнорирует; outbox-payload получается только с base-class-полями. Добавь `JacksonConfig`:
   ```java
   @Bean
   public Jackson2ObjectMapperBuilderCustomizer objectMapperCustomizer() {
       return builder -> builder.postConfigurer((ObjectMapper m) ->
           m.setVisibility(m.getSerializationConfig().getDefaultVisibilityChecker()
               .withFieldVisibility(JsonAutoDetect.Visibility.ANY)));
   }
   ```
   Проверяя починку, **смотри реальное содержимое колонки payload** в `outbox` — тесты, проверяющие только `event_type`, эту регрессию не поймают.

8. **Подключи миграции один раз, версионируй навсегда.** По `BS-10/BS-12`: `migrations/db/` в корне репозитория, модуль `adapter-out-postgres` (или `bootstrap`) подтягивает их через `srcDir(rootProject.file("migrations"))`. Последующие изменения схемы — в новые ChangeSet-файлы (`v-1.1`, `v-1.2`); никогда не редактируй применённые ChangeSet-ы — Liquibase отвергнет их при старте по checksum-несовпадению.

9. **Persistence — только jOOQ, только сгенерированный.** По `BS-17/18/19/20`:
   - **Никакого JdbcTemplate, JPA, MyBatis.** Это применимо на **каждом** Tier (A/B/C). Если видишь репозиторий на JdbcTemplate или JPA `@Entity` — это нарушение; перепиши на jOOQ DSL над сгенерированными таблицами.
   - **Codegen-плагин**: `nu.studer.jooq` 10.x со стратегией PASCAL `_Pojo`. Codegen работает против **применённой** Liquibase-схемы в локальном Postgres — последовательность команд: `./gradlew update && ./gradlew generateJooq && ./gradlew test`. Добавь задачу `regenerate`, объединяющую обе.
   - **Используй сгенерированные POJO и enum-ы** (`<service>.generated.tables.pojos.*Pojo`, `<service>.generated.enums.*`) напрямую в репозиториях, сервисах, мапперах DTO контроллеров. Ручные классы `Notification` / `Channel` / `NotificationStatus`, дублирующие layout строки — удали.
   - **Колонки VARCHAR с фиксированными значениями → Postgres ENUM-типы.** Добавь отдельный ChangeSet `v-1.x/enum-types.yaml`, который создаёт enum и `ALTER`-ит колонку под него. Тогда jOOQ codegen сгенерирует Java-enum автоматически — никакого `forcedType`, никакого ручного enum.
   - **Сгенерированные классы не модифицируются.** Если на enum'е нужны методы (`isTerminal()`, `canRetry()`) — встрой проверку на use-sites или положи хелперы в utility-класс. Не редактируй сгенерированный код, он будет перезатёрт.
   - **Исключение** (`BS-20`): DTO внешних API (`UserContact` из REST-клиента, OpenAPI-сгенерированные DTO, Kafka-payload-ы) остаются ручными — они не из твоей БД.

   При починке сервиса с ручными POJO / enum миграция механическая: добавь плагин, добавь `v-1.x/enum-types.yaml` для любых VARCHAR-enum-колонок, запусти `regenerate`, удали ручные классы, search-and-replace импорты, тесты должны пройти после переименования типов.

10. **Задокументируй локальный quickstart в README**:
    ```bash
    docker compose up -d postgres
    ./gradlew :bootstrap:bootRun --args='--spring.profiles.active=local'
    ```
    Плюс матрица профилей (`BS-2`). Если в README не сказано, какой профиль использовать для локальной разработки — следующий dev, склонировавший репо, потратит час на отладку JWK-fetch-сбоя.

11. **Не цитируй коды правил в комментариях исходников** (`JS-7.3` в `java-style-guide.md`). В сгенерированных Java/YAML-файлах — никаких `// BS-7`, `// BS-13`, `# BS-10` и т.п. Соответствие правилу выражается через имена / структуру / аннотации. Комментарий уместен только когда WHY неочевиден из кода — и без цитаты правила.

12. **Lombok + MapStruct + OpenAPI-generator — обязательны в build с самого старта** (`JS-6.6`, `R-LAY-3`, style guide §12.2). Пропиши в `build.gradle.kts` каждого модуля (или в `subprojects { ... }`):

    ```kotlin
    plugins {
        id("org.openapi.generator") version "7.10.0"
    }

    dependencies {
        compileOnly("org.projectlombok:lombok:1.18.34")
        annotationProcessor("org.projectlombok:lombok:1.18.34")
        testCompileOnly("org.projectlombok:lombok:1.18.34")
        testAnnotationProcessor("org.projectlombok:lombok:1.18.34")

        implementation("org.mapstruct:mapstruct:1.6.3")
        annotationProcessor("org.mapstruct:mapstruct-processor:1.6.3")
        // Lombok+MapStruct interop — без этого MapStruct не видит Lombok-сгенерированных конструкторов.
        annotationProcessor("org.projectlombok:lombok-mapstruct-binding:0.2.0")
    }

    openApiGenerate {
        generatorName.set("spring")
        inputSpec.set("$projectDir/src/main/resources/openapi/<service>.openapi.yaml")
        outputDir.set("$buildDir/generated/openapi")
        apiPackage.set("<base>.generated.api")
        modelPackage.set("<base>.generated.api.model")
        configOptions.set(mapOf(
            "useSpringBoot3" to "true",
            "useJakartaEe" to "true",
            "interfaceOnly" to "true",
            "skipDefaultInterface" to "true",
            "useTags" to "true",
            "openApiNullable" to "false",
            "documentationProvider" to "none",
            "annotationLibrary" to "none",
            "dateLibrary" to "java8"
        ))
    }
    sourceSets["main"].java.srcDir("$buildDir/generated/openapi/src/main/java")
    tasks.named("compileJava") { dependsOn("openApiGenerate") }
    ```

    Без этого downstream-скиллы упадут: `ucp-pattern-design` генерит `@RequiredArgsConstructor`-handler-ы (`JS-6.1`), `@Mapper`-интерфейсы (`R-LAY-3`) и `Controller implements <Tag>Api` (§12.2) — все три annotation/codegen-цепочки должны работать с первой компиляции.

13. **Создай (или обнови) корневой `CLAUDE.md`.** Каждый UCP-сервис обязан нести в корне репозитория `CLAUDE.md` — always-loaded память для AI-агента. Нет файла — создай; есть — обнови соответствующий блок, не дублируя то, что и так выводится из кода. Минимальный обязательный контент:

    ```markdown
    ### Спецификация

    `docs/spec/` — источник правды по сервису (формат — Use Case спецификация Bounded
    Context). Точка входа — корневой файл контекста `docs/spec/<service>-spec.md`
    (секции уровня контекста); секции уровня агрегата — в
    `docs/spec/aggregates/<aggregate>.md` (для одноагрегатного сервиса всё в корневом
    файле). **Читай корневой файл в начале сессии** — раннее чтение оседает в тёплом
    префиксе кэша. Ссылки между разделами — по именам/якорям; машинная идентичность —
    в минимальном frontmatter (`context`, `aggregate`). Техника (схема БД, стек) — в
    разделе «Техническая реализация», домен — во всех остальных.

    ### Кодогенерация и ревью — через скиллы

    Любая работа над UCP-артефактом обязана идти через `/ucp-*` скилл, не писаться от руки:

    | Тип работы | Скилл |
    |---|---|
    | Спека по бизнес-описанию | `/ucp-spec-design` |
    | As-is спека из кода | `/ucp-spec-tier-0` |
    | Ревью спеки | `/ucp-spec-review` |
    | UseCase + Handler + Controller + маппер | `/ucp-pattern-design` |
    | OpenAPI + DTO из карточки команды | `/ucp-api-design` |
    | Aggregate + VO + Domain Event + Repository (Tier C) | `/ucp-ddd-tactical-design` |
    | Bootstrap (профили, jOOQ, Liquibase) | `/ucp-bootstrap-design` |
    | Тесты по разделу «Критерии приёмки» | `/ucp-test-design` |
    ```

    Держи `CLAUDE.md` коротким (always-loaded): только то, что неочевидно из кода/структуры.

## Вывод

Произведи конкретные файлы (Java + YAML + корневой `CLAUDE.md`) и короткое описание PR, перечисляющее:
- Какие правила `BS-*` адресуются каждым файлом.
- Трейс исходного сбоя (если это была починка), чтобы будущие читатели могли его найти.
- Сниппет `bootRun`-лога, показывающий, что сервис стартует чисто на профиле `local` (строка `Tomcat started on port 8080`).

Если что-то в существующей настройке пользователя нарушает `BS-*` — флаги это явно с цитатой, не переписывай production-shaped код молча.
