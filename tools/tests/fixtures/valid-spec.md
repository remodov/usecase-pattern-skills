# PostgreSQL Migrations

## Purpose

Как менять схему PostgreSQL, не роняя прод.

**Что здесь главное**

- Первое правило домена простым языком.
- Второе правило простым языком.
- Где чаще всего ошибаются и почему это не видно сразу.

<!-- BEGIN:ucp-domain-stats -->
**Чем держится домен.** Требований — 1; проверкой закрыто 1, держится ревью 0 (0 %).
<!-- END:ucp-domain-stats -->

## Requirements

### Requirement: lock_timeout в каждой миграции с ALTER TABLE

Миграция с `ALTER TABLE` SHALL начинаться с `SET LOCAL lock_timeout`;
без него миграция SHALL NOT попадать в релиз.

**Почему**: без этого требования нарушение доходит до прода и обнаруживается по последствиям.
**ID**: pg-migrations/lock-timeout-required
**Код**: PG-M-022
**Гейт**: squawk:require-lock-timeout
**Покрытие**: частичное
**Не ловит**: значение таймаута линтер не оценивает — `lock_timeout = '5min'` для него неотличим от трёх секунд.

#### Scenario: changeset с ALTER TABLE без таймаута

- **WHEN** в changeset есть `ALTER TABLE` и нет `SET LOCAL lock_timeout`
- **THEN** squawk краснеет и называет файл миграции
