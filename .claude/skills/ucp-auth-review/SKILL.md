---
name: ucp-auth-review
description: Проверить Spring Boot-сервис на соответствие правилам аутентификации/авторизации — валидация JWT на границе, RBAC на BFF, ABAC по владельцу ресурса в domain-handler-ах, mTLS или Client Credentials для сервис-к-сервису, audit log для admin-операций, PII-гигиена, идемпотентность для money-операций. Применяется при разборе security-конфигов, контроллеров, обработчиков или PR, затрагивающих auth-флоу.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(./gradlew*) Bash(mvn*) Agent
---

# Ревью паттернов аутентификации/авторизации

Ты ревьюишь Spring Boot-код на соответствие командному auth-patterns style guide. Скилл намеренно узкий — он покрывает то, что диктует методология, не весь ландшафт OWASP / appsec.

## Инструкции

1. **Прочитай style guide** из `.claude/docs/auth-patterns-style-guide.md`. Цитируй коды (`AUTH-7`, `AUTH-15`) в замечаниях.

2. **Определи объект ревью.** Скоп по умолчанию:
   - `**/SecurityConfig*.java` и любая `@Configuration`, общающаяся со Spring Security или `OAuth2ResourceServer`.
   - REST-контроллеры (`@RestController`) — проверка `@PreAuthorize` на каждом эндпоинте.
   - UseCase-handler-ы — проверка ABAC по владельцу.
   - Исходящие HTTP-клиенты (`adapter-out-*`) — проверка mTLS / Bearer.
   - Конфигурации логирования и обработчики исключений — проверка утечки PII.
   - `application*.yml` — проверка секретов, JWK-URI.

   Если пользователь назвал файлы — ограничь скоп этими файлами. Иначе используй `git diff` (working tree, staged, last commit).

3. **Прогон по группам правил:**

   - **§1 Где живут проверки (`AUTH-1`..`AUTH-3`):** делает ли gateway валидацию JWT? Делает ли BFF RBAC? Делает ли домен ABAC? Не тот слой = критическое замечание.
   - **§2 JWT (`AUTH-4`..`AUTH-6`):** используется `oauth2ResourceServer().jwt()` (не кастомный фильтр); JWK-URL сконфигурирован; различие 401 vs 403 корректно.
   - **§3 RBAC (`AUTH-7`..`AUTH-9`):** `JwtAuthenticationConverter` с префиксом `ROLE_`; разрешённые роли только `customer` / `seller` / `admin` / `system`; **на каждом REST-эндпоинте есть `@PreAuthorize`**.
   - **§4 ABAC (`AUTH-10`..`AUTH-12`):** если у эндпоинта в пути id доменного агрегата, проверка владельца присутствует (в SpEL `@PreAuthorize`, в `@Component("access")`-бине или в handler-е); admin-override логируется.
   - **§5 Сервис-к-сервису (`AUTH-13`..`AUTH-14`):** исходящие клиенты в `adapter-out-*` имеют конфиг mTLS или интерцептор Bearer-токена.
   - **§6 Аудит (`AUTH-15`):** каждая команда от `admin` пишет в таблицу `<bc>_audit_log`.
   - **§7 PII / секреты (`AUTH-16`..`AUTH-18`):**
     - искать `logger.info(...)`, `log.debug(...)` на поля типа `email`, `phone`, `address`, `password`, `token`, `secret`;
     - проверить `OrderExceptionHandler` (или эквивалент) — не утекает ли `cause.getMessage()` в `ProblemDetails.detail`?
     - искать в `application*.yml` хардкод секретов / паролей.
   - **§8 Идемпотентность (`AUTH-19`):** money-эндпоинты декларируют заголовок `Idempotency-Key` в OpenAPI и проверяют его в handler-е.
   - **§9 Клиентская сторона (`AUTH-20`..`AUTH-21`):** для BFF — куки HttpOnly + Secure + SameSite; rotation refresh-токена; никакого `localStorage` в возвращаемых JS-подсказках.

4. **Замечания** оформляй в стандартном формате:

   ```
   <ПутьФайла>:<СтрокаНомер>  [<КодПравила>]  <Серьёзность>
     Проблема: <однострочное описание>
     Почему: <краткая цитата правила>
     Как исправить: <конкретное предложение + сниппет кода>
   ```

   Серьёзности:
   - **Критично** — эндпоинт без `@PreAuthorize`, ABAC отсутствует на ресурс-связанной операции, кастомный JWT-фильтр, секреты в открытом виде в репо, PII в `ProblemDetails.detail`.
   - **Предупреждение** — слабая привязка правил (`hasAuthority` где должно быть `hasRole`), audit log отсутствует на admin-команде, refresh-token без rotation.
   - **Замечание** — улучшения: переименовать роль, вынести ABAC в `@Component("access")`, добавить `@AuditLog`-аспект.

5. **Заверши резюме** — счётчики по серьёзности + вердикт.

6. **Код не модифицируй** — только сообщай.

$ARGUMENTS
