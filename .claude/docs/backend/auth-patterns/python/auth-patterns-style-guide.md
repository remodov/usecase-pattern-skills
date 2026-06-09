# Auth Patterns — Python Style Guide (FastAPI / PyJWT / authlib)

Реализация язык-нейтрального контракта `../auth-patterns-rules.md` (`AUTH-*`) на FastAPI. Коды общие с Java;
механизм: вместо Spring Security `@PreAuthorize`/`oauth2ResourceServer` — **FastAPI-зависимости** (`Depends`) +
библиотека валидации JWT (`PyJWT`/`authlib`/`joserfc`) с JWKS-клиентом. Без самописного парсинга подписи.

## 1. Где какая проверка (`AUTH-1..3`)

`AUTH-1` — edge/gateway: аутентификация (валидация JWT: подпись, `exp`, `iss`, `aud`) + rate limit; identity в
downstream. `AUTH-2` — BFF/application: грубая RBAC по роли — FastAPI-зависимость `Depends(require_roles("admin"))`.
`AUTH-3` — domain-handler: ABAC по ресурсу (`order.customer_id == principal.sub`), не на gateway (он не знает домен).

## 2. JWT validation (`AUTH-4..6`)

`AUTH-4` — JWT валидируется одной общей зависимостью на проверенной библиотеке (`PyJWT` + `PyJWKClient` / `authlib`
ResourceProtector / `joserfc`), не россыпью самописного `jwt.decode` без проверки подписи/claims. `AUTH-5` — JWK Set
тянется из IdP по `jwks_uri` с кешем (~5 мин, `PyJWKClient` кеширует; не распаковывать ключи руками). `AUTH-6` —
невалидная подпись/просроченный `exp` → **401**, не 403.

```python
# adapters/in/http/security.py
_jwks = PyJWKClient(settings.jwks_uri, cache_keys=True, lifespan=300)

async def principal(token: str = Depends(oauth2_scheme)) -> Principal:
    try:
        key = _jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"],
                            audience=settings.audience, issuer=settings.issuer)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="invalid token") from e
    return Principal(sub=claims["sub"], roles=_roles(claims))

def require_roles(*roles: str):
    async def dep(p: Principal = Depends(principal)) -> Principal:
        if not set(roles) & set(p.roles):
            raise HTTPException(status_code=403, detail="forbidden")
        return p
    return dep
```

## 3. RBAC (`AUTH-7..9`)

`AUTH-7` — роли из claim (`realm_access.roles` Keycloak / `scope`) маппятся в `Principal.roles` в зависимости.
`AUTH-8` — разрешённые роли: `customer`/`seller`/`admin`/`system`. `AUTH-9` — на каждом endpoint —
`Depends(require_roles(...))`; endpoint без проверки роли — критично.

## 4. ABAC (`AUTH-10..12`)

`AUTH-10` — команда/запрос с агрегатом по id — ABAC по владению: сравнение `aggregate.owner_id` с `principal.sub` в
Handler с `403`/`ForbiddenError`. `AUTH-11` — ABAC-логика в выделенном компоненте (`AccessPolicy`)/Handler, не
размазана по роутерам. `AUTH-12` — `admin` обходит ABAC, но каждое действие — в audit log (`AUTH-15`).

## 5. Service-to-service (`AUTH-13..14`)

`AUTH-13` — s2s: mTLS (Service Mesh) либо Client Credentials Flow (`grant_type=client_credentials`,
`scope=service:operation`). `AUTH-14` — outbound-клиенты в `adapters/out/*` не ходят без mTLS/`Bearer`; анонимный
inter-service трафик — критично.

## 6. Аудит admin-команд (`AUTH-15`)

`AUTH-15` — каждая state-changing команда от `admin` пишет строку в `*_audit_log` (`actor_id`, `occurred_at`,
`action`, `<aggregate>_id`, `metadata` JSONB) — через декоратор/зависимость или явный вызов в Handler.

## 7. PII и секреты (`AUTH-16..18`)

`AUTH-16` — PII (email/phone/ФИО/адрес) не в логах (даже DEBUG), не в `str(exc)`/`problem.detail`, не в Kafka-событиях
(только id, PII подгружает потребитель) — cross-ref `R-OBS-LOG-X1`. `AUTH-17` — секреты (client-secret, DB-пароли,
ключи) **не в git** — через env / Vault / SealedSecrets, читаются `pydantic-settings`. `AUTH-18` — exception-handler
не выводит `str(cause)` в `detail` — только заранее заданное сообщение по коду (cross-ref `R-ERR-MAP-*`).

## 8. Идемпотентность (`AUTH-19`)

`AUTH-19` — команда, меняющая деньги/резерв (`CreateOrder`, `ConfirmPayment`, `Refund`), требует `Idempotency-Key`;
повтор с тем же ключом → прежний результат, не дубль (cross-ref `R-DIST-IDEM-3`).

## 9. Хранение токенов на клиенте (`AUTH-20..21`)

`AUTH-20` — для SPA — HttpOnly + Secure + SameSite=Lax cookie (session-cookie у BFF или JWT-в-cookie), не
`localStorage`. `AUTH-21` — refresh-токены с rotation: при обновлении старый инвалидируется; повторное использование
старого RT → компрометация, инвалидируется вся цепочка.

## 10. Чеклист подключения к новому сервису (Python)

1. Edge валидирует JWT (подпись/exp/iss/aud) через библиотеку+JWKS-кеш; невалидный → 401.
2. Каждый endpoint — `Depends(require_roles(...))`; роли из claim в `Principal`.
3. ABAC по владению в Handler/AccessPolicy; admin-обход + audit.
4. s2s через mTLS/Client Credentials, не анонимно.
5. PII не в логах/exception/событиях; секреты не в git; handler не светит `str(cause)`.
6. Money-команды требуют `Idempotency-Key`; SPA — HttpOnly cookie, RT с rotation.
