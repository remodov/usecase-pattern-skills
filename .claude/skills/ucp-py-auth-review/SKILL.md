---
name: ucp-py-auth-review
lang: python
description: Ревью аутентификации/авторизации FastAPI-сервиса (Python) по UCP — JWT через библиотеку+JWKS-кеш, RBAC через Depends(require_roles), ABAC в Handler/AccessPolicy, s2s mTLS, audit-log, PII и секреты, idempotency-key для money.
when_to_use: Изменения в security-зависимостях, роутерах, Handler-ABAC, AccessPolicy, конфигах секретов, audit-логике.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Auth Patterns (Python / FastAPI + PyJWT/authlib)

Ты ревьюишь auth на соответствие **контракту** `backend/auth-patterns/spec.md` (`AUTH-*`) и **Python-реализации** `backend/auth-patterns/references/python/implementation.md`.

## Зависимости

- **`.claude/docs/backend/auth-patterns/spec.md`** + **`backend/auth-patterns/references/python/implementation.md`**.
- Парные: `backend/error-handling/python/...` (401/403, cause), `observability` (`auth-patterns/no-pii-in-logs-and-events` PII), `distributed-patterns` (`auth-patterns/money-commands-need-idempotency-key`/`R-DIST-IDEM`).

## Инструкции

1. **Прочти** требования `python-style/*`. Цитируй коды (`auth-patterns/every-endpoint-has-role-check`, `auth-patterns/no-pii-in-logs-and-events`), не префикс.

2. **Скоп.** Security-зависимости (`security.py`/`principal`/`require_roles`), роутеры, Handler-ABAC, `AccessPolicy`, конфиги секретов (`settings`), audit-логика, outbound-клиенты (s2s); `git diff`.

3. **Прогон.**
   - **Где (`AUTH-1..3`):** аутентификация на edge, RBAC на BFF, ABAC в domain-handler (не на gateway).
   - **JWT (`AUTH-4..6`):** валидация через библиотеку+JWKS-кеш, не самописный `jwt.decode` без подписи/claims (`auth-patterns/token-validated-by-library`); ручная распаковка ключей (`auth-patterns/token-validated-by-library`); 403 вместо 401 на невалидный токен → нарушение `auth-patterns/401-not-403`.
   - **RBAC (`AUTH-7..9`):** роли из claim в `Principal`; `Depends(require_roles)` на **каждом** endpoint — без проверки → критично (`auth-patterns/every-endpoint-has-role-check`); роли из разрешённого набора (`auth-patterns/roles-from-token-claims`).
   - **ABAC (`AUTH-10..12`):** сравнение владельца с `principal.sub` в Handler/`AccessPolicy` (размазан по роутерам → `auth-patterns/ownership-checked-in-domain`); admin обходит + audit (`auth-patterns/admin-bypass-is-audited`).
   - **S2S (`AUTH-13..14`):** mTLS/Client Credentials; анонимный inter-service вызов → критично (`auth-patterns/service-to-service-authenticated`).
   - **Audit (`auth-patterns/admin-commands-write-audit-log`):** admin state-changing команды пишут `*_audit_log`.
   - **PII/Secrets (`AUTH-16..18`):** PII в логах/exception/событиях → критично (`auth-patterns/no-pii-in-logs-and-events`); секреты в git/yaml-в-репо → критично (`auth-patterns/no-secrets-in-repository`); `str(cause)` в `detail` (`auth-patterns/error-response-hides-cause`).
   - **Idempotency/Tokens (`AUTH-19..21`):** money-команда без `Idempotency-Key` (`auth-patterns/money-commands-need-idempotency-key`); токен в `localStorage` (`auth-patterns/token-in-httponly-cookie`); refresh без rotation (`auth-patterns/refresh-token-rotation`).

4. **Cross-check:** 401/403-mapping и не-светить-cause — `ucp-py-error-handling-review`; PII в логах — `ucp-py-observability-review`; idempotency-таблица — `ucp-py-distributed-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — endpoint без проверки роли (`auth-patterns/every-endpoint-has-role-check`), самописная JWT-валидация без подписи/claims (`auth-patterns/token-validated-by-library`), анонимный s2s (`auth-patterns/service-to-service-authenticated`), PII в логах/событиях (`auth-patterns/no-pii-in-logs-and-events`), секреты в git (`auth-patterns/no-secrets-in-repository`), money без `Idempotency-Key` (`auth-patterns/money-commands-need-idempotency-key`), токен в `localStorage` (`auth-patterns/token-in-httponly-cookie`).
   - **Предупреждение** — 403 вместо 401 (`auth-patterns/401-not-403`), ABAC размазан по роутерам (`auth-patterns/ownership-checked-in-domain`), admin без audit (`auth-patterns/admin-bypass-is-audited`/`auth-patterns/admin-commands-write-audit-log`), `str(cause)` в `detail` (`auth-patterns/error-response-hides-cause`), refresh без rotation (`auth-patterns/refresh-token-rotation`).
   - **Замечание** — JWKS без явного кеша (`auth-patterns/token-validated-by-library`), роль вне разрешённого набора (`auth-patterns/roles-from-token-claims`).

## Что не входит

- 401/403-mapping/ProblemDetails — `ucp-py-error-handling-review`. PII в логах/спанах — `ucp-py-observability-review`.
- SAST/CVE/контейнер/криптография — `ucp-py-security-review`. Idempotency-таблица — `ucp-py-distributed-review`.

$ARGUMENTS
