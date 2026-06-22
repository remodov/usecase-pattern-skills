# Codegen — индекс правил (Python contract/DB-first генерация)

> **Что это.** Генерация артефактов из источников истины: **схемы** Pydantic из OpenAPI-контракта
> (`datamodel-codegen`) и **ORM-модели** из DBML-схемы БД (`dbml2sql` → Liquibase → `sqlacodegen`).
> Языко-специфичный concern (как `sqlalchemy` / `python-bootstrap`) — **только Python**, префикс `PYGEN-*`.
> Скиллы читают этот файл; код-примеры включены. Коды: `PYGEN-<N>` — обязательно, `PYGEN-X<N>` — антипаттерн.
> Сшивки: формат самого контракта/DTO — `rest-api/rest-api-rules.md` (`R-API-*`); типы ORM и слой persistence —
> `python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-*`); типы колонок — `pg-types` (`PG-T-*`); безопасность
> миграций — `pg-migrations` (`PG-M-*`).

Суть: контракт (OpenAPI) и DBML — **источники истины**; код генерируется из них, а не пишется с нуля.
Это командный **contract/DB-first** binding; миграции ведёт **Liquibase** — единый инструмент трека (см. §3,
cross-ref `R-SQLA-MIG-1`).

## 1. Схемы — OpenAPI → Pydantic (`datamodel-codegen`)
**MUST:**
- **PYGEN-SC-1.** OpenAPI-контракт (`doc/openapi.yaml`, версия ≥ 3.0.3; предпочтительно 3.1) — единый источник истины; Pydantic-схемы генерируются `datamodel-codegen`, не пишутся вручную с нуля.
- **PYGEN-SC-2.** Вывод — Pydantic **v2** (`--output-model-type pydantic_v2.BaseModel`), `populate_by_name=True` (флаг `--allow-population-by-field-name` даёт это в v2-выводе).
- **PYGEN-SC-3.** Поля `snake_case` + `alias` в `camelCase` — соответствие JSON-контракту (cross-ref `R-API-RSP-*`); генерится `--snake-case-field`.
- **PYGEN-SC-4.** Enum — `StrEnum` (`--use-subclass-enum`), значения `UPPER_SNAKE` (cross-ref `R-API`).
- **PYGEN-SC-5.** Общий базовый `ApiBaseModel` с `model_config` (`populate_by_name`, `from_attributes`, сериализация `datetime` → ISO 8601 `Z`) — ручная надстройка поверх генерации, наследуется всеми схемами.
- **PYGEN-SC-6.** Типы: деньги — `Decimal`; время — aware `datetime`; `X | None`, `list[X]`; `from __future__ import annotations`.

**MUST NOT:**
- **PYGEN-SC-X1.** Писать схемы с нуля руками вместо генерации из контракта — даёт дрейф контракт↔код.
- **PYGEN-SC-X2.** Править сгенерированный файл, не обновив контракт-источник (правка теряется при регенерации).
- **PYGEN-SC-X3.** Enum как `class X(str, Enum)` вместо `StrEnum`; `null` в 2xx-ответе (нет `exclude_none`).
- **PYGEN-SC-X4.** `float` для денежных полей.

Команда (пример):
```bash
datamodel-codegen \
  --input doc/openapi.yaml --input-file-type openapi \
  --output <pkg>/schemas/ \
  --output-model-type pydantic_v2.BaseModel \
  --use-subclass-enum --snake-case-field --allow-population-by-field-name \
  --use-annotated --use-standard-collections --use-union-operator \
  --field-constraints --target-python-version 3.12
```
```python
# <pkg>/schemas/common.py — ручная база поверх генерации (PYGEN-SC-5)
class ApiBaseModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, from_attributes=True,
        json_encoders={datetime: serialize_datetime_to_utc_z},
    )

class OrderStatus(StrEnum):            # PYGEN-SC-4 (НЕ class X(str, Enum))
    PENDING = "PENDING"
    BOOKED = "BOOKED"

class VehicleInfo(ApiBaseModel):       # PYGEN-SC-3/6
    vehicle_id: UUID | None = Field(default=None, alias="vehicleId")
    fare_amount: Decimal | None = Field(default=None, alias="fareAmount")  # НЕ float
```

## 2. ORM-модели — DBML → Liquibase → `sqlacodegen`
**MUST:**
- **PYGEN-MD-1.** `doc/schema.dbml` — источник истины схемы БД.
- **PYGEN-MD-2.** Пайплайн: `dbml2sql schema.dbml --postgres -o schema.sql` → Liquibase changelog (в `liquibase/changelog/generated/`) → `sqlacodegen` (черновик `models.py`).
- **PYGEN-MD-3.** Типы ORM: деньги — `Numeric(p, s)` → **`Decimal`**; время — `DateTime(timezone=True)` → aware; UUID — `UUID(as_uuid=True)`; PG-enum — `PG_ENUM(..., create_type=False)` (тип создаёт Liquibase). Cross-ref `R-SQLA-MODEL-2`, `PG-T-013/030/040`.
- **PYGEN-MD-4.** ORM-модели — в `adapters/out/persistence/`, не в `core/` (cross-ref `R-SQLA-MODEL-1`).
- **PYGEN-MD-5.** Сгенерированный `models.py` — стартовый черновик; ручная доводка допустима, но финальный артефакт соответствует `R-SQLA-MODEL-*` (типы, расположение, анемичность).

**MUST NOT:**
- **PYGEN-MD-X1.** `Mapped[float]` для денежных колонок (потеря точности) — частый реальный дефект; брать `Mapped[Decimal]`.
- **PYGEN-MD-X2.** `DateTime` без timezone (naive) с «доклейкой» tz только на сериализации — колонка `DateTime(timezone=True)`.
- **PYGEN-MD-X3.** Пропуск шага `dbml2sql` (Liquibase не подхватывает `.dbml` напрямую).
- **PYGEN-MD-X4.** Доменная логика на ORM-модели (cross-ref `R-SQLA-MODEL-X1`).

```python
# <pkg>/adapters/out/persistence/models.py — после sqlacodegen + доводки (PYGEN-MD-3)
OrderStatusEnum = PG_ENUM("PENDING", "BOOKED", name="orderstatus", create_type=False)

class OrderModel(Base):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    fare_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))      # PYGEN-MD-3 (НЕ float)
    status: Mapped[str] = mapped_column(OrderStatusEnum, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)  # PYGEN-MD-X2: tz=True
```

## 3. Миграции — Liquibase
**MUST:**
- **PYGEN-MIG-1.** Миграции ведутся **Liquibase** (changelog в `liquibase/changelog/generated/` + diff-changelog'и) — единый инструмент трека (cross-ref `R-SQLA-MIG-1`).
- **PYGEN-MIG-2.** Безопасность миграций (expand-contract, `CONCURRENTLY`, `lock_timeout`, координация с N-1) — по `pg-migrations-rules.md` (`PG-M-*`, нейтральны, применяются и к Liquibase).

**MUST NOT:**
- **PYGEN-MIG-X1.** Несколько источников схемы (ручной DDL мимо changelog рядом с Liquibase) — единственный источник истины DDL — Liquibase changelog, сгенерированный из DBML.
- **PYGEN-MIG-X2.** Править уже применённый changelog — добавлять новый (cross-ref `PG-M-*`).

## Чеклист подключения к новому сервису (Python / codegen)

- [ ] `doc/openapi.yaml` и `doc/schema.dbml` — источники истины, в репозитории.
- [ ] Воспроизводимая команда `datamodel-codegen` (Pydantic v2, StrEnum, snake+alias) в Makefile/justfile.
- [ ] Пайплайн `dbml2sql --postgres` → Liquibase changelog → `sqlacodegen` зафиксирован (не пропущен `dbml2sql`).
- [ ] Деньги — `Decimal`, время — `DateTime(timezone=True)` и в схемах, и в ORM (проверить после генерации).
- [ ] Миграции — Liquibase (единственный источник DDL); безопасность по `PG-M-*`.
- [ ] Регенерация не затирает ручные надстройки (`ApiBaseModel`, доводка `models.py`) — они вне генерируемых блоков.
