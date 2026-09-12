# Auth Patterns — реализация на Node (NestJS / passport-jwt / jwks-rsa)

Реализация язык-нейтрального контракта `../spec.md` (`AUTH-*`) на NestJS. Коды общие с Java и
Python; механизм: вместо Spring Security `@PreAuthorize`/`oauth2ResourceServer` — **Guards** NestJS
(`@nestjs/passport` + `passport-jwt`) с JWKS-клиентом `jwks-rsa`. Без самописного парсинга подписи.

## 1. Где какая проверка (`AUTH-1..3`)

`auth-patterns/checks-split-by-layer` — edge/gateway: аутентификация (валидация JWT: подпись, `exp`, `iss`, `aud`) + rate limit; identity в
downstream. `auth-patterns/checks-split-by-layer` — BFF/application: грубая RBAC по роли — `@Roles('admin')` + `RolesGuard`.
`auth-patterns/checks-split-by-layer` — domain-handler: ABAC по ресурсу (`order.customerId === principal.sub`), не на gateway (он не знает домен).

## 2. JWT validation (`AUTH-4..6`)

`auth-patterns/token-validated-by-library` — JWT валидируется одной стратегией на проверенных библиотеках (`passport-jwt` + `jwks-rsa`), не
самописным `jwt.decode` без проверки подписи/claims. `auth-patterns/token-validated-by-library` — JWK Set тянется из IdP по `jwksUri` с кешем
(~5 мин — `cache: true` у `jwks-rsa`; не распаковывать ключи руками). `auth-patterns/401-not-403` — невалидная
подпись/просроченный `exp` → **401** (`JwtAuthGuard` кидает `UnauthorizedException`), не 403.

```ts
// adapters/in/http/security/jwt.strategy.ts
@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(config: AppConfig) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      algorithms: ['RS256'],
      audience: config.auth.audience,
      issuer: config.auth.issuer,
      secretOrKeyProvider: passportJwtSecret({          // jwks-rsa
        jwksUri: config.auth.jwksUri,
        cache: true, cacheMaxAge: 300_000,              // AUTH-5
        rateLimit: true,
      }),
    });
  }
  validate(claims: JwtClaims): Principal {              // claims уже проверены
    return { sub: claims.sub, roles: extractRoles(claims) };
  }
}

export const Roles = Reflector.createDecorator<string[]>();

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}
  canActivate(ctx: ExecutionContext): boolean {
    const required = this.reflector.get(Roles, ctx.getHandler());
    const { user } = ctx.switchToHttp().getRequest<{ user: Principal }>();
    if (!required?.some((r) => user.roles.includes(r))) throw new ForbiddenException();
    return true;                                        // 403 = аутентифицирован, но прав нет
  }
}
// app.module.ts: APP_GUARD → JwtAuthGuard (401), затем RolesGuard (403);
// публичные эндпоинты — явный @Public()-декоратор, не отсутствие guard'а
```

## 3. RBAC (`AUTH-7..9`)

`auth-patterns/roles-from-token-claims` — роли из claim (`realm_access.roles` Keycloak / `scope`) маппятся в `Principal.roles` в
`JwtStrategy.validate`. `auth-patterns/roles-from-token-claims` — разрешённые роли: `customer`/`seller`/`admin`/`system`. `auth-patterns/every-endpoint-has-role-check` — на каждом
endpoint — `@Roles(...)`; endpoint без проверки роли (и без явного `@Public()`) — критично.

## 4. ABAC (`AUTH-10..12`)

`auth-patterns/ownership-checked-in-domain` — команда/запрос с агрегатом по id — ABAC по владению: сравнение `aggregate.ownerId` с
`principal.sub` в Handler с `ForbiddenError` (→ 403 на edge). `auth-patterns/ownership-checked-in-domain` — ABAC-логика в выделенном
`@Injectable() AccessPolicy` или Handler, не размазана по контроллерам. `auth-patterns/admin-bypass-is-audited` — `admin` обходит ABAC,
но каждое действие — в audit log (`auth-patterns/admin-commands-write-audit-log`).

```ts
// core/order/handlers/cancel-order.handler.ts
async execute(cmd: CancelOrder, principal: Principal): Promise<void> {
  const order = await this.orders.byId(cmd.orderId);
  if (!principal.roles.includes('admin') && order.customerId !== principal.sub) {
    throw new ForbiddenError(cmd.orderId);              // AUTH-10
  }
  ...
}
```

## 5. Service-to-service (`AUTH-13..14`)

`auth-patterns/service-to-service-authenticated` — s2s: mTLS (Service Mesh) либо Client Credentials Flow (`grant_type=client_credentials`,
`scope=service:operation`; токен получает и кеширует outbound-клиент). `auth-patterns/service-to-service-authenticated` — клиенты в `adapters/out/*`
(axios/undici) не ходят без mTLS/`Bearer`; анонимный inter-service трафик — критично.

## 6. Аудит admin-команд (`auth-patterns/admin-commands-write-audit-log`)

`auth-patterns/admin-commands-write-audit-log` — каждая state-changing команда от `admin` пишет строку в `*_audit_log` (`actor_id`, `occurred_at`,
`action`, `<aggregate>_id`, `metadata` JSONB) — через audit-`NestInterceptor` на admin-эндпоинтах или явный
вызов в Handler:

```ts
intercept(ctx: ExecutionContext, next: CallHandler): Observable<unknown> {
  const { user } = ctx.switchToHttp().getRequest<{ user: Principal }>();
  return next.handle().pipe(tap(() =>
    this.audit.log({ actorId: user.sub, action: ctx.getHandler().name,
                     occurredAt: this.clock.now(), metadata: auditMeta(ctx) })));
}
```

## 7. PII и секреты (`AUTH-16..18`)

`auth-patterns/no-pii-in-logs-and-events` — PII (email/phone/ФИО/адрес) не в логах (nestjs-pino `redact`-paths, даже DEBUG), не в
`err.message`/`problem.detail`, не в Kafka-событиях (только id, PII подгружает потребитель). `auth-patterns/no-secrets-in-repository` —
секреты (client-secret, DB-пароли, ключи) **не в git** — через env / Vault / SealedSecrets, читаются
валидируемым конфигом (`nest-bootstrap/config-validated-at-startup`, `security/no-secret-values-in-config`). `auth-patterns/error-response-hides-cause` — Exception Filter не выводит
`String(cause)` в `detail` — только заранее заданное сообщение по коду (cross-ref `R-ERR-MAP-*`).

## 8. Идемпотентность (`auth-patterns/money-commands-need-idempotency-key`)

`auth-patterns/money-commands-need-idempotency-key` — команда, меняющая деньги/резерв (`CreateOrder`, `ConfirmPayment`, `Refund`), требует
`Idempotency-Key`: guard/interceptor проверяет заголовок, Handler по ключу из таблицы идемпотентности
возвращает прежний результат, не дубль (cross-ref `R-DIST-IDEM-*`).

## 9. Хранение токенов на клиенте (`AUTH-20..21`)

`auth-patterns/token-in-httponly-cookie` — для SPA — HttpOnly + Secure + SameSite=Lax cookie (session-cookie у BFF или JWT-в-cookie), не
`localStorage`. `auth-patterns/refresh-token-rotation` — refresh-токены с rotation: при обновлении старый инвалидируется; повторное
использование старого RT → компрометация, инвалидируется вся цепочка.

## 10. Чеклист подключения к новому сервису (Node/NestJS)

1. `JwtStrategy` (passport-jwt + jwks-rsa, `cache: true`) валидирует подпись/exp/iss/aud; невалидный → 401.
2. Глобальные `APP_GUARD`: `JwtAuthGuard` + `RolesGuard`; каждый endpoint — `@Roles(...)` или явный `@Public()`.
3. ABAC по владению в Handler/AccessPolicy (403); admin-обход + audit-interceptor в `*_audit_log`.
4. s2s через mTLS/Client Credentials; outbound-клиенты не анонимны.
5. PII не в логах (pino redact)/exception/событиях; секреты не в git; filter не светит `String(cause)`.
6. Money-команды требуют `Idempotency-Key`; SPA — HttpOnly cookie, RT с rotation.
