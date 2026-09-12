---
name: ucp-node-auth-design
lang: node
description: Зашаблонить auth NestJS-сервиса (Node) по UCP — JwtStrategy на passport-jwt + jwks-rsa (JWKS-кеш), RBAC через @Roles + RolesGuard, ABAC по владению в Handler, audit-interceptor admin-команд, секреты в валидируемом конфиге.
when_to_use: Триггеры — «настрой auth на NestJS», «JWT-валидация», «RBAC/ABAC через guards». При старте сервиса или добавлении auth.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# Auth Patterns — проектирование (Node / NestJS + passport-jwt/jwks-rsa)

Ты проектируешь auth по **контракту** `backend/auth-patterns/spec.md` (`AUTH-*`) и **Node-реализации** `backend/auth-patterns/references/node/implementation.md`.

## Инструкции

1. **Прочитай** требования `node-style/*`. Коды в обосновании, не в коде. Связанные: `backend/usecase-pattern/node/...` (ABAC в Handler), `backend/error-handling/node/...` (401/403-mapping, не светить cause), `observability` (`auth-patterns/no-pii-in-logs-and-events` PII, pino `redact`), `backend/node/nest-bootstrap/...` (`nest-bootstrap/config-validated-at-startup` секреты/конфиг).

2. **Где** (`AUTH-1..3`): edge — аутентификация (валидация JWT); BFF — RBAC по роли; domain-handler — ABAC по ресурсу.

3. **JWT validation** (`AUTH-4..6`): `JwtStrategy` (`@nestjs/passport` + `passport-jwt`) с `secretOrKeyProvider: passportJwtSecret(...)` из `jwks-rsa` (`cache: true`, ~5 мин), проверка подписи/`exp`/`iss`/`aud` (`algorithms`, `audience`, `issuer`); невалидный → **401** (`JwtAuthGuard`). Не самописный `jwt.decode`.

4. **RBAC** (`AUTH-7..9`): роли из claim (`realm_access.roles`/`scope`) → `Principal.roles` в `JwtStrategy.validate`; глобальные `APP_GUARD`: `JwtAuthGuard` (401), затем `RolesGuard` (403); на каждом endpoint — `@Roles(...)` или явный `@Public()`; роли `customer`/`seller`/`admin`/`system`.

5. **ABAC** (`AUTH-10..12`): сравнение `aggregate.ownerId` с `principal.sub` в Handler/`@Injectable() AccessPolicy` с `ForbiddenError` (→ 403 на edge); admin обходит + audit.

6. **S2S/Audit/PII/Secrets** (`AUTH-13..18`): mTLS/Client Credentials для inter-service (outbound axios/undici не анонимны); audit-`NestInterceptor` на admin-эндпоинтах → `*_audit_log`; PII не в логах (pino `redact`)/exception/событиях; секреты через env/Vault + валидируемый конфиг (`nest-bootstrap/config-validated-at-startup`), не в git; filter не выводит `String(cause)`.

7. **Idempotency/Tokens** (`AUTH-19..21`): money-команды требуют `Idempotency-Key` (guard/interceptor + таблица идемпотентности); SPA — HttpOnly+Secure+SameSite cookie; refresh с rotation. Самопроверка (§10) + предложи `ucp-node-auth-review`.

## Антипаттерны, которые НЕ генерировать

- Самописный `jwt.decode` без проверки подписи/claims (`auth-patterns/token-validated-by-library`); ручная распаковка JWK без `jwks-rsa`-кеша (`auth-patterns/token-validated-by-library`); 403 вместо 401 на невалидный токен (`auth-patterns/401-not-403`).
- Endpoint без `@Roles` и без явного `@Public()` (`auth-patterns/every-endpoint-has-role-check`); ABAC размазан по контроллерам (`auth-patterns/ownership-checked-in-domain`); admin без audit (`auth-patterns/admin-bypass-is-audited`/`auth-patterns/admin-commands-write-audit-log`).
- Анонимный inter-service вызов (`auth-patterns/service-to-service-authenticated`); PII в логах/exception/событиях (`auth-patterns/no-pii-in-logs-and-events`); секреты в git/`.env`-в-репо (`auth-patterns/no-secrets-in-repository`); `String(cause)` в `detail` (`auth-patterns/error-response-hides-cause`).
- Money-команда без `Idempotency-Key` (`auth-patterns/money-commands-need-idempotency-key`); токен в `localStorage` (`auth-patterns/token-in-httponly-cookie`); refresh без rotation (`auth-patterns/refresh-token-rotation`).

После работы скилла — обязательно `ucp-node-auth-review`.

$ARGUMENTS
