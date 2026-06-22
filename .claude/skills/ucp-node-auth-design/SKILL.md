---
name: ucp-node-auth-design
lang: node
description: Зашаблонить auth NestJS-сервиса (Node) по UCP (коды AUTH-*) — JwtStrategy на passport-jwt + jwks-rsa (JWKS-кеш), RBAC через @Roles + RolesGuard, ABAC по владению в Handler, audit-interceptor admin-команд, секреты в валидируемом конфиге.
when_to_use: Триггеры — «настрой auth на NestJS», «JWT-валидация», «RBAC/ABAC через guards». При старте сервиса или добавлении auth.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# Auth Patterns — проектирование (Node / NestJS + passport-jwt/jwks-rsa)

Ты проектируешь auth по **контракту** `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-*`) и **Node-реализации** `backend/auth-patterns/node/auth-patterns-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Node-style-guide. Коды в обосновании, не в коде. Связанные: `backend/usecase-pattern/node/...` (ABAC в Handler), `backend/error-handling/node/...` (401/403-mapping, не светить cause), `observability` (`AUTH-16` PII, pino `redact`), `backend/node/nest-bootstrap/...` (`NESTBOOT-4` секреты/конфиг).

2. **Где** (`AUTH-1..3`): edge — аутентификация (валидация JWT); BFF — RBAC по роли; domain-handler — ABAC по ресурсу.

3. **JWT validation** (`AUTH-4..6`): `JwtStrategy` (`@nestjs/passport` + `passport-jwt`) с `secretOrKeyProvider: passportJwtSecret(...)` из `jwks-rsa` (`cache: true`, ~5 мин), проверка подписи/`exp`/`iss`/`aud` (`algorithms`, `audience`, `issuer`); невалидный → **401** (`JwtAuthGuard`). Не самописный `jwt.decode`.

4. **RBAC** (`AUTH-7..9`): роли из claim (`realm_access.roles`/`scope`) → `Principal.roles` в `JwtStrategy.validate`; глобальные `APP_GUARD`: `JwtAuthGuard` (401), затем `RolesGuard` (403); на каждом endpoint — `@Roles(...)` или явный `@Public()`; роли `customer`/`seller`/`admin`/`system`.

5. **ABAC** (`AUTH-10..12`): сравнение `aggregate.ownerId` с `principal.sub` в Handler/`@Injectable() AccessPolicy` с `ForbiddenError` (→ 403 на edge); admin обходит + audit.

6. **S2S/Audit/PII/Secrets** (`AUTH-13..18`): mTLS/Client Credentials для inter-service (outbound axios/undici не анонимны); audit-`NestInterceptor` на admin-эндпоинтах → `*_audit_log`; PII не в логах (pino `redact`)/exception/событиях; секреты через env/Vault + валидируемый конфиг (`NESTBOOT-4`), не в git; filter не выводит `String(cause)`.

7. **Idempotency/Tokens** (`AUTH-19..21`): money-команды требуют `Idempotency-Key` (guard/interceptor + таблица идемпотентности); SPA — HttpOnly+Secure+SameSite cookie; refresh с rotation. Самопроверка (§10) + предложи `ucp-node-auth-review`.

## Антипаттерны, которые НЕ генерировать

- Самописный `jwt.decode` без проверки подписи/claims (`AUTH-4`); ручная распаковка JWK без `jwks-rsa`-кеша (`AUTH-5`); 403 вместо 401 на невалидный токен (`AUTH-6`).
- Endpoint без `@Roles` и без явного `@Public()` (`AUTH-9`); ABAC размазан по контроллерам (`AUTH-11`); admin без audit (`AUTH-12`/`AUTH-15`).
- Анонимный inter-service вызов (`AUTH-14`); PII в логах/exception/событиях (`AUTH-16`); секреты в git/`.env`-в-репо (`AUTH-17`); `String(cause)` в `detail` (`AUTH-18`).
- Money-команда без `Idempotency-Key` (`AUTH-19`); токен в `localStorage` (`AUTH-20`); refresh без rotation (`AUTH-21`).

После работы скилла — обязательно `ucp-node-auth-review`.

$ARGUMENTS
