# Background Jobs & Scheduling — Python Style Guide (FastAPI / SQLAlchemy 2.0 async)

Реализация контракта `../scheduler-rules.md` (`R-JOB-*`). Те же коды и разделы — здесь идиома на async-стеке.
Стек по умолчанию: FastAPI, SQLAlchemy 2.0 async (`asyncpg`), Postgres, внешний Celery как планировщик-тик.
Дополнительно — `redis[asyncio]`, `arq`/`taskiq` как escalation.

## Решение по умолчанию (две оси)

Фоновую работу UCP делит на **две независимые оси**; не путать их в один механизм:

- **Ось A — work queue (что делать):** **БД-as-queue на `FOR UPDATE SKIP LOCKED`** — дефолт.
- **Ось B — periodic tick (когда запускать):** **внешний Celery (beat) → внутренний HTTP-эндпоинт** — дефолт.

Ключевой приём: Celery (отдельный сервис-планировщик) только **толкает** работу по HTTP; вся async-логика
остаётся в FastAPI/хендлерах. Так обходится классическая проблема «async внутри sync Celery task» — внутри
Celery-задачи нет ни event loop, ни async SQLAlchemy, только HTTP-вызов.

## 1. Выбор механизма (`R-JOB-KIND-*`)

| Природа | Решение по умолчанию | Когда |
|---|---|---|
| Очередь единиц работы | **БД-as-queue (SKIP LOCKED)** | есть Postgres, нужна транзакционная согласованность job+данные |
| Периодика | **внешний Celery (beat) → internal HTTP → Dispatcher/UseCase** | любой периодический прогон в multi-replica |
| Event-driven retry | Redis reliable-queue (BLMOVE + processing-list) или брокер | ретраи онлайн-операций |
| Высокий throughput / фан-аут | escalation: **arq** (Redis-only) или **taskiq** (multi-broker), async-native | БД-as-queue упёрся в throughput / сложная маршрутизация |
| Мелкий after-response side-effect | FastAPI `BackgroundTasks` | письмо/инвалидация кеша после ответа, потеря допустима |

- **PREFER** для периодики — внешний Celery-beat, дёргающий тонкий HTTP-эндпоинт; async-логика не уходит внутрь Celery-task. k8s `CronJob` (`concurrencyPolicy: Forbid`) — равнозначная альтернатива, если Celery в инфраструктуре не нужен.
- **PREFER** async-native брокеры (`arq`, `taskiq`), если очередь перерастает БД. Полноценный Celery-воркер (не только beat) для самой работы — только при mixed CPU-bound sync; тогда task → HTTP в FastAPI, не async внутри task. `Dramatiq` — компромисс (async там second-class).
- **AVOID** `BackgroundTasks` для денег/периодики/гарантий (`R-JOB-KIND-X1`).

## 2. Идемпотентность (`R-JOB-IDEM-*`)

Read-before-write по natural-key перед обращением во внешнюю систему:

```python
async def ensure_external_order(self, order: PaymentOrder) -> ExternalId:
    existing = await self._gateway.find_by_natural_key(order.order_number)  # R-JOB-IDEM-2
    if existing is not None:
        return existing.external_id
    return await self._gateway.register(order)
```

- **AVOID** опоры на «очередь доставит ровно один раз» (`R-JOB-IDEM-X1`).

## 3. Антидубли на репликах (`R-JOB-DUP-*`)

**Work queue — атомарный захват батча через `FOR UPDATE SKIP LOCKED`** (несколько реплик берут непересекающиеся батчи):

```python
async def claim_due(self, *, limit: int, now: datetime) -> list[PaymentOrder]:
    stmt = (
        select(PaymentOrderModel)
        .where(PaymentOrderModel.status == JobStatus.PENDING)
        .where(PaymentOrderModel.run_after <= now)
        .order_by(PaymentOrderModel.run_after)
        .limit(limit)
        .with_for_update(skip_locked=True)          # R-JOB-DUP-1, cross-ref PG-W-*
    )
    rows = (await self._session.execute(stmt)).scalars().all()
    return [to_domain(r) for r in rows]
```

**Periodic tick — один источник тика, вне реплик API.** Внешний Celery-beat (отдельный деплой `*-celery-jobs`)
по расписанию делает HTTP-вызов; сам тик не дублируется по репликам приложения, а конкуренция воркеров,
забирающих работу, обезврежена `SKIP LOCKED`:

```python
# celery beat (внешний сервис-планировщик): задача только толкает работу по HTTP
@celery_app.task
def tick_process_payments() -> None:
    httpx.post("http://otw-svc/internal/jobs/process", timeout=5).raise_for_status()

celery_app.conf.beat_schedule = {
    "process-payments": {"task": "tick_process_payments", "schedule": 60.0},
}
```

Внутренний эндпоинт тонкий, скрыт из схемы, делегирует в Dispatcher (вся async-логика — здесь, не в Celery):

```python
jobs_router = APIRouter(prefix="/internal/jobs", include_in_schema=False)

@jobs_router.post("/process")
async def process(dispatcher: DispatcherDep) -> JobRunResult:
    return await dispatcher.dispatch(ProcessDuePaymentOrders())
```

Для beat-singleton: один экземпляр beat (replicas=1) или single-beat lock — иначе тик задвоится (`R-JOB-DUP-2`).
Альтернатива без Celery — k8s `CronJob` с `concurrencyPolicy: Forbid`, args `curl -XPOST .../internal/jobs/process`.

- **AVOID** in-process `APScheduler`/`while`-loop в каждой реплике без координации (`R-JOB-DUP-X1`). APScheduler допустим **только** для single-replica/dev; в multi-replica обязателен k8s `Lease`/leader-election или PG advisory-lock.
- **AVOID** расчёта «воркер один» вместо явного claim (`R-JOB-DUP-X2`); нескольких beat-экземпляров без single-lock.

## 4. Надёжность (`R-JOB-REL-*`)

- Retry с экспоненциальным backoff, лимит попыток, затем **DLQ** (см. `resilience`/`R-RES-RETRY-*`).
- Транспортная ошибка внешней системы → единица остаётся `PENDING`/`IN_PROGRESS` (заберёт следующий тик); бизнес-ошибка → терминальный `FAILED` (`R-JOB-REL-3`).
- Зависшие claim'ы восстанавливать по visibility-timeout (`run_after`/`locked_until` в прошлом снова видны).
- **Redis reliable-queue:** processing-list/consumer-group **per-replica**, иначе `recover()` вернёт в общую очередь то, что обрабатывает другая реплика (`R-JOB-REL-X2`).
- **AVOID** blocking `asyncio.sleep`-retry внутри одного прохода, удерживающего claim (`R-JOB-REL-X1`).

## 5. Время и конфиг (`R-JOB-TIME-*`, `R-JOB-CFG-*`)

```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)                 # R-JOB-TIME-1 (НЕ datetime.now())
cutoff = now - timedelta(minutes=settings.pending_ttl_minutes)
```

Колонки времени — `DateTime(timezone=True)` (cross-ref `R-SQLA-MODEL-2`). Конфиг — `pydantic-settings`:

```python
class SchedulerSettings(BaseSettings):
    process_batch_size: int = 50
    pending_ttl_minutes: int = 25
    retry_max_attempts: int = 3
    model_config = SettingsConfigDict(env_prefix="JOBS_")
```

- **AVOID** naive `datetime.now()` для cutoff (`R-JOB-TIME-X1`); сырые `os.environ[...]` россыпью.

## 6. Наблюдаемость (`R-JOB-OBS-*`)

- Метрики `prometheus_client`: `jobs_processed_total{job,outcome}`, `jobs_duration_seconds`, `jobs_queue_depth`, `jobs_lag_seconds`.
- Лог — `structlog` с `correlation_id`/`job_unit_id` (cross-ref `R-OBS-LOG-*`); алерт на рост `queue_depth`/`lag`.

## Чеклист подключения к новому сервису (Python / FastAPI)

- [ ] Определена ось: work queue (БД-as-queue) и/или periodic tick (внешний Celery-beat → HTTP).
- [ ] Захват батча через `with_for_update(skip_locked=True)` + `limit`.
- [ ] Внутренний `/internal/jobs/*` роутер `include_in_schema=False`, делегирует в Dispatcher.
- [ ] Тик — внешний Celery-beat (single instance) или k8s CronJob `Forbid`; нет in-process планировщика в репликах.
- [ ] Celery-task только толкает HTTP, async-логика не внутри task.
- [ ] Идемпотентность: read-before-write по natural-key.
- [ ] Retry+backoff+DLQ; recovery зависших по visibility-timeout.
- [ ] UTC tz-aware время; `pydantic-settings` для параметров.
- [ ] Метрики processed/duration/queue-depth/lag + structlog correlation-id.
- [ ] APScheduler/BackgroundTasks — только в допустимых нишах (dev/мелкий side-effect).
