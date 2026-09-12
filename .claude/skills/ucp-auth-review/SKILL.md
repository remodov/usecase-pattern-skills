---
name: ucp-auth-review
description: Ревью аутентификации/авторизации Spring Boot-сервиса (требования auth-patterns/*) — JWT на границе, RBAC на BFF, ABAC по владельцу в handler-ах, mTLS/Client Credentials, audit log, PII-гигиена, идемпотентность money-операций.
when_to_use: Ревью security-конфигов, контроллеров, handler-ов, application.yml или PR, затрагивающих auth-флоу.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(./gradlew*) Bash(mvn*)
---

# Ревью паттернов аутентификации/авторизации

Ты ревьюишь Spring Boot-код на соответствие требованиям `auth-patterns/*`. Скилл намеренно узкий — он покрывает то, что диктует методология, не весь ландшафт OWASP / appsec.

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/auth-patterns/spec.md` (полный текст с примерами кода — `backend/auth-patterns/references/java/implementation.md`, открывай точечно по разделу). Цитируй коды (`auth-patterns/roles-from-token-claims`, `auth-patterns/admin-commands-write-audit-log`) в замечаниях.

2. **Определи объект ревью.** Скоп по умолчанию:
   - `**/SecurityConfig*.java` и любая `@Configuration`, общающаяся со Spring Security или `OAuth2ResourceServer`.
   - REST-контроллеры (`@RestController`) — проверка `@PreAuthorize` на каждом эндпоинте.
   - UseCase-handler-ы — проверка ABAC по владельцу.
   - Исходящие HTTP-клиенты (`adapter-out-*`) — проверка mTLS / Bearer.
   - Конфигурации логирования и обработчики исключений — проверка утечки PII.
   - `application*.yml` — проверка секретов, JWK-URI.

   Если пользователь назвал файлы — ограничь скоп этими файлами. Иначе используй `git diff` (working tree, staged, last commit).

3. **Прогон по группам правил:**

   - **§1 Где живут проверки (`auth-patterns/checks-split-by-layer`..`auth-patterns/checks-split-by-layer`):** делает ли gateway валидацию JWT? Делает ли BFF RBAC? Делает ли домен ABAC? Не тот слой = критическое замечание.
   - **§2 JWT (`auth-patterns/token-validated-by-library`..`auth-patterns/401-not-403`):** используется `oauth2ResourceServer().jwt()` (не кастомный фильтр); JWK-URL сконфигурирован; различие 401 vs 403 корректно.
   - **§3 RBAC (`auth-patterns/roles-from-token-claims`..`auth-patterns/every-endpoint-has-role-check`):** `JwtAuthenticationConverter` с префиксом `ROLE_`; разрешённые роли только `customer` / `seller` / `admin` / `system`; **на каждом REST-эндпоинте есть `@PreAuthorize`**.
   - **§4 ABAC (`auth-patterns/ownership-checked-in-domain`..`auth-patterns/admin-bypass-is-audited`):** если у эндпоинта в пути id доменного агрегата, проверка владельца присутствует (в SpEL `@PreAuthorize`, в `@Component("access")`-бине или в handler-е); admin-override логируется.
   - **§5 Сервис-к-сервису (`auth-patterns/service-to-service-authenticated`..`auth-patterns/service-to-service-authenticated`):** исходящие клиенты в `adapter-out-*` имеют конфиг mTLS или интерцептор Bearer-токена.
   - **§6 Аудит (`auth-patterns/admin-commands-write-audit-log`):** каждая команда от `admin` пишет в таблицу `<bc>_audit_log`.
   - **§7 PII / секреты (`auth-patterns/no-pii-in-logs-and-events`..`auth-patterns/error-response-hides-cause`):**
     - искать `logger.info(...)`, `log.debug(...)` на поля типа `email`, `phone`, `address`, `password`, `token`, `secret`;
     - проверить `OrderExceptionHandler` (или эквивалент) — не утекает ли `cause.getMessage()` в `ProblemDetails.detail`?
     - искать в `application*.yml` хардкод секретов / паролей.
   - **§8 Идемпотентность (`auth-patterns/money-commands-need-idempotency-key`):** money-эндпоинты декларируют заголовок `Idempotency-Key` в OpenAPI и проверяют его в handler-е.
   - **§9 Клиентская сторона (`auth-patterns/token-in-httponly-cookie`..`auth-patterns/refresh-token-rotation`):** для BFF — куки HttpOnly + Secure + SameSite; rotation refresh-токена; никакого `localStorage` в возвращаемых JS-подсказках.

4. **Формат finding, локализация, серьёзность, резюме, запрет правок** — см. `.claude/docs/shared/review-format/spec.md` (правила `review-format/*`). Перед каждым finding обязательна Read-проверка строки (`review-format/*`), поле `Строка` в формате обязательно (`review-format/finding-carries-line-and-rule`).

5. **Доменные ориентиры для серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — эндпоинт без `@PreAuthorize`, ABAC отсутствует на ресурс-связанной операции, кастомный JWT-фильтр, секреты в открытом виде в репо, PII в `ProblemDetails.detail`.
   - **Предупреждение** — слабая привязка правил (`hasAuthority` где должно быть `hasRole`), audit log отсутствует на admin-команде, refresh-token без rotation.
   - **Замечание** — переименовать роль, вынести ABAC в `@Component("access")`, добавить `@AuditLog`-аспект.

$ARGUMENTS
