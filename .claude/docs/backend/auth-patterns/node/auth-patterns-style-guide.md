# Auth Patterns — Node Style Guide (NestJS / passport-jwt / jwks-rsa)

Реализация язык-нейтрального контракта `../auth-patterns-rules.md` (`AUTH-*`) на NestJS. Коды общие с Java и
Python; механизм: вместо Spring Security `@PreAuthorize`/`oauth2ResourceServer` — **Guards** NestJS
(`@nestjs/passport` + `passport-jwt`) с JWKS-клиентом `jwks-rsa`. Без самописного парсинга подписи.

## 1. Где какая проверка (`AUTH-1..3`)

`AUTH-1` — edge/gateway: аутентификация (валидация JWT: подпись, `exp`, `iss`, `aud`) + rate limit; identity в
downstream. `AUTH-2` — BFF/application: грубая RBAC по роли — `@Roles('admin')` + `RolesGuard`.
`AUTH-3` — domain-handler: ABAC по ресурсу (`order.customerId === principal.sub`), не на gateway (он не знает домен).

## 2. JWT validation (`AUTH-4..6`)

`AUTH-4` — JWT валидируется одной стратегией на проверенных библиотеках (`passport-jwt` + `jwks-rsa`), не
самописным `jwt.decode` без проверки подписи/claims. `AUTH-5` — JWK Set тянется из IdP по `jwksUri` с кешем
(~5 мин — `cache: true` у `jwks-rsa`; не распаковывать ключи руками). `AUTH-6` — невалидная
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

`AUTH-7` — роли из claim (`realm_access.roles` Keycloak / `scope`) маппятся в `Principal.roles` в
`JwtStrategy.validate`. `AUTH-8` — разрешённые роли: `customer`/`seller`/`admin`/`system`. `AUTH-9` — на каждом
endpoint — `@Roles(...)`; endpoint без проверки роли (и без явного `@Public()`) — критично.

## 4. ABAC (`AUTH-10..12`)

`AUTH-10` — команда/запрос с агрегатом по id — ABAC по владению: сравнение `aggregate.ownerId` с
`principal.sub` в Handler с `ForbiddenError` (→ 403 на edge). `AUTH-11` — ABAC-логика в выделенном
`@Injectable() AccessPolicy` или Handler, не размазана по контроллерам. `AUTH-12` — `admin` обходит ABAC,
но каждое действие — в audit log (`AUTH-15`).

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

`AUTH-13` — s2s: mTLS (Service Mesh) либо Client Credentials Flow (`grant_type=client_credentials`,
`scope=service:operation`; токен получает и кеширует outbound-клиент). `AUTH-14` — клиенты в `adapters/out/*`
(axios/undici) не ходят без mTLS/`Bearer`; анонимный inter-service трафик — критично.

## 6. Аудит admin-команд (`AUTH-15`)

`AUTH-15` — каждая state-changing команда от `admin` пишет строку в `*_audit_log` (`actor_id`, `occurred_at`,
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

`AUTH-16` — PII (email/phone/ФИО/адрес) не в логах (nestjs-pino `redact`-paths, даже DEBUG), не в
`err.message`/`problem.detail`, не в Kafka-событиях (только id, PII подгружает потребитель). `AUTH-17` —
секреты (client-secret, DB-пароли, ключи) **не в git** — через env / Vault / SealedSecrets, читаются
валидируемым конфигом (`NESTBOOT-4`, `R-SEC-SECRET-X1`). `AUTH-18` — Exception Filter не выводит
`String(cause)` в `detail` — только заранее заданное сообщение по коду (cross-ref `R-ERR-MAP-*`).

## 8. Идемпотентность (`AUTH-19`)

`AUTH-19` — команда, меняющая деньги/резерв (`CreateOrder`, `ConfirmPayment`, `Refund`), требует
`Idempotency-Key`: guard/interceptor проверяет заголовок, Handler по ключу из таблицы идемпотентности
возвращает прежний результат, не дубль (cross-ref `R-DIST-IDEM-*`).

## 9. Хранение токенов на клиенте (`AUTH-20..21`)

`AUTH-20` — для SPA — HttpOnly + Secure + SameSite=Lax cookie (session-cookie у BFF или JWT-в-cookie), не
`localStorage`. `AUTH-21` — refresh-токены с rotation: при обновлении старый инвалидируется; повторное
использование старого RT → компрометация, инвалидируется вся цепочка.

## 10. Чеклист подключения к новому сервису (Node/NestJS)

1. `JwtStrategy` (passport-jwt + jwks-rsa, `cache: true`) валидирует подпись/exp/iss/aud; невалидный → 401.
2. Глобальные `APP_GUARD`: `JwtAuthGuard` + `RolesGuard`; каждый endpoint — `@Roles(...)` или явный `@Public()`.
3. ABAC по владению в Handler/AccessPolicy (403); admin-обход + audit-interceptor в `*_audit_log`.
4. s2s через mTLS/Client Credentials; outbound-клиенты не анонимны.
5. PII не в логах (pino redact)/exception/событиях; секреты не в git; filter не светит `String(cause)`.
6. Money-команды требуют `Idempotency-Key`; SPA — HttpOnly cookie, RT с rotation.
