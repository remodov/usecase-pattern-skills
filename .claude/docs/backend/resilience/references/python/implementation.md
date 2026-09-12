# Resilience — реализация на Python (httpx / tenacity / circuit breaker / asyncio)

Реализация язык-нейтрального контракта `../spec.md` (`R-RES-*`) на Python async-стеке. Коды общие с
Java; меняется реализация: вместо Resilience4j-аннотаций — обёртки/декораторы на **public-методах out-adapter**:

| Защита | Java (Resilience4j) | Python |
|---|---|---|
| timeout | OkHttp call/read/connect | `httpx.Timeout(connect/read/write/pool)` + `asyncio.timeout()` |
| circuit breaker | `@CircuitBreaker` | `purgatory` (async-native) или `aiobreaker` |
| retry | `@Retry` | `tenacity` (`@retry`, async) |
| bulkhead | `@Bulkhead(SEMAPHORE)` | `asyncio.Semaphore` per-system |
| time limiter | `@TimeLimiter` | `asyncio.timeout()` / `asyncio.wait_for` |
| health | `HealthIndicator` | FastAPI health-check с TTL-кешем |

## 1. Где какая защита (`R-RES-WHERE-*`)

`resilience/outbound-calls-fully-protected` — outbound HTTP к внешним системам: полный набор (timeout + CB + bulkhead + опц. retry). `resilience/outbound-calls-fully-protected` —
internal s2s: timeout + CB. `resilience/durable-retry-via-task-queue` — schedulers/outbox-relay: durable retry через **task-queue** (DB), не
in-memory (`resilience/durable-retry-via-task-queue`). `resilience/inbound-rate-limiting-at-edge` — inbound rate limit — на API Gateway, не в каждом сервисе.
`resilience/no-protection-around-local-operations` — CB/retry вокруг локальных операций (репозиторий, in-memory) — нет транзиентов, любой сбой реален.

## 2. Per-system isolation (`R-RES-ISO-*`)

`resilience/client-per-external-system` — на каждую внешнюю систему — **отдельный `httpx.AsyncClient`** с собственными `httpx.Limits`
(`max_connections`, `max_keepalive_connections`), CB, bulkhead-семафором. `resilience/pool-sizes-are-balanced` — pool sizing per-system:
`max_connections ≈ max_concurrent × 1.2`; суммарно ≤ половина пула БД. `resilience/instance-names-match-system` — единое имя системы (`sber`,
`receipt`) для клиента, CB, семафора.

`resilience/client-per-external-system` — один shared `AsyncClient` на несколько систем (зависание одной блокирует коннекты других).
`resilience/client-per-external-system` — `AsyncClient()` без явных `limits`/`timeout` — глобальные дефолты, shared-семантика.

```python
# adapters/out/payment_provider/client_factory.py
# R-RES-ISO-1: per-system AsyncClient + собственные httpx.Limits + bulkhead-семафор + CB.
# Каждая внешняя система получает СВОЙ набор; имя системы (R-RES-ISO-3) одно для client/CB/sem.
def build_payment_provider_client(settings: "PaymentProviderClientSettings") -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.base_url,
        limits=httpx.Limits(                              # R-RES-ISO-1: per-system pool, не глобальный дефолт (R-RES-ISO-X2)
            max_connections=settings.max_connections,     # R-RES-ISO-2: ≈ max_concurrent × 1.2
            max_keepalive_connections=settings.max_keepalive,
        ),
        timeout=httpx.Timeout(                            # R-RES-TO-1: иерархия connect < read; общий cap — asyncio.timeout
            connect=settings.connect_timeout,
            read=settings.read_timeout,
            write=settings.write_timeout,
            pool=settings.pool_timeout,
        ),
    )

# Composition root собирает per-system триплет {client, breaker, semaphore} под единым именем системы:
payment_provider_client = build_payment_provider_client(settings.client_payment_provider)
payment_provider_sem = asyncio.Semaphore(settings.client_payment_provider.max_concurrent)  # R-RES-BH-1
# breaker — см. §4 (purgatory/aiobreaker), имя инстанса = "payment_provider" (R-RES-ISO-3, R-RES-CFG-3).
# ВАЖНО: ОТДЕЛЬНЫЙ AsyncClient на receipt/insurance/… — НЕ один shared (R-RES-ISO-X1).
```

## 3. Timeouts (`R-RES-TO-*`)

`resilience/timeout-hierarchy` — иерархия `connect < read < total`; `httpx.Timeout(connect=.., read=.., write=.., pool=..)` + общий
`asyncio.timeout(total)` вокруг вызова. `resilience/timeout-hierarchy` — per-system через `<System>ClientSettings` (pydantic-settings
`client_<system>__*`). `resilience/respect-remaining-time-budget` — уважать оставшийся TimeBudget при наличии `traceparent`.

`resilience/timeout-hierarchy` — `AsyncClient()` без timeout — дефолт может «висеть». `resilience/timeout-hierarchy` — total-timeout меньше read —
внутреннее противоречие. `resilience/no-long-synchronous-waits` — read > 60s в синхронном HTTP-handler — в task-queue.

## 4. Circuit Breaker (`R-RES-CB-*`)

`resilience/breaker-on-adapter-method` — CB оборачивает **public-метод out-adapter**, не сгенерированный клиент, не handler, не репозиторий.
`resilience/breaker-window-and-thresholds`..`resilience/breaker-window-and-thresholds` — count-based окно (~50), min calls ~10, failure rate 50% (30% для платежей),
open ~30s → half-open (~3 пробных), slow-call threshold ≈ read/2.

```python
# Инициализация circuit breaker — per-system, имя инстанса = имя системы (R-RES-CB-3..5, R-RES-CFG-3).
# Вариант A — purgatory (async-native): создаётся один менеджер, breaker берётся по имени.
from purgatory import AsyncCircuitBreakerFactory

cb_factory = AsyncCircuitBreakerFactory(
    default_threshold=5,                             # R-RES-CB-3: failures до open (для платежей — ниже порог)
    default_ttl=30.0,                                # R-RES-CB-4: open ~30s → half-open
)
# в адаптер передаётся async-context-менеджер брейкера под именем системы:
breaker = await cb_factory.get_breaker("payment_provider")   # R-RES-ISO-3: имя = имя системы

# Вариант B — aiobreaker (порт pybreaker под asyncio):
from aiobreaker import CircuitBreaker as AioCircuitBreaker
from datetime import timedelta

breaker = AioCircuitBreaker(
    fail_max=5,                                      # R-RES-CB-3
    timeout_duration=timedelta(seconds=30),         # R-RES-CB-4: waitDurationInOpenState
)
# R-RES-CB-X2: НЕ самописный CB на try/except + счётчик — бери отлаженную либу с метриками.
# R-RES-CB-X3: ОТДЕЛЬНЫЙ инстанс на систему — не общий "default" на payment_provider+receipt.
```

```python
# adapters/out/sber/sber_adapter.py
class SberAdapter:                                   # implements PaymentPort из core/
    def __init__(self, client: httpx.AsyncClient, breaker: CircuitBreaker, sem: asyncio.Semaphore) -> None: ...

    async def register(self, order: Order) -> PaymentRef:
        async with self._sem:                        # bulkhead (R-RES-BH)
            try:
                async with self._breaker:            # CB (purgatory/aiobreaker)
                    async with asyncio.timeout(self._settings.total):
                        resp = await self._client.post("/register", json=to_sber(order))
                return to_domain(resp.json())
            except CircuitBreakerError as e:
                raise PaymentPortError.system_unavailable("sber") from e
```

`resilience/open-breaker-maps-to-domain-error` — при open CB → `CircuitBreakerError`; адаптер мапит в port-исключение (`PaymentPortError`), handler — в
503/409. `resilience/no-protection-around-local-operations` — CB на репозитории/in-memory. `resilience/no-custom-breaker` — самописный CB на `try/except` + счётчик
(bug-source; бери отлаженную либу с метриками). `resilience/instance-names-match-system` — общий CB-инстанс на разные системы.

## 5. Retry (`R-RES-RE-*`)

`resilience/retry-only-when-safe` — `tenacity` `@retry` **только** при идемпотентности: read-метод **или** запрос с `Idempotency-Key`
(`auth-patterns/money-commands-need-idempotency-key`). `resilience/retry-with-backoff-and-limit`/`resilience/retry-with-backoff-and-limit` — exponential backoff (`wait_exponential`), `stop_after_attempt(3)` (макс 5),
`retry_if_exception_type` только на транзиентные (timeout/5xx/`ConnectError`). `resilience/durable-retry-via-task-queue`/`resilience/durable-retry-via-task-queue` — долгий
retry (>30s, переживание рестарта) — task-queue (`*_task`: `status`/`retry_count`/`next_attempt_at`/`last_error`,
poll каждые ~5s).

`resilience/retry-only-when-safe` — retry write-метода без `Idempotency-Key` (двойная операция/платёж). `resilience/retry-only-when-safe` — retry на 4xx
(контрактная ошибка). `resilience/retry-with-backoff-and-limit` — retry без exponential backoff (бьёт по лежачей системе). `resilience/retry-with-backoff-and-limit` —
retry на тех же исключениях, что ловит CB, без согласования (двойной счёт failure).

```python
from tenacity import (retry, stop_after_attempt, wait_exponential,
                      retry_if_exception_type)

# R-RES-RE-1: tenacity @retry ТОЛЬКО на идемпотентных — read-метод (ниже) ИЛИ write с Idempotency-Key (AUTH-19).
class PaymentProviderAdapter:                        # implements PaymentPort из core/
    @retry(
        stop=stop_after_attempt(3),                  # R-RES-RE-3: 3 попытки (макс 5 — дальше task-queue)
        wait=wait_exponential(multiplier=0.5, max=8),# R-RES-RE-2: exponential backoff, не линейный (R-RES-RE-X3)
        retry=retry_if_exception_type(               # только транзиентные; НЕ 4xx (R-RES-RE-X2)
            (httpx.ConnectError, httpx.ReadTimeout, ServerSidePortError)),
        reraise=True,
    )
    async def get_status(self, ref: PaymentRef) -> PaymentStatus:   # read → идемпотентен
        async with self._sem:                        # bulkhead остаётся снаружи retry
            async with asyncio.timeout(self._settings.total):
                resp = await self._client.get(f"/payments/{ref.value}")
            return to_domain(_raise_for_status(resp))

# R-RES-RE-X1: retry write-метода (register/charge) без Idempotency-Key → двойной платёж — НЕ ретраить.
# write с идемпотентностью: ключ в заголовке, тогда retry безопасен:
async def charge(self, cmd: ChargeCommand) -> ChargeResult:
    resp = await self._client.post(
        "/charges", json=to_provider(cmd),
        headers={"Idempotency-Key": str(cmd.idempotency_key)})  # AUTH-19: провайдер сам дедуплицирует
    return to_domain(_raise_for_status(resp))
```

## 6. Bulkhead (`R-RES-BH-*`)

`resilience/bulkhead-is-semaphore-based`/`resilience/bulkhead-is-semaphore-based` — `asyncio.Semaphore(max_concurrent)` per-system, **отдельно** от connection-pool;
ограничивает одновременные вызовы. Semaphore работает в текущей таске — `contextvars` (trace/MDC) не теряются.
`resilience/bulkhead-is-semaphore-based` — `max_concurrent ≈ pool × 0.8` (срабатывает раньше исчерпания пула); короткое ожидание/немедленный
fail (`asyncio.timeout` вокруг `acquire` или `Semaphore(value)` без ожидания).

`resilience/bulkhead-is-semaphore-based` — отдельный пул-исполнитель (`run_in_executor`/`ThreadPoolExecutor`) как bulkhead для async-кода —
теряется `contextvars`, лишние треды; семафора достаточно.

## 7. Fallback (`R-RES-FB-*`)

`resilience/fallback-does-not-fake-success` — fallback допустим для деградации (кеш/частичный ответ/дефолт), не для money-операций. `resilience/fallback-does-not-fake-success` —
явная обработка исключения (`except CircuitBreakerError`/`tenacity.RetryError`) с осознанным результатом.

`resilience/fallback-does-not-fake-success` — fallback `Money(0)`/`None` для money-операции (бизнес-баг). `resilience/fallback-does-not-fake-success` — fallback, тихо
возвращающий «успех». `resilience/fallback-does-not-fake-success` — fallback с вызовом второго провайдера без своего CB (cascading failure).

## 8. Конфигурация (`R-RES-CFG-*`)

`resilience/declarative-configuration`/`resilience/declarative-configuration` — параметры CB/retry/timeout/bulkhead — через `pydantic-settings` (`<System>ClientSettings`,
секции `client.<system>`), не хардкодом в коде; дефолты + per-system override. `resilience/instance-names-match-system` — имена инстансов = имя
системы. `resilience/declarative-configuration` — скрытая программная конфигурация без причины.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

# R-RES-CFG-1/2: per-system настройки клиента — типизированы, валидируются, не хардкод в коде (R-RES-CFG-X1).
class PaymentProviderClientSettings(BaseSettings):
    base_url: str
    connect_timeout: float = 5.0                     # R-RES-TO-1: connect < read < total
    read_timeout: float = 30.0
    write_timeout: float = 10.0
    pool_timeout: float = 5.0
    total: float = 36.0                              # общий cap (asyncio.timeout); ≥ connect+read+buffer (R-RES-TO-X2)
    max_connections: int = 24                        # R-RES-ISO-2: ≈ max_concurrent × 1.2
    max_keepalive: int = 12
    max_concurrent: int = 20                         # bulkhead-семафор (R-RES-BH-3)
    max_attempts: int = 3                            # R-RES-RE-3: верх — 5; больше → task-queue
    cb_fail_max: int = 5                             # R-RES-CB-3: для платежей порог ниже
    cb_reset_timeout: float = 30.0                   # R-RES-CB-4
    # секция client.payment_provider.* → env CLIENT_PAYMENT_PROVIDER__READ_TIMEOUT и т.п.
    model_config = SettingsConfigDict(env_prefix="CLIENT_PAYMENT_PROVIDER__")
```

## 9. Связка с OpenAPI generator (`R-RES-OAS-*`)

`resilience/breaker-on-adapter-method` — обёртки CB/retry/bulkhead — на public-методе out-adapter, не на сгенерированном клиенте.
`resilience/client-generated-from-contract` — для нового кода клиент генерируется из OpenAPI-спеки внешней системы (`openapi-python-client` /
openapi-generator `python` target, на базе httpx); спека в `adapters/out/<system>/openapi/`, codegen не коммитится.
`resilience/mapper-between-client-and-port` — между сгенерированным клиентом и портом из `core/` — **mapper** (DTO внешней системы → domain);
адаптер не пробрасывает DTO наверх.

`resilience/breaker-on-adapter-method` — обёртки на сгенерированном клиенте (регенерация затрёт). `R-RES-OAS-X3` — возврат DTO внешней
системы из port-метода.

## 10. Health checks (`R-RES-HC-*`)

`resilience/cached-health-probe-per-system` — на каждую систему — health-индикатор (функция/класс), отражается в `/health/ready`. `resilience/cached-health-probe-per-system` —
**кеш TTL ~30s** (`cachetools.TTLCache` / ручной `last_probe`), не probe на каждый actuator-call. `resilience/cached-health-probe-per-system` —
лёгкий probe (`GET /health`/`OPTIONS`), не бизнес-вызов. `resilience/external-systems-affect-readiness` — readiness учитывает внешние, liveness — нет.

`resilience/cached-health-probe-per-system` — sync-probe без кеша на каждый `/health` (DDoS внешней системы своими probe). `resilience/cached-health-probe-per-system` —
probe бизнес-операцией (`register_test_order`).

## 11. Async и polling (`R-RES-ASYNC-*`)

`resilience/async-calls-need-time-limit` — polling внешней системы — через **task-queue**, не `asyncio.sleep`-цикл в handler. `resilience/no-long-synchronous-waits` —
`asyncio.sleep` в адаптере допустим только при total wait <2s (короткий фиксированный backoff). `resilience/async-calls-need-time-limit` —
для всех async-вызовов — `asyncio.timeout()`/`wait_for` (отдельный time-limit).

`resilience/no-long-synchronous-waits` — `asyncio.sleep`-цикл опроса в handler (держит таску, исчерпывает воркеры). `resilience/no-long-synchronous-waits` —
`asyncio.sleep > 5s` — запах «должно быть task-queue».

## 12. Observability (`R-RES-OBS-*`)

`resilience/resilience-state-is-observable` — метрики CB/retry/bulkhead через `prometheus-client` (state CB, retry count, semaphore rejections).
`resilience/resilience-state-is-observable` — OTel-span на adapter-методе с атрибутами `circuit_breaker.state`, `external.system`. `resilience/resilience-state-is-observable` —
структурный лог (WARN) на каждый state-transition CB, не на каждый успешный вызов.

`resilience/resilience-state-is-observable` — отключение метрик resilience без причины (SRE не увидит залипший half-open).

## 13. Чеклист подключения к новому сервису (Python)

1. На каждую внешнюю систему — отдельный `AsyncClient` + CB + semaphore + per-system settings.
2. timeout (httpx + `asyncio.timeout`), иерархия connect<read<total; CB/retry/bulkhead на public-методе адаптера.
3. retry только при идемпотентности, exponential backoff, не на 4xx; долгий retry — task-queue.
4. bulkhead — `asyncio.Semaphore`, не executor-пул; sizing < pool.
5. fallback — не для money, не «тихий успех»; mapper DTO→domain, порт возвращает domain.
6. health — кеш TTL, лёгкий probe; polling — task-queue, не sleep-цикл; метрики/спаны включены.
