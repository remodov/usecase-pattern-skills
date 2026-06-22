# Payment Integration — Python Style Guide (FastAPI / httpx / SQLAlchemy 2.0 async)

Реализация контракта `../payment-integration-rules.md` (`R-PAYINT-*`). Те же коды и разделы — здесь идиома на
async-стеке. Стек: FastAPI, httpx (клиент провайдера), SQLAlchemy 2.0 async, Pydantic v2; фоновый дозабор — см.
`scheduler/python`.

## 1. Идемпотентный флоу провайдера (`R-PAYINT-1..4`)

Out-adapter провайдера на общем `BaseHttpAdapter`; креды берутся из конфигурации (`pydantic-settings`), не per-call.
Идемпотентность — в сервисном слое (read-before-write по natural key):

```python
async def resolve_provider_order_id(provider, payment) -> str | None:
    existing = await provider.find_status(natural_key=str(payment.natural_key))  # R-PAYINT-2
    if existing is not None and existing.provider_order_id:
        return existing.provider_order_id
    registered = await provider.register(
        natural_key=str(payment.natural_key),
        amount_minor=to_minor_units(payment.amount),                            # R-PAYINT-13
        description=str(payment.id),
    )
    return registered.provider_order_id


async def execute_if_not_terminal(provider, provider_order_id, binding_id):
    resp = await provider.get_status(provider_order_id)
    if to_domain_status(resp) == DomainStatus.CREATED:                          # R-PAYINT-3
        await provider.charge(provider_order_id, binding_id)
        resp = await provider.get_status(provider_order_id)
    return resp
```

Конкурентные оплаты одного заказа сериализуются advisory-локом в репозитории (`R-PAYINT-4`, cross-ref `R-JOB-DUP-1`):

```python
async def acquire_order_payment_lock(self, session: AsyncSession, order_id: UUID) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"payment:{order_id}"},
    )
```

- **AVOID** `register()` без предварительного `find_status` (`R-PAYINT-X1`); `charge()` без проверки статуса (`R-PAYINT-X2`).

## 2. Anti-corruption маппинг статусов (`R-PAYINT-5..7`)

Единый stateless-маппер, общий для онлайн- и фонового путей; partial-update через Pydantic `exclude_none`:

```python
def to_domain_status(resp: ProviderStatusResponse) -> DomainStatus:      # R-PAYINT-5 (одна точка)
    code = resp.order_status                                             # код провайдера интерпретируется здесь
    if code == ProviderCode.DEPOSITED:
        return DomainStatus.SUCCEEDED
    if code in _TERMINAL_DECLINE_CODES:
        return DomainStatus.FAILED
    return DomainStatus.PENDING

await repo.update_status(
    session, payment.id,
    PaymentUpdateFields(status=domain_status, deposited_at=deposited_at),  # R-PAYINT-7 partial
)
```

- **PREFER** возвращать доменные типы из adapter/mapper. **AVOID** утечки `ProviderStatusResponse`/кодов выше адаптера (`R-PAYINT-X4`) и дублирования маппинга (`R-PAYINT-X3`).

## 3. Транспорт vs бизнес-отказ (`R-PAYINT-8..10`)

Транспортная ошибка → port-specific `provider_unavailable()`; её пробрасываем и **не** финализируем в FAIL:

```python
try:
    resp = await provider.get_status(provider_order_id)
except ServiceError as err:
    if err.code == "PROVIDER_UNAVAILABLE":      # транспорт → повтор следующим проходом (R-PAYINT-8)
        raise
    await repo.update_status(session, payment.id, PaymentUpdateFields(status=DomainStatus.FAILED))  # бизнес-отказ → терминал (R-PAYINT-9)
    return
```

В out-adapter транспорт/5xx → `provider_unavailable()`, бизнес-код провайдера → `ProviderBusinessError` (`R-PAYINT-10`).

- **AVOID** финализации FAILED по таймауту/5xx (`R-PAYINT-X5`); единого `except` без различения (`R-PAYINT-X6`).

## 4. Reconciliation (`R-PAYINT-11..12`)

Фоновый тик (см. `scheduler/python`) добирает незавершённые через атомарный захват и финализирует:

```python
rows = await repo.claim_unfinished(session, limit=batch, now=datetime.now(timezone.utc))  # SKIP LOCKED + UTC TTL
for payment in rows:
    resp = await execute_if_not_terminal(provider, payment.provider_order_id, payment.binding_id)
    await repo.update_status(session, payment.id, PaymentUpdateFields(status=to_domain_status(resp)))
```

- **AVOID** опоры только на онлайн-путь без дозабора (`R-PAYINT-X7`).

## 5. Деньги (`R-PAYINT-13`)

```python
from decimal import Decimal, ROUND_HALF_UP

def to_minor_units(amount: Decimal) -> int:
    return int((Decimal(amount) * 100).to_integral_value(rounding=ROUND_HALF_UP))  # НЕ int(float*100)
```

Денежные поля — `Mapped[Decimal]` + `Numeric(p, s)` (cross-ref `R-SQLA-MODEL-2`). **AVOID** `float`/`int(float*100)` (`R-PAYINT-X8`).

## 6. Наблюдаемость и аудит (`R-PAYINT-14..15`)

- `structlog` с natural key/`payment_id` в каждом шаге; метрики `payment_provider_total{outcome}`, `payment_provider_unavailable_total`.
- В логи/события/ошибки **не** попадают PAN, секреты, токены провайдера (`R-PAYINT-X9`); каждая денежная операция оставляет аудит-след (`R-PAYINT-X10`).

## Чеклист подключения к новому сервису (Python / FastAPI)

- [ ] Out-adapter провайдера на `BaseHttpAdapter`, креды из `pydantic-settings`.
- [ ] `resolve_provider_order_id` — read-before-write по natural key; `charge` только при не-терминальном статусе.
- [ ] Конкурентные оплаты заказа сериализованы advisory-локом в репозитории.
- [ ] Единый `to_domain_status`-маппер; partial-update `exclude_none`; DTO провайдера не утекают.
- [ ] Транспорт → `provider_unavailable()` (повтор), бизнес-отказ → терминал; нет FAILED по таймауту.
- [ ] Reconciliation через scheduler-тик (claim SKIP LOCKED + UTC TTL).
- [ ] Деньги — `Decimal`, минорные единицы — `ROUND_HALF_UP`.
- [ ] Логи/метрики с идентификатором; нет PAN/секретов в логах.
