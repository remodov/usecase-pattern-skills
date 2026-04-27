---
name: ucp-bootstrap-design
description: Design or fix Spring Boot bootstrap configuration for a Use Case Pattern service — profiles (local / integration-test / production), production beans for clock/UUID interfaces, SecurityConfig per profile, Liquibase, Kafka listener gating, Jackson event-payload visibility. Use when scaffolding a new service or when bootRun fails with UnsatisfiedDependencyException, JWK-set fetch errors, empty outbox payloads, or the service refuses to start without a live Keycloak/Kafka.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(docker compose*) Bash(curl*)
---

# Spring Boot Bootstrap Design

You are setting up — or rescuing — the Spring Boot bootstrap layer of a Use Case Pattern service: profiles, beans, security, persistence, messaging. This skill is **not** about scaffolding business logic (that's `ucp-pattern-design`); it's about making the service actually start and run locally and in production with the right configuration shape.

## When to invoke

- New service: bootstrap module is empty / missing profiles.
- `./gradlew bootRun` fails with `UnsatisfiedDependencyException` on a `DateTimeService` / `UuidGenerator` / similar core interface.
- Service won't start without Keycloak (JWK-set fetch errors at boot).
- Outbox events publish but payload is empty / contains only base fields (`id`, `aggregateId`, `aggregateType`, `createdAt`).
- `@KafkaListener`-consumers throw boot errors when there is no broker.
- User asks for a `local` profile, dev quickstart, or "why doesn't the service start without docker-compose up everything".

## Instructions

1. **Read the style guide** from `docs/spring-bootstrap-style-guide.md`. Every rule has a `BS-N` code; cite them in your design and review notes. On Level 4 projects also read `usecase-pattern-style-guide.md` for module layout.

2. **Diagnose if this is a fix or a from-scratch task.** For a fix, run the boot first and read the actual error:
   ```bash
   ./gradlew :bootstrap:bootRun --args='--spring.profiles.active=local'
   ```
   The `Quickstart-чеклист` (§7 of the style guide) lists the most common failures in order. Don't refactor the whole bootstrap until you've confirmed the actual symptom.

3. **Verify or create the three profile-files.** Per `BS-2`:
   - `application.yml` — production defaults (placeholders for IdP / Kafka / Catalog OK; real values via ENV).
   - `application-local.yml` — overrides for local dev (Postgres from docker-compose, `kafka.listener.auto-startup: false`, dev-port URLs for external services).
   - `application-integration-test.yml` — overrides for `@SpringBootTest` (WireMock-stub URLs, schedulers cron set to "never", auto-startup off).

   Don't duplicate the entire config in profile files — only the overrides. If you see the same key in all three with the same value, delete it from the profile.

4. **Register production beans for every core service interface.** Per `BS-5/BS-6`: any `core/service/*` interface (`DateTimeService`, `UuidGenerator`, etc.) needs a non-test bean. Put them in `bootstrap/.../config/ServiceBeansConfig`, all under `@ConditionalOnMissingBean` so `@MockitoBean` can override in tests:
   ```java
   @Bean @ConditionalOnMissingBean
   public DateTimeService dateTimeService(Clock clock) { return () -> Instant.now(clock); }
   ```
   This is the #1 cause of "service doesn't start" — the interface exists and tests work because `@MockitoBean` provides the bean, but production has nothing.

5. **Split `SecurityConfig` per profile.** Per `BS-7/BS-8`:
   - Production `SecurityConfig` is `@Profile("!integration-test & !local")` and uses `oauth2ResourceServer().jwt()`.
   - `LocalSecurityConfig` is `@Profile("local")` with `permitAll()` — keeps `@EnableMethodSecurity` so `@PreAuthorize` annotations stay active for the test-jwt path.
   - `TestJwtConfiguration` is `@Profile("integration-test")` with `permitAll()`.

   Three small classes is right. Don't try to do one universal config switching by ENV vars — Spring's profile system already gives you the gating.

6. **Gate Kafka listeners by profile.** Per `BS-13`: in both `local` and `integration-test`, set `spring.kafka.listener.auto-startup: false`. Consumers wired with `@KafkaListener` start only when explicitly resumed. In tests, invoke `consumer.onMessage(record)` directly with a hand-built `ConsumerRecord` — much simpler than embedded broker.

7. **Add the Jackson visibility customizer if events use record-style accessors.** Per `BS-16`: a typical `DomainEvent` subclass declares fields and exposes them via `customerId()`-style accessors. Jackson default visibility ignores them; outbox payload comes out with only base-class fields. Add a `JacksonConfig`:
   ```java
   @Bean
   public Jackson2ObjectMapperBuilderCustomizer objectMapperCustomizer() {
       return builder -> builder.postConfigurer((ObjectMapper m) ->
           m.setVisibility(m.getSerializationConfig().getDefaultVisibilityChecker()
               .withFieldVisibility(JsonAutoDetect.Visibility.ANY)));
   }
   ```
   When checking your fix, **inspect the actual payload column** in `outbox` — tests that only check `event_type` won't catch this regression.

8. **Wire migrations once, version forever.** Per `BS-10/BS-12`: `migrations/db/` at repo root, the `adapter-out-postgres` (or `bootstrap`) module pulls them via `srcDir(rootProject.file("migrations"))`. Subsequent schema changes go into new ChangeSet files (`v-1.1`, `v-1.2`); never edit applied ChangeSets — Liquibase will reject them on startup with checksum mismatch.

9. **Document the local quickstart in README**:
   ```bash
   docker compose up -d postgres
   ./gradlew :bootstrap:bootRun --args='--spring.profiles.active=local'
   ```
   Plus the matrix of profiles (BS-2). If the README doesn't say which profile to use for local dev, the next dev to clone this repo will spend an hour debugging a JWK-fetch failure.

## Output

Produce concrete files (Java + YAML) and a short PR description that lists:
- Which `BS-*` rules each file addresses.
- A trace of the original failure (if this was a fix), so future readers can grep for it.
- A `bootRun` log snippet showing the service starting cleanly on `local` profile (`Tomcat started on port 8080` line).

If anything in the user's existing setup violates `BS-*`, flag it explicitly with a citation — don't silently rewrite production-shaped code.
