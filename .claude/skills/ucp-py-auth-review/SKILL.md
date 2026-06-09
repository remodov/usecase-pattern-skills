---
name: ucp-py-auth-review
lang: python
description: Ревью аутентификации/авторизации FastAPI-сервиса (Python) по UCP (коды AUTH-*) — JWT через библиотеку+JWKS-кеш, RBAC через Depends(require_roles), ABAC в Handler/AccessPolicy, s2s mTLS, audit-log, PII и секреты, idempotency-key для money.
when_to_use: Изменения в security-зависимостях, роутерах, Handler-ABAC, AccessPolicy, конфигах секретов, audit-логике.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Auth Patterns (Python / FastAPI + PyJWT/authlib)

Ты ревьюишь auth на соответствие **контракту** `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-*`) и **Python-реализации** `backend/auth-patterns/python/auth-patterns-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/auth-patterns/auth-patterns-rules.md`** + **`backend/auth-patterns/python/auth-patterns-style-guide.md`**.
- Парные: `backend/error-handling/python/...` (401/403, cause), `observability` (`AUTH-16` PII), `distributed-patterns` (`AUTH-19`/`R-DIST-IDEM`).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй коды (`AUTH-9`, `AUTH-16`), не префикс.

2. **Скоп.** Security-зависимости (`security.py`/`principal`/`require_roles`), роутеры, Handler-ABAC, `AccessPolicy`, конфиги секретов (`settings`), audit-логика, outbound-клиенты (s2s); `git diff`.

3. **Прогон.**
   - **Где (`AUTH-1..3`):** аутентификация на edge, RBAC на BFF, ABAC в domain-handler (не на gateway).
   - **JWT (`AUTH-4..6`):** валидация через библиотеку+JWKS-кеш, не самописный `jwt.decode` без подписи/claims (`AUTH-4`); ручная распаковка ключей (`AUTH-5`); 403 вместо 401 на невалидный токен → нарушение `AUTH-6`.
   - **RBAC (`AUTH-7..9`):** роли из claim в `Principal`; `Depends(require_roles)` на **каждом** endpoint — без проверки → критично (`AUTH-9`); роли из разрешённого набора (`AUTH-8`).
   - **ABAC (`AUTH-10..12`):** сравнение владельца с `principal.sub` в Handler/`AccessPolicy` (размазан по роутерам → `AUTH-11`); admin обходит + audit (`AUTH-12`).
   - **S2S (`AUTH-13..14`):** mTLS/Client Credentials; анонимный inter-service вызов → критично (`AUTH-14`).
   - **Audit (`AUTH-15`):** admin state-changing команды пишут `*_audit_log`.
   - **PII/Secrets (`AUTH-16..18`):** PII в логах/exception/событиях → критично (`AUTH-16`); секреты в git/yaml-в-репо → критично (`AUTH-17`); `str(cause)` в `detail` (`AUTH-18`).
   - **Idempotency/Tokens (`AUTH-19..21`):** money-команда без `Idempotency-Key` (`AUTH-19`); токен в `localStorage` (`AUTH-20`); refresh без rotation (`AUTH-21`).

4. **Cross-check:** 401/403-mapping и не-светить-cause — `ucp-py-error-handling-review`; PII в логах — `ucp-py-observability-review`; idempotency-таблица — `ucp-py-distributed-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — endpoint без проверки роли (`AUTH-9`), самописная JWT-валидация без подписи/claims (`AUTH-4`), анонимный s2s (`AUTH-14`), PII в логах/событиях (`AUTH-16`), секреты в git (`AUTH-17`), money без `Idempotency-Key` (`AUTH-19`), токен в `localStorage` (`AUTH-20`).
   - **Предупреждение** — 403 вместо 401 (`AUTH-6`), ABAC размазан по роутерам (`AUTH-11`), admin без audit (`AUTH-12`/`AUTH-15`), `str(cause)` в `detail` (`AUTH-18`), refresh без rotation (`AUTH-21`).
   - **Замечание** — JWKS без явного кеша (`AUTH-5`), роль вне разрешённого набора (`AUTH-8`).

## Что не входит

- 401/403-mapping/ProblemDetails — `ucp-py-error-handling-review`. PII в логах/спанах — `ucp-py-observability-review`.
- SAST/CVE/контейнер/криптография — `ucp-py-security-review`. Idempotency-таблица — `ucp-py-distributed-review`.

$ARGUMENTS
