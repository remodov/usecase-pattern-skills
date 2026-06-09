---
name: ucp-py-auth-design
lang: python
description: Зашаблонить auth FastAPI-сервиса (Python) по UCP (коды AUTH-*) — JWT-валидация через зависимость (PyJWT/authlib + JWKS-кеш), RBAC через Depends(require_roles), ABAC по владению в Handler, audit-log admin-команд, секреты в pydantic-settings.
when_to_use: Триггеры — «настрой auth на FastAPI», «JWT-валидация», «RBAC/ABAC на питоне». При старте сервиса или добавлении auth.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Auth Patterns — проектирование (Python / FastAPI + PyJWT/authlib)

Ты проектируешь auth по **контракту** `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-*`) и **Python-реализации** `backend/auth-patterns/python/auth-patterns-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Python-style-guide. Коды в обосновании, не в коде. Связанные: `backend/usecase-pattern/python/...` (ABAC в Handler), `backend/error-handling/python/...` (401/403-mapping, не светить cause), `observability` (`AUTH-16` PII), `python-bootstrap` (секреты/настройки).

2. **Где** (`AUTH-1..3`): edge — аутентификация (валидация JWT); BFF — RBAC по роли; domain-handler — ABAC по ресурсу.

3. **JWT validation** (`AUTH-4..6`): общая зависимость `principal()` на `PyJWT`+`PyJWKClient` (или authlib), проверка подписи/`exp`/`iss`/`aud`, кеш JWKS ~5м; невалидный → **401**. Не самописный парсинг.

4. **RBAC** (`AUTH-7..9`): роли из claim (`realm_access.roles`/`scope`) → `Principal.roles`; `Depends(require_roles(...))` на каждом endpoint; роли `customer`/`seller`/`admin`/`system`.

5. **ABAC** (`AUTH-10..12`): сравнение `aggregate.owner_id` с `principal.sub` в Handler/`AccessPolicy` с `403`; admin обходит + audit.

6. **S2S/Audit/PII/Secrets** (`AUTH-13..18`): mTLS/Client Credentials для inter-service; audit-log admin-команд (`*_audit_log`); PII не в логах/exception/событиях; секреты через `pydantic-settings` (env/Vault), не в git; handler не выводит `str(cause)`.

7. **Idempotency/Tokens** (`AUTH-19..21`): money-команды требуют `Idempotency-Key`; SPA — HttpOnly+Secure+SameSite cookie; refresh с rotation. Самопроверка (§10) + предложи `ucp-py-auth-review`.

## Антипаттерны, которые НЕ генерировать

- Самописный `jwt.decode` без проверки подписи/claims (`AUTH-4`); ручная распаковка ключей без JWKS-кеша (`AUTH-5`); 403 вместо 401 на невалидный токен (`AUTH-6`).
- Endpoint без `require_roles` (`AUTH-9`); ABAC размазан по роутерам (`AUTH-11`); admin без audit (`AUTH-12`/`AUTH-15`).
- Анонимный inter-service вызов (`AUTH-14`); PII в логах/exception/событиях (`AUTH-16`); секреты в git/yaml-в-репо (`AUTH-17`); `str(cause)` в `detail` (`AUTH-18`).
- Money-команда без `Idempotency-Key` (`AUTH-19`); токен в `localStorage` (`AUTH-20`); refresh без rotation (`AUTH-21`).

После работы скилла — обязательно `ucp-py-auth-review`.

$ARGUMENTS
