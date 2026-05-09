---
name: ucp-hexagonal-design
description: Сгенерировать или ре-структурировать сервис под Hexagonal Architecture — multi-module gradle skeleton (core/persistence/*-in-adapter/*-out-adapter/bootstrap), settings.gradle.kts с include-ами, build.gradle.kts для каждого модуля с правильными dependencies (core без Spring/JOOQ, adapters → core), placeholder-классы (Application.java в bootstrap, package-info.java в core/<bc>/{aggregate,port}, ArchUnit base test). Решает: какой Tier (применять Hexagonal с Tier C+, иначе skip), какие in-adapter модули нужны (user/admin/kafka), какие out-adapter модули (persistence + per-system: payment/notification/storage), композиция bootstrap. Применяется при старте нового Tier C-сервиса либо при upgrade existing Tier B → Tier C. Триггеры: «hexagonal layout для нового сервиса», «реструктурируй под core/adapter».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Hexagonal — проектирование

Ты генерируешь multi-module gradle-проект под Hexagonal Architecture по Hexagonal Style Guide.

## Инструкции

1. **Прочитай** `.claude/docs/hexagonal-style-guide.md` (`R-HEX-*`). Опционально — `usecase-pattern-style-guide.md` (`R-LAY-*`), `spring-bootstrap-style-guide.md` (`BS-*`).

2. **Уточни параметры:**
   - **Service name** — `<service>` (`order-service`, `notification-service`).
   - **Tier** — должен быть **C+** (Hexagonal на Tier A/B = overkill, см. `R-HEX-WHEN-X1`). Если C/C+ не подтверждён — отказ генерировать с suggestion перейти на UCP L1-2.
   - **Bounded contexts** — список (для small-сервиса часто 1 BC; для модульного монолита 2-3+). Влияет на пакетную раскладку core/<bc>/.
   - **Inbound** — какие нужны: REST user, REST admin, Kafka consumer, scheduler, CLI?
   - **Outbound** — какие внешние системы: PG (всегда), payment (`sber`, `yandex-pay`), SMS (`twilio`), file-storage (`s3`), Kafka producer?

3. **Произведи код.** Lombok-defaults обязательны. Не цитируй коды правил в комментариях.

   ### 3.1. settings.gradle.kts

   ```kotlin
   rootProject.name = "<service>"

   include(
       ":core",
       ":persistence",
       ":user-api-in-adapter",
       ":admin-api-in-adapter",         // если есть admin REST
       ":kafka-in-adapter",              // если есть Kafka consumers
       ":kafka-out-adapter",             // если есть direct Kafka producers (часто не нужно — outbox в persistence)
       ":sber-out-adapter",              // если интеграция с Sber
       ":<system>-out-adapter",          // ... per system
       ":scheduler-out-adapter",         // если @Scheduled
       ":bootstrap"
   )
   ```

   ### 3.2. build.gradle.kts шаблоны

   **Root `build.gradle.kts`:**
   ```kotlin
   plugins {
       java
   }

   allprojects {
       group = "ru.example.<service>"
       version = "0.1.0-SNAPSHOT"
       repositories {
           mavenCentral()
           // maven("<your-internal-maven-repo>") // если есть внутренний Maven
       }
   }

   subprojects {
       apply(plugin = "java")
       java {
           sourceCompatibility = JavaVersion.VERSION_21
           targetCompatibility = JavaVersion.VERSION_21
       }
       dependencies {
           compileOnly("org.projectlombok:lombok:1.18.30")
           annotationProcessor("org.projectlombok:lombok:1.18.30")
           testImplementation("org.junit.jupiter:junit-jupiter:5.10.0")
       }
       tasks.test {
           useJUnitPlatform()
       }
   }
   ```

   **`core/build.gradle.kts`:**
   ```kotlin
   dependencies {
       // ТОЛЬКО эти зависимости — никакого Spring/JOOQ/etc (R-HEX-CORE-1)
       implementation("ru.vikulinva:ddd-building-blocks:1.0.0")
       implementation("ru.vikulinva:usecase-pattern:1.0.0")
       implementation("ru.vikulinva:hexagonal-architecture:1.0.0")
       implementation("jakarta.validation:jakarta.validation-api:3.0.2")
   }
   ```

   **`persistence/build.gradle.kts`:**
   ```kotlin
   plugins {
       id("ru.mttech.jooq.jooq-postgresql-generator-plugin")
   }
   dependencies {
       implementation(project(":core"))
       implementation("org.springframework.boot:spring-boot-starter-jooq")
       implementation("org.liquibase:liquibase-core")
       // generated jOOQ classes — auto via plugin
   }
   ```

   **`user-api-in-adapter/build.gradle.kts`:**
   ```kotlin
   plugins {
       id("org.openapi.generator")
   }
   dependencies {
       implementation(project(":core"))
       implementation("org.springframework.boot:spring-boot-starter-web")
       implementation("org.springframework.boot:spring-boot-starter-validation")
       implementation("org.mapstruct:mapstruct:1.5.5.Final")
       annotationProcessor("org.mapstruct:mapstruct-processor:1.5.5.Final")
   }
   openApiGenerate {
       generatorName.set("spring")
       inputSpec.set("$projectDir/src/main/resources/openapi/<service>-user.yaml")
       outputDir.set("$buildDir/generated/openapi")
       configOptions.set(mapOf(
           "useSpringBoot3" to "true",
           "useJakartaEe" to "true",
           "useBeanValidation" to "true"
       ))
   }
   ```

   **`<system>-out-adapter/build.gradle.kts`:**
   ```kotlin
   plugins {
       id("org.openapi.generator")
   }
   dependencies {
       implementation(project(":core"))
       implementation("org.springframework.boot:spring-boot-starter-web")     // для RestClient
       implementation("io.github.resilience4j:resilience4j-spring-boot3:2.2.0")
   }
   openApiGenerate {
       generatorName.set("spring-restclient")          // R-RES-OAS-2
       inputSpec.set("$projectDir/src/main/resources/openapi/<system>.openapi.yaml")
       configOptions.set(mapOf(
           "useSpringBoot3" to "true",
           "useJakartaEe" to "true",
           "useBeanValidation" to "true"
       ))
   }
   ```

   **`bootstrap/build.gradle.kts`:**
   ```kotlin
   plugins {
       id("org.springframework.boot")
       id("io.spring.dependency-management")
       id("com.gorylenko.gradle-git-properties")
   }
   dependencies {
       implementation(project(":core"))
       implementation(project(":persistence"))
       implementation(project(":user-api-in-adapter"))
       implementation(project(":admin-api-in-adapter"))
       implementation(project(":sber-out-adapter"))
       // ...все adapters
       implementation("org.springframework.boot:spring-boot-starter-actuator")
       implementation("io.micrometer:micrometer-registry-prometheus")
       implementation("io.opentelemetry.instrumentation:opentelemetry-spring-boot-starter")
       runtimeOnly("org.postgresql:postgresql")
   }
   springBoot {
       buildInfo()
   }
   ```

   ### 3.3. Placeholder-классы

   **`bootstrap/src/main/java/<pkg>/Application.java`:**
   ```java
   @SpringBootApplication
   public class Application {
       public static void main(String[] args) {
           SpringApplication.run(Application.class, args);
       }
   }
   ```

   **`core/src/main/java/<pkg>/domain/<bc>/aggregate/package-info.java`:**
   ```java
   /**
    * Aggregate Roots (DDD-tactical, R-AGG-*) для bounded context <bc>.
    * Содержит rich domain methods, порождает domain events, гарантирует инварианты.
    */
   package <pkg>.domain.<bc>.aggregate;
   ```

   **`core/src/main/java/<pkg>/domain/<bc>/port/out/package-info.java`:**
   ```java
   /**
    * Outbound ports для bounded context <bc> (R-HEX-PORT-*).
    * Interfaces — реализации в *-out-adapter/.
    */
   package <pkg>.domain.<bc>.port.out;
   ```

   ### 3.4. ArchUnit base-test (R-HEX-TEST-1)

   `bootstrap/src/test/java/<pkg>/architecture/HexagonalArchitectureTest.java`:
   ```java
   import com.tngtech.archunit.core.domain.JavaClasses;
   import com.tngtech.archunit.core.importer.ClassFileImporter;
   import org.junit.jupiter.api.BeforeAll;
   import org.junit.jupiter.api.Test;

   import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.*;

   public class HexagonalArchitectureTest {

       private static JavaClasses classes;

       @BeforeAll
       static void importClasses() {
           classes = new ClassFileImporter().importPackages("<pkg>");
       }

       @Test
       void coreShouldNotDependOnSpring() {
           noClasses().that().resideInAPackage("..domain..")
               .or().resideInAPackage("..usecase..")
               .should().dependOnClassesThat().resideInAPackage("org.springframework..")
               .check(classes);
       }

       @Test
       void coreShouldNotDependOnJooq() {
           noClasses().that().resideInAPackage("..domain..")
               .or().resideInAPackage("..usecase..")
               .should().dependOnClassesThat().resideInAPackage("org.jooq..")
               .check(classes);
       }

       @Test
       void portsShouldBeInterfaces() {
           classes().that().resideInAPackage("..port.out..")
               .should().beInterfaces()
               .check(classes);
       }

       @Test
       void inAdapterShouldNotDependOnOutAdapter() {
           noClasses().that().resideInAPackage("..adapter.in..")
               .should().dependOnClassesThat().resideInAPackage("..adapter.out..")
               .check(classes);
       }
   }
   ```

   `bootstrap/build.gradle.kts` добавить:
   ```kotlin
   testImplementation("com.tngtech.archunit:archunit-junit5:1.2.1")
   ```

   ### 3.5. Patch для existing Tier B → Tier C upgrade

   Если сервис уже существует на Tier B (один gradle-модуль), миграция — отдельный план:
   - Шаг 1: создать `core/` модуль + переместить туда domain + UseCase.
   - Шаг 2: создать `persistence/` модуль + переместить JOOQ-репозитории.
   - Шаг 3: разделить REST в `*-in-adapter/`.
   - Шаг 4: создать `bootstrap/` + перевести `Application.java`.
   - Шаг 5: добавить ArchUnit-тесты.

   В выводе скилла (для upgrade) — пошаговый план с командами `git mv`.

4. **Самопроверка перед выдачей** (`R-HEX-*`):
   - Multi-module: ≥ 4 модуля (core + persistence + ≥1 in-adapter + bootstrap).
   - `core/build.gradle.kts` — нет Spring, JOOQ, Jackson.
   - Каждый adapter — отдельный модуль; `*-in-adapter/` per-purpose; `*-out-adapter/` per-system.
   - `bootstrap/` зависит от всего, никто от него.
   - ArchUnit-тесты в bootstrap-test или отдельный модуль.
   - Placeholder package-info для domain и port.

5. **Структура вывода:**
   1. **Решения** — Tier, список модулей (in-adapters / out-adapters), bounded contexts.
   2. **Дерево модулей** — `tree`-style.
   3. **Каждый файл — отдельный code block** с путём.
   4. **Для upgrade existing-сервиса** — пошаговый migration plan с `git mv`.
   5. **Заметки по реализации:**
      - Команды: `./gradlew build`, `./gradlew :bootstrap:test --tests *HexagonalArchitectureTest`.
      - **TODO для пользователя:** заполнить domain (через `ucp-ddd-tactical-design`), создать use cases (через `ucp-pattern-design`), настроить openapi YAML для каждого in-adapter; настроить port-implementations через `ucp-integration-design` для outbound.
   6. **Финальный шаг:** «после генерации запусти `ucp-hexagonal-review` для верификации».

## Что НЕ делает

- Domain (Aggregate, Entity, VO, Events) внутри `core/<bc>/` — `ucp-ddd-tactical-design`.
- UseCase + Handler — `ucp-pattern-design`.
- jOOQ-имплементация в persistence/ — `ucp-jooq-design`.
- Out-adapter implementations — `ucp-integration-design`.
- REST OpenAPI YAML — `ucp-api-design`.
- Resilience-обвязка — `ucp-resilience-design`.

После — обязательно `ucp-hexagonal-review` для верификации.

$ARGUMENTS
