---
name: ucp-py-auth-design
lang: python
description: Зашаблонить auth FastAPI-сервиса (Python) по UCP — JWT-валидация через зависимость (PyJWT/authlib + JWKS-кеш), RBAC через Depends(require_roles), ABAC по владению в Handler, audit-log admin-команд, секреты в pydantic-settings.
when_to_use: Триггеры — «настрой auth на FastAPI», «JWT-валидация», «RBAC/ABAC на питоне». При старте сервиса или добавлении auth.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Auth Patterns — проектирование (Python / FastAPI + PyJWT/authlib)

Ты проектируешь auth по **контракту** `backend/auth-patterns/spec.md` (`AUTH-*`) и **Python-реализации** `backend/auth-patterns/references/python/implementation.md`.

## Инструкции

1. **Прочитай** требования `python-style/*`. Коды в обосновании, не в коде. Связанные: `backend/usecase-pattern/python/...` (ABAC в Handler), `backend/error-handling/python/...` (401/403-mapping, не светить cause), `observability` (`auth-patterns/no-pii-in-logs-and-events` PII), `python-bootstrap` (секреты/настройки).

2. **Где** (`AUTH-1..3`): edge — аутентификация (валидация JWT); BFF — RBAC по роли; domain-handler — ABAC по ресурсу.

3. **JWT validation** (`AUTH-4..6`): общая зависимость `principal()` на `PyJWT`+`PyJWKClient` (или authlib), проверка подписи/`exp`/`iss`/`aud`, кеш JWKS ~5м; невалидный → **401**. Не самописный парсинг.

4. **RBAC** (`AUTH-7..9`): роли из claim (`realm_access.roles`/`scope`) → `Principal.roles`; `Depends(require_roles(...))` на каждом endpoint; роли `customer`/`seller`/`admin`/`system`.

5. **ABAC** (`AUTH-10..12`): сравнение `aggregate.owner_id` с `principal.sub` в Handler/`AccessPolicy` с `403`; admin обходит + audit.

6. **S2S/Audit/PII/Secrets** (`AUTH-13..18`): mTLS/Client Credentials для inter-service; audit-log admin-команд (`*_audit_log`); PII не в логах/exception/событиях; секреты через `pydantic-settings` (env/Vault), не в git; handler не выводит `str(cause)`.

7. **Idempotency/Tokens** (`AUTH-19..21`): money-команды требуют `Idempotency-Key`; SPA — HttpOnly+Secure+SameSite cookie; refresh с rotation. Самопроверка (§10) + предложи `ucp-py-auth-review`.

## Антипаттерны, которые НЕ генерировать

- Самописный `jwt.decode` без проверки подписи/claims (`auth-patterns/token-validated-by-library`); ручная распаковка ключей без JWKS-кеша (`auth-patterns/token-validated-by-library`); 403 вместо 401 на невалидный токен (`auth-patterns/401-not-403`).
- Endpoint без `require_roles` (`auth-patterns/every-endpoint-has-role-check`); ABAC размазан по роутерам (`auth-patterns/ownership-checked-in-domain`); admin без audit (`auth-patterns/admin-bypass-is-audited`/`auth-patterns/admin-commands-write-audit-log`).
- Анонимный inter-service вызов (`auth-patterns/service-to-service-authenticated`); PII в логах/exception/событиях (`auth-patterns/no-pii-in-logs-and-events`); секреты в git/yaml-в-репо (`auth-patterns/no-secrets-in-repository`); `str(cause)` в `detail` (`auth-patterns/error-response-hides-cause`).
- Money-команда без `Idempotency-Key` (`auth-patterns/money-commands-need-idempotency-key`); токен в `localStorage` (`auth-patterns/token-in-httponly-cookie`); refresh без rotation (`auth-patterns/refresh-token-rotation`).

После работы скилла — обязательно `ucp-py-auth-review`.

$ARGUMENTS
