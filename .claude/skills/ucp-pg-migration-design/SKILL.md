---
lang: any
name: ucp-pg-migration-design
description: Сгенерировать безопасные Liquibase changeset'ы для breaking changes PostgreSQL-схемы (требования pg-migrations/*) — expand-contract для RENAME/DROP COLUMN и ALTER TYPE, FK через NOT VALID, CREATE INDEX CONCURRENTLY, lock_timeout в каждой фазе.
when_to_use: Триггеры — «переименовать колонку без даунтайма», «безопасный ALTER TYPE», «добавить FK constraint». Existing-схема, не новый агрегат.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# PostgreSQL Migration — проектирование

Ты генерируешь expand-contract Liquibase changeset'ы для breaking changes existing-схемы по требованиям `backend/pg-migrations/spec.md`. Цель — миграция, которая **не ломает прод** под нагрузкой и совместима с предыдущей версией кода (N-1 правило, `pg-migrations/n-minus-one-compatibility`).

Для нового агрегата (просто `CREATE TABLE`) — `ucp-pg-schema-design`, не этот скилл.

## Инструкции

1. **Прочитай** `.claude/docs/backend/pg-migrations/spec.md` (требования `pg-migrations/*`) и, для SQL-рецептов, `.claude/docs/backend/pg-migrations/references/recipes.md` и опционально `.claude/docs/backend/pg-runtime/spec.md` (для понимания, какие операции `ACCESS EXCLUSIVE` влияют на trafic).

2. **Уточни параметры:**
   - **Тип breaking change.** Самые частые:
     - `RENAME COLUMN` (`pg-migrations/rename-column-expand-contract`) — 3 фазы.
     - `DROP COLUMN` (`pg-migrations/drop-column-after-code`) — 2 фазы.
     - `ALTER TYPE` (`pg-migrations/alter-type-rewrites-table`) — 2-3 фазы (тип → теневая колонка → swap).
     - `ADD COLUMN NOT NULL` (`pg-migrations/add-column-not-null`/`pg-migrations/set-not-null-via-check`) — 1-2 фазы (зависит от PG-версии).
     - `ADD CONSTRAINT FK` (`pg-migrations/fk-not-valid-then-validate`) — 2 фазы (`NOT VALID` + `VALIDATE`).
     - `CREATE INDEX` (`pg-migrations/index-concurrently`) — 1 фаза (`CONCURRENTLY` обязательно).
     - `DROP / RENAME TABLE` (`pg-migrations/table-drop-after-release`) — после полного перехода на новое имя.
     - Удаление значения enum (`pg-migrations/enum-value-removal-via-shadow-type`) — теневой тип.
     - `SET NOT NULL` через `CHECK NOT VALID + VALIDATE + SET NOT NULL` (`pg-migrations/set-not-null-via-check`).
   - **Текущая версия PG.** PG12+ — больше «дешёвых» операций. PG11- — больше expand-contract.
   - **Размер таблицы / нагрузка.** Маленькая (< 100K строк, low traffic) → можно срезать углы (single-changeset). Большая → строго expand-contract.
   - **Связанный код.** Какая версия кода работает «с обеими формами»? Какая «только с новой»? Это деплой-план: миграция → код-1 → миграция → код-2 → миграция.

3. **Применяй expand-contract паттерн (`pg-migrations/expand-contract-three-releases`):**

   **Phase 1 — EXPAND:** добавить новое, оставить старое. Старый код продолжает работать.

   **Phase 2 — MIGRATE:** код пишет в новое + старое (если нужно), читает уже из нового. Backfill в отдельном changeset (или background-job).

   **Phase 3 — CONTRACT:** удалить старое после полного перехода кода. Никто из живых сервисов не использует старую форму.

4. **Шаблоны для каждого случая.**

   ### 4.1. RENAME COLUMN (`old_name` → `new_name`)
   Нельзя одним коммитом без даунтайма. 3 фазы (`pg-migrations/rename-column-expand-contract`):

   **Phase 1 — добавить `new_name`, синхронизировать через trigger:**
   ```yaml
   - changeSet:
       id: <NNN>-rename-old-to-new-phase1-add-new
       author: <автор>
       changes:
         - addColumn:
             tableName: <table>
             columns:
               - column: { name: new_name, type: <type> }
         - sql:
             sql: |
               UPDATE <table> SET new_name = old_name;

               CREATE OR REPLACE FUNCTION <table>_sync_old_new() RETURNS trigger AS $$
               BEGIN
                 NEW.new_name = COALESCE(NEW.new_name, NEW.old_name);
                 NEW.old_name = COALESCE(NEW.old_name, NEW.new_name);
                 RETURN NEW;
               END; $$ LANGUAGE plpgsql;

               CREATE TRIGGER <table>_sync_old_new_trg
                 BEFORE INSERT OR UPDATE ON <table>
                 FOR EACH ROW EXECUTE FUNCTION <table>_sync_old_new();
   ```

   **Phase 2 — релиз кода, читающего/пишущего `new_name`. Trigger продолжает синхронизировать.**

   **Phase 3 — drop trigger + drop `old_name`:**
   ```yaml
   - changeSet:
       id: <NNN>-rename-old-to-new-phase3-contract
       changes:
         - sql:
             sql: |
               SET LOCAL lock_timeout = '3s';
               DROP TRIGGER <table>_sync_old_new_trg ON <table>;
               DROP FUNCTION <table>_sync_old_new();
         - dropColumn:
             tableName: <table>
             columnName: old_name
   ```

   ### 4.2. DROP COLUMN (`pg-migrations/drop-column-after-code`)
   Дёшев на стороне БД, но требует, чтобы вся версия кода уже не трогала колонку.

   **Phase 1 — релиз кода, которая не пишет/не читает колонку.**

   **Phase 2 — drop:**
   ```yaml
   - changeSet:
       id: <NNN>-drop-<column>
       changes:
         - sql:
             sql: SET LOCAL lock_timeout = '3s';
         - dropColumn:
             tableName: <table>
             columnName: <column>
   ```

   ### 4.3. ALTER TYPE (`pg-migrations/alter-type-rewrites-table`)
   `ALTER TYPE` переписывает всю таблицу под `ACCESS EXCLUSIVE`. Для большой таблицы — теневая колонка + swap.

   **Phase 1 — добавить shadow-колонку, копировать batched:**
   ```yaml
   - changeSet:
       id: <NNN>-alter-type-phase1-shadow
       changes:
         - addColumn:
             tableName: <table>
             columns:
               - column: { name: <col>_v2, type: <newType> }
         # Backfill в отдельном changeset или job — небольшими батчами:
         # UPDATE <table> SET <col>_v2 = <col>::<newType> WHERE id BETWEEN ? AND ?;
   ```

   **Phase 2 — код пишет в обе колонки, читает из новой.**

   **Phase 3 — swap имён, drop старой:**
   ```yaml
   - changeSet:
       id: <NNN>-alter-type-phase3-swap
       changes:
         - sql:
             sql: |
               SET LOCAL lock_timeout = '3s';
               ALTER TABLE <table> RENAME COLUMN <col> TO <col>_old;
               ALTER TABLE <table> RENAME COLUMN <col>_v2 TO <col>;
         - dropColumn:
             tableName: <table>
             columnName: <col>_old
   ```

   ### 4.4. ADD CONSTRAINT FK (`pg-migrations/fk-not-valid-then-validate`)
   `ADD CONSTRAINT ... NOT VALID` (мгновенно) + `VALIDATE` (медленно, без блокировки писателей):

   ```yaml
   - changeSet:
       id: <NNN>-add-fk-phase1-not-valid
       changes:
         - sql:
             sql: |
               SET LOCAL lock_timeout = '3s';
               ALTER TABLE <child>
                 ADD CONSTRAINT <child>_<parent>_fk
                 FOREIGN KEY (<parent>_id) REFERENCES <parent> (id)
                 NOT VALID;

   - changeSet:
       id: <NNN>-add-fk-phase2-validate
       changes:
         - sql:
             sql: ALTER TABLE <child> VALIDATE CONSTRAINT <child>_<parent>_fk;
   ```

   ### 4.5. SET NOT NULL (`pg-migrations/set-not-null-via-check`)
   PG12+ — через `CHECK NOT VALID + VALIDATE + SET NOT NULL`:

   ```yaml
   - changeSet:
       id: <NNN>-set-not-null-phase1-check
       changes:
         - sql:
             sql: |
               SET LOCAL lock_timeout = '3s';
               ALTER TABLE <table>
                 ADD CONSTRAINT <table>_<col>_not_null_chk
                 CHECK (<col> IS NOT NULL) NOT VALID;

   - changeSet:
       id: <NNN>-set-not-null-phase2-validate
       changes:
         - sql:
             sql: ALTER TABLE <table> VALIDATE CONSTRAINT <table>_<col>_not_null_chk;

   - changeSet:
       id: <NNN>-set-not-null-phase3-promote
       changes:
         - sql:
             sql: |
               SET LOCAL lock_timeout = '3s';
               ALTER TABLE <table> ALTER COLUMN <col> SET NOT NULL;
               ALTER TABLE <table> DROP CONSTRAINT <table>_<col>_not_null_chk;
   ```

   ### 4.6. CREATE INDEX (`pg-migrations/index-concurrently`)
   В продакшене — **всегда** `CONCURRENTLY`:

   ```yaml
   - changeSet:
       id: <NNN>-create-index-<col>
       runInTransaction: false   # CONCURRENTLY несовместим с tx
       changes:
         - sql:
             sql: CREATE INDEX CONCURRENTLY <table>_<col>_idx ON <table> (<col>);
   ```

   После — `VACUUM` для visibility map (`pg-runtime/vacuum-analyze-after-bulk-change`):
   ```yaml
   - changeSet:
       id: <NNN>-vacuum-after-index
       runInTransaction: false
       changes:
         - sql:
             sql: VACUUM <table>;
   ```

   ### 4.7. Удаление значения enum (`pg-migrations/enum-value-removal-via-shadow-type`)
   Нативно невозможно. Через теневой тип:

   ```yaml
   - changeSet:
       id: <NNN>-remove-enum-value-phase1-shadow-type
       changes:
         - sql:
             sql: |
               CREATE TYPE <enum>_v2 AS ENUM ('VAL1', 'VAL2');  -- без удаляемого 'VAL3'

               ALTER TABLE <table>
                 ADD COLUMN status_v2 <enum>_v2;

               UPDATE <table> SET status_v2 = status::text::<enum>_v2
                 WHERE status::text != 'VAL3';
               -- строки с VAL3 — обработать отдельно (миграция данных)

   # Phase 2 — релиз кода
   # Phase 3 — swap (как в 4.3)
   # Phase 4 — DROP TYPE <enum>; ALTER TYPE <enum>_v2 RENAME TO <enum>
   ```

5. **Решения по lock_timeout:**
   - Каждый changeset с `ALTER TABLE` имеет `SET LOCAL lock_timeout = '3s'` (`pg-migrations/lock-timeout-required`). Если не получили лок за 3s — миграция fail-fast, не блокирует traffic.
   - Для `CREATE INDEX CONCURRENTLY` — `lock_timeout` не нужен (CONCURRENTLY не берёт ACCESS EXCLUSIVE).

6. **N-1 совместимость (`pg-migrations/n-minus-one-compatibility`):**
   - Каждая phase должна работать с **двумя версиями** кода: предыдущей и текущей.
   - Если миграция требует «код v2 уже зарелижен» — это explicit release-gate в комментарии changeset'а.

7. **Самопроверка:**
   - Каждый breaking change разбит на ≥2 фазы.
   - `lock_timeout = '3s'` (или меньше для критичных) во всех `ALTER TABLE`.
   - `CONCURRENTLY` для `CREATE INDEX` / `DROP INDEX` в проде, `runInTransaction: false`.
   - `ADD CONSTRAINT FK NOT VALID` + отдельный `VALIDATE`, не одной операцией.
   - `SET NOT NULL` — через `CHECK NOT VALID + VALIDATE + SET NOT NULL`, не напрямую (для PG12+).
   - Между phase'ами есть deploy-gate — комментарий в changeset «Phase 2: deploy code-version Y first».
   - `UPDATE` миллионов строк — выделен в отдельный backfill-job, не миграция.
   - `ALTER TYPE` на большой таблице — через теневую колонку, не напрямую.
   - Удаление значения enum — через теневой тип, не `DROP VALUE` (его нет).
   - `down`-миграции **не пишутся** для phase 3 (нечего откатывать; rollback стратегия — forward fix).

8. **Вывод** — по общему правилу: размер ответа равен размеру вопроса; решения и затронутые файлы — всегда, полные файлы — только когда просят сгенерировать; ревью — по запросу, не автоматически.

## Что НЕ делает

- Не пишет `CREATE TABLE` для нового агрегата — это `ucp-pg-schema-design`.
- Не пишет backfill-job (UPDATE миллионов строк) — это отдельный Java-код, координирует `ucp-pattern-design`.
- Не модифицирует доменные классы / репозитории — это `ucp-ddd-tactical-design` / `ucp-jooq-design`.
- Не делает `down` rollback'и — `pg-migrations/no-down-migrations`: forward fix, не rollback (на проде rollback миграции почти всегда не работает).

После каждой фазы — обязательно `ucp-pg-migration-review` для проверки lock-safety и expand-contract.

$ARGUMENTS
