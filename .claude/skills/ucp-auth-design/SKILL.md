---
name: ucp-auth-design
description: Зашаблонить Spring Security + OAuth2 Resource Server для UCP-сервиса на Java/Spring (требования auth-patterns/*) — валидация JWT, маппинг ролей, RBAC на эндпоинтах, ABAC-хелперы, audit log-аспект, раскладка секретов, идемпотентность.
when_to_use: При старте нового сервиса или добавлении auth в существующий. В цепочке — после ucp-pattern-design.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Проектирование паттернов аутентификации/авторизации

Ты шаблонируешь слой безопасности / auth для Java/Spring-сервиса по требованиям `auth-patterns/*`.

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/auth-patterns/spec.md` (полный текст с примерами кода — `backend/auth-patterns/references/java/implementation.md`, открывай точечно по разделу). Цитируй правила `AUTH-N` **в design-обосновании ответа пользователю**, но **не в комментариях сгенерированного кода** (`java-style/no-rule-codes-or-history-in-code` в `backend/java/java-style/spec.md`). Никаких `// AUTH-15`, `// AUTH-9` в исходниках — соответствие выражается через `@PreAuthorize`, наличие audit-таблицы, `JwtAuthenticationConverter` и т.д.

2. **Подтверди слой.** Определи:
   - **Gateway** — здесь только валидация JWT + rate limiting. Сервис обычно не Gateway; если перед тобой именно Gateway — генерируешь правила маршрутизации, но не RBAC handler-ов.
   - **BFF** — валидация JWT + RBAC по ролям, агрегация вызовов. При необходимости — сессия в Redis.
   - **Domain Service** — валидация JWT (передаётся от Gateway / BFF) + RBAC + ABAC по владельцу ресурса + audit log для admin.

   Спроси, если непонятно. По умолчанию для UCP — **Domain Service**.

3. **Подключить зависимости:**

   ```kotlin
   implementation("org.springframework.boot:spring-boot-starter-security")
   implementation("org.springframework.boot:spring-boot-starter-oauth2-resource-server")
   ```

4. **Сгенерировать `SecurityConfig`** (`auth-patterns/token-validated-by-library`, `auth-patterns/roles-from-token-claims`):

   ```java
   @Configuration
   @EnableMethodSecurity
   public class SecurityConfig {

       @Bean
       SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
           http
               .csrf(AbstractHttpConfigurer::disable)
               .authorizeHttpRequests(auth -> auth
                   .requestMatchers("/actuator/health", "/actuator/prometheus").permitAll()
                   .anyRequest().authenticated())
               .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
               .oauth2ResourceServer(oauth -> oauth
                   .jwt(jwt -> jwt.jwtAuthenticationConverter(jwtAuthenticationConverter())));
           return http.build();
       }

       private JwtAuthenticationConverter jwtAuthenticationConverter() {
           var authorities = new JwtGrantedAuthoritiesConverter();
           authorities.setAuthorityPrefix("ROLE_");
           authorities.setAuthoritiesClaimName("realm_access.roles");
           var converter = new JwtAuthenticationConverter();
           converter.setJwtGrantedAuthoritiesConverter(authorities);
           return converter;
       }
   }
   ```

5. **`AuthenticatedX`-хелперы** (по одному на каждую задействованную роль):

   ```java
   @Component
   public class AuthenticatedCustomer {
       public CustomerId currentCustomerId() {
           var jwt = (Jwt) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
           return CustomerId.of(UUID.fromString(jwt.getSubject()));
       }
   }
   ```

6. **`@Component("access")`** для нетривиального ABAC (если есть ≥ 2 эндпоинта с проверкой владения):

   ```java
   @Component("access")
   public class AccessPolicy {
       private final OrderRepository orders;

       public boolean canViewOrder(UUID orderId, Authentication auth) {
           var jwt = (Jwt) auth.getPrincipal();
           var order = orders.findById(OrderId.of(orderId)).orElse(null);
           if (order == null) return false;
           if (auth.getAuthorities().stream().anyMatch(a -> "ROLE_admin".equals(a.getAuthority()))) return true;
           return order.customerId().value().toString().equals(jwt.getSubject());
       }
   }
   ```

6a. **Контур безопасности адаптера** — пакет `security/` входного адаптера: конвертер токена в принципала, запись принципала, провайдер контекста (`port/in`), перечисление ролей; сам `SecurityConfiguration` — в `config/` (`hexagonal/adapter-structure`). Конвертер читает нужное через порт напрямую, диспетчер не зовёт и состояние не меняет (`usecase-pattern/entry-calls-dispatcher`).

7. **На каждом REST-эндпоинте** — `@PreAuthorize` (`auth-patterns/every-endpoint-has-role-check`):

   - Прямая проверка роли: `@PreAuthorize("hasRole('customer')")`.
   - Проверка владельца через бин: `@PreAuthorize("@access.canViewOrder(#id, authentication)")`.

8. **Audit log для admin** (`auth-patterns/admin-commands-write-audit-log`):

   - Таблица `<bc>_audit_log` (шаблон — `auth-patterns/references/java/implementation.md`, раздел `admin-commands-write-audit-log`).
   - Аспект `@Around("@within(InboundAdapter) && execution(* *(..))")`, который проверяет роль `admin` и пишет строку. Или явный вызов в Handler.

9. **Идемпотентность** (`auth-patterns/money-commands-need-idempotency-key`) — для денежных команд:

   - Заголовок `Idempotency-Key` в OpenAPI обязательный.
   - Таблица `idempotency_keys` (шаблон).
   - Handler сначала проверяет ключ, потом исполняет команду; в той же транзакции пишет ключ.

10. **PII / секреты** (`auth-patterns/no-pii-in-logs-and-events`..`auth-patterns/error-response-hides-cause`):

    - Logback-фильтр на маскирование email / phone / cardNumber (генерируй стандартный `MaskingPatternLogger`).
    - `RestControllerAdvice`: переписывай `cause.getMessage()` на статический title по коду ошибки (никогда не пробрасывай).
    - `application-prod.yml` — только плейсхолдеры (`${KAFKA_PASSWORD}`); секреты — внешние.

11. **Вывод** — по общему правилу: размер ответа равен размеру вопроса; решения и затронутые файлы — всегда, полные файлы — только когда просят сгенерировать; ревью — по запросу, не автоматически.

$ARGUMENTS
