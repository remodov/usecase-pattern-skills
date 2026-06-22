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

`PyJWKClient` кеширует JWK Set (`R-AUTH-5`), повторно не ходит в IdP на каждый запрос; невалидная подпись /
просроченный `exp` → **401** (`AUTH-6`). RBAC — `Depends(require_roles(...))` на каждом endpoint (`AUTH-9`):

```python
# adapters/in/http/order_router.py — RBAC объявляется зависимостью (AUTH-9), не вручную внутри хендлера
@router.post("/v1/orders", status_code=201, responses=get_error_responses(401, 403))  # 401 невалид JWT, 403 нет роли
async def create_order(req: CreateOrderRequest,
                       principal: Principal = Depends(require_roles("customer", "admin")),  # AUTH-7/AUTH-9
                       dispatcher: Dispatcher = Depends(get_dispatcher)) -> CreateOrderResponse:
    order_id = await dispatcher.dispatch(
        CreateOrder(customer_id=principal.sub, items=req.to_domain_items()))   # owner = principal.sub, не из Request
    return CreateOrderResponse(id_=str(order_id))           # PY-2.X2: поле без затенения builtin id
```

## 3. RBAC (`AUTH-7..9`)

`AUTH-7` — роли из claim (`realm_access.roles` Keycloak / `scope`) маппятся в `Principal.roles` в зависимости.
`AUTH-8` — разрешённые роли: `customer`/`seller`/`admin`/`system`. `AUTH-9` — на каждом endpoint —
`Depends(require_roles(...))`; endpoint без проверки роли — критично.

## 4. ABAC (`AUTH-10..12`)

`AUTH-10` — команда/запрос с агрегатом по id — ABAC по владению: сравнение `aggregate.owner_id` с `principal.sub` в
Handler с `403`/`ForbiddenError`. `AUTH-11` — ABAC-логика в выделенном компоненте (`AccessPolicy`)/Handler, не
размазана по роутерам. `AUTH-12` — `admin` обходит ABAC, но каждое действие — в audit log (`AUTH-15`).

ABAC в Python — **императивно в Handler**: грузим агрегат через репозиторий, сравниваем владельца с `principal.sub`,
бросаем `ForbiddenError` при несовпадении (это сознательный UCP-биндинг — не декоративный `@PreAuthorize`-аналог,
т.к. проверка владения требует загруженного агрегата). `principal` кладётся в UseCase как поле, не передаётся объект
запроса (`R-DSP-X2`). `admin` обходит проверку, но действие пишется в audit log (`AUTH-12`, `AUTH-15`):

```python
# core/order/usecases.py
@dataclass(frozen=True)
class CancelOrder:                                   # Command[None]
    order_id: OrderId
    principal_sub: str                               # владелец из токена, не из body (R-DSP-X2)
    principal_roles: frozenset[str]

# core/order/handlers.py — ABAC императивно, после load-aggregate (AUTH-10/AUTH-11)
class CancelOrderHandler:
    def __init__(self, session_factory, orders: OrderRepository, audit: AuditLogRepository,
                 clock: Clock) -> None:
        self._session_factory = session_factory
        self._orders = orders
        self._audit = audit
        self._clock = clock

    async def handle(self, cmd: CancelOrder) -> None:
        async with self._session_factory() as session, session.begin():
            order = await self._orders.by_id(session, cmd.order_id)         # доступ к БД — через репозиторий
            is_admin = "admin" in cmd.principal_roles
            if not is_admin and order.owner_id != cmd.principal_sub:        # ABAC по владению (AUTH-10)
                raise ForbiddenError("not the owner")                       # → 403, не 401 (AUTH-6)
            order.cancel(self._clock.now())
            await self._orders.save(session, order)
            if is_admin:                                                    # admin обходит ABAC, но пишет audit (AUTH-12)
                self._audit.add(session, actor_id=cmd.principal_sub, action="order.cancel",
                                aggregate_id=order.id.value, at=self._clock.now())  # AUTH-15
```

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

Секреты и параметры IdP — через `pydantic-settings` из env/Vault, не хардкодом и не в git (`AUTH-17`). `SecretStr`
не утекает в логи/repr. Exception-handler отдаёт фиксированное сообщение по коду, без `str(cause)` (`AUTH-18`):

```python
# app/settings.py
class AuthSettings(BaseSettings):
    jwks_uri: str                                    # из env, не хардкод (AUTH-17)
    issuer: str
    audience: str
    client_secret: SecretStr                         # SecretStr → не светится в repr/логах (AUTH-16)
    model_config = SettingsConfigDict(env_prefix="AUTH_", secrets_dir="/run/secrets")  # Vault/SealedSecrets

# adapters/in/http/error_handlers.py — фиксированное сообщение по коду, без str(cause) (AUTH-18)
@app.exception_handler(ForbiddenError)
async def _forbidden(_: Request, exc: ForbiddenError):
    return problem_response(status=403, code="FORBIDDEN", detail="access denied")  # не str(exc) — нет утечки PII/internals
```

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
