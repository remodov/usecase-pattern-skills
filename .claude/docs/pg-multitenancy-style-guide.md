# PostgreSQL Multi-tenancy Style Guide

Конвенции для multi-tenant сервисов на PostgreSQL: схема, защита от утечек между тенантами, RLS. Кодами `PG-MT-NNN` ссылается скилл `ucp-pg-schema-review` (DDL) и `ucp-pattern-review` (Java code).

Базовый принцип: **забытый `WHERE tenant_id = ?` в ОДНОМ запросе = security-уязвимость и потенциальная утечка PII между тенантами**. Серверная защита (RLS) обязательна для проектов, где это критично.

---

## 1. Выбор паттерна

### `PG-MT-001` — Default — row-per-tenant с `tenant_id` колонкой

Просто, эффективно, масштабируемо до тысяч тенантов.

### `PG-MT-002` — Schema-per-tenant — для энтерпрайз-клиентов с регуляторными требованиями к изоляции

### `PG-MT-003` — DB-per-tenant — только когда тенанты — полноценные клиенты с собственным контрактом

(≤ десятки) и нужна полная изоляция (отдельные креды, backup-стратегия).

## 2. Row-per-tenant — DDL

### `PG-MT-010` — Каждая бизнес-таблица имеет колонку `tenant_id bigint NOT NULL REFERENCES tenant(id)`

### `PG-MT-011` — Композитный PK с `tenant_id` первой колонкой:

`PRIMARY KEY (tenant_id, id)`. Гарантирует, что все индексы автоматически partition'ятся по тенанту, partition pruning работает на бизнес-уровне.

### `PG-MT-012` — Каждый индекс начинается с `tenant_id`:
```sql
CREATE INDEX ix_order_tenant_status ON order_doc (tenant_id, status);
CREATE INDEX ix_order_tenant_created ON order_doc (tenant_id, created_at DESC);
```

### `PG-MT-013` — Foreign keys внутри тенанта

обязаны проверять, что parent в том же тенанте. Если PK включает `tenant_id` — это автоматически.

## 3. Row-Level Security (RLS) — обязательно

### `PG-MT-020` — RLS — серверная защита: PG сам добавляет фильтр в каждый запрос. Включи на каждой бизнес-таблице

```sql
ALTER TABLE order_doc ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON order_doc
    USING (tenant_id = current_setting('app.tenant_id')::bigint);
```

### `PG-MT-021` — `SET LOCAL` обязателен (не `SET`):
```java
jdbc.execute("SET LOCAL app.tenant_id = ?", tenantId);
```

Без `LOCAL` GUC живёт всю сессию — тенант «протечёт» при возврате connection в pool (особенно с PgBouncer transaction mode).

### `PG-MT-022` — RLS — defense in depth

Даже если разработчик забыл `WHERE tenant_id`, PG не отдаст чужие данные.

### `PG-MT-023` — RLS не работает для superuser

Для backup/admin — отдельная роль без `BYPASSRLS`.

## 4. Java/Spring code

### `PG-MT-030` — `TenantContext` через ThreadLocal + `HandlerInterceptor`

в Spring Web — извлекает `tenant_id` из JWT/header, ставит в ThreadLocal.

### `PG-MT-031` — `@Transactional`-методы в начале выставляют tenant в БД:
```java
@Component
@RequiredArgsConstructor
class TenantAwareTransactionInterceptor {
    private final JdbcTemplate jdbc;
    private final TenantContext ctx;

    @EventListener(TransactionPhaseEvent.class)
    public void onTransactionStart(...) {
        jdbc.execute("SET LOCAL app.tenant_id = " + ctx.currentTenantId());
    }
}
```

Или через `@Aspect` на UseCaseHandler.

### `PG-MT-032` — Каждый Java-запрос в jOOQ должен включать `WHERE tenant_id = ?` или полагаться на RLS

Лучше оба.

### `PG-MT-033` — Кросс-тенант запросы

(admin-операции, аналитика) — отдельный сервис с ролью `BYPASSRLS`. В обычном API — никогда.

## 5. Schema-per-tenant — детали

### `PG-MT-040` — Каждый тенант — своя schema с одинаковой структурой

`SET LOCAL search_path = tenant_<id>, public` перед операциями.

### `PG-MT-041` — Миграции — Liquibase/Flyway с iteration по схемам

На 100 схемах — миграция в N раз дольше.

### `PG-MT-042` — `SET LOCAL` обязателен

— иначе через PgBouncer следующий запрос пойдёт в чужую схему.

### `PG-MT-043` — Не масштабируется до тысяч тенантов

На > 1000 схем `pg_class` распухает, autovacuum не справляется.

## 6. DB-per-tenant — детали

### `PG-MT-050` — Routing DataSource по тенанту

— `AbstractRoutingDataSource` Spring или `MultiTenantConnectionProvider` JPA.

### `PG-MT-051` — Подходит для:

≤ десятков энтерпрайз-клиентов. Каждый с собственным SLA, backup, потенциально хостом.

### `PG-MT-052` — Самый дорогой по операциям

— миграции, мониторинг, backup на каждого тенанта.

## 7. Партиционирование по тенанту

### `PG-MT-060` — `PARTITION BY LIST (tenant_id)` — спорный паттерн

Оправдан только при ≤ десятков тенантов с большими объёмами и GDPR-требованием «удалить всё за тенанта одной операцией».

### `PG-MT-061` — Не применяй на тысячах мелких тенантов

— будет тысячи партиций → планировщик тормозит.

## 8. Антипаттерны

### `PG-MT-080` — Row-per-tenant без `WHERE tenant_id` хотя бы в одном запросе

— security-уязвимость.

### `PG-MT-081` — Row-per-tenant без RLS

— защита только в коде, легко забыть в новом методе.

### `PG-MT-082` — Schema-per-tenant на тысячах тенантов

— `pg_class` распухает.

### `PG-MT-083` — DB-per-tenant для всех тенантов SaaS

— операционный кошмар.

### `PG-MT-084` — `SET search_path` без `LOCAL`

в transaction-pool mode — search_path остаётся в сессии, следующий тенант видит чужую схему.

### `PG-MT-085` — `tenant_id` НЕ первой колонкой в PK

— теряется partition pruning, индексы хуже работают.

### `PG-MT-086` — Кросс-тенант SELECT в основном API

— даже если для admin-функций. Должен быть отдельный admin-сервис с `BYPASSRLS`.

---

## Чек-лист на ревью

- [ ] Выбран паттерн под бизнес-модель: row (default), schema (compliance), db (enterprise).
- [ ] `tenant_id` колонка во всех бизнес-таблицах (для row-per-tenant).
- [ ] `tenant_id` первой колонкой в композитных PK и индексах.
- [ ] `WHERE tenant_id = ?` в каждом запросе ИЛИ через RLS.
- [ ] RLS включён для defense in depth.
- [ ] `SET LOCAL` (не `SET`) для tenant-context в transaction-pooled connections.
- [ ] Миграции учитывают multi-schema (для schema-per-tenant).
- [ ] Кросс-тенант запросы — отдельный сервис, не основной API.
