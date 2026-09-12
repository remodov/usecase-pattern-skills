---
name: ucp-go-cqrs-design
lang: go
description: Спроектировать CQRS-разделение в Go-сервисе (net/http + chi) по UCP (требования cqrs/*) — маркеры Command/Query (Уровень 2) или полный split (Уровень 3: ViewRepository+read-DTO), read-model через outbox+kafka-go, idempotent consumer, sqlc+pgx.
when_to_use: Триггеры — «CQRS для X», «read-модель Y», «вынести чтение в проекцию». При добавлении read-проекций в Go-сервисе.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# CQRS — проектирование (Go / net/http + chi)

Ты проектируешь CQRS по **контракту** `backend/cqrs/spec.md` (`R-CQRS-*`) и **Go-реализации** `backend/cqrs/references/go/implementation.md`.

## Инструкции

1. **Прочитай** требования `go-style/*`. Цитируй коды в обосновании, не в коде. Связанные: `backend/usecase-pattern/...` (`Command`/`Query`-маркеры, Handler), `backend/error-handling/references/go/implementation.md` (ошибки-значения, `apperr.Kind`+`errors.As`), `backend/caching/go/...` (go-redis при Redis read-model), kafka-биндинг (`segmentio/kafka-go`, outbox), `ddd-tactical` (агрегат на write-side).

2. **Реши уровень** (`R-CQRS-WHEN-*` / `R-CQRS-TIER-*`): Уровень 2 → lightweight (маркеры + `pgx.TxOptions{AccessMode: pgx.ReadOnly}`, один `<X>Repository`); Уровень 3 → отдельный `<X>ViewRepository`-интерфейс + read-DTO + sqlc-запросы под read; event-driven → денормализованная read-таблица или Redis + outbox. Не вводи полный split без доказанной read-нагрузки (`cqrs/lightweight-first-full-on-evidence`). Назови выбор явно.

3. **Command side** (`R-CQRS-CMD-*`): `struct`, реализует пустой интерфейс `cqrs.Command` с неэкспортируемым методом (пакетный замок); меняет **один** агрегат; handler: `BeginTx` → load → доменный метод → save → `Commit`; возвращает минимум (id/статус/`struct{}`), не read-DTO (`cqrs/command-returns-minimum`); ошибки агрегата — значения с `Kind() apperr.Domain`, `fmt.Errorf("...: %w", err)`.

4. **Query side** (`R-CQRS-QRY-*`): `struct`, реализует `cqrs.Query`; handler читает через `<X>ViewRepository`, read-only транзакция `pgx.TxOptions{AccessMode: pgx.ReadOnly}`, без `Commit`; read-DTO в `core/<bc>/dto/view/` — структура под UI/API, не агрегат; не вызывает доменные методы, не пишет (`cqrs/query-is-read-only`).

5. **Read-model** (`R-CQRS-RM-*` / `R-CQRS-SYNC-*`): денормализована, восстановима (отдельная CLI-команда rebuild); sync через **outbox + `segmentio/kafka-go`** в одну сторону; idempotent consumer — таблица `processed_event` или version-проверка в UPDATE; eventual consistency задекларируй в OpenAPI (`X-Data-Freshness: eventual`); read-your-writes при необходимости.

6. **sqlc** генерирует отдельные query-файлы под write (`<X>Repository`) и read (`<X>ViewRepository`); sqlc-структуры write-схемы не используй как event-payload (`cqrs/events-not-coupled-to-write-schema`) — явный event-struct с версионированием.

7. **Производи код** (полные `.go`-файлы, gofmt; без комментариев — соответствие выражается именами/типами/структурой; коды правил в комментариях не цитируй).

   ### 7.1 `core/cqrs/cqrs.go` — маркеры
   ```go
   package cqrs
   type Command interface{ isCommand() }
   type Query   interface{ isQuery()   }
   ```

   ### 7.2 Command-struct + Handler
   `struct` в `core/<bc>/command/`; `func (<T>) isCommand() {}`. Handler в `core/<bc>/handler/`: конструкторная DI (`func New<X>Handler(...) *<X>Handler`), зависимости — интерфейсы порта; транзакция pgx: `BeginTx` (rw) → load aggregate → доменный метод → save → outbox.Enqueue → `Commit`.

   ### 7.3 Query-struct + Handler + ViewRepository
   `struct` в `core/<bc>/query/`; `func (<T>) isQuery() {}`. Handler в `core/<bc>/handler/`: `BeginTx(pgx.TxOptions{AccessMode: pgx.ReadOnly})` → `<X>ViewRepository.<Method>` → read-DTO. ViewRepository-интерфейс в `core/<bc>/port/` (Уровень 3).

   ### 7.4 Read-DTO
   Экспортируемый `struct` в `core/<bc>/dto/view/`; поля — по контракту API, не по агрегату; `int64` для денег.

   ### 7.5 Outbox + idempotent consumer
   `adapters/out/outbox/` — `Enqueue(ctx, tx, evt)` INSERT в outbox-таблицу в той же pgx-транзакции command-handler. `adapters/in/kafka/` — consumer: unmarshal → check `processed_event` → `<X>SummaryRepository.Upsert` → INSERT processed_event → `Commit`.

   ### 7.6 chi-интеграция
   Контроллер в `edge/handler/` получает command/query по HTTP, вызывает handler, ошибки — `httperr.Write(w, r, err)` (маппит `apperr.Kind` в статус).

8. **Самопроверка** — пройдись по чеклисту из `backend/cqrs/references/go/implementation.md` §«Чеклист подключения к новому сервису (Go)». Предложи `ucp-go-cqrs-review`.

## Антипаттерны, которые НЕ генерировать

- Полный CQRS/разделение БД без боли (`R-CQRS-WHEN-X1/X2`); маркеры без enforcement — read-only tx или отдельный интерфейс (`cqrs/split-matches-maturity-level`).
- Read-DTO из command (`cqrs/command-returns-minimum`); SELECT «для чтения» в command-handler (`cqrs/command-handler-does-not-query`); несколько агрегатов в одном BeginTx без саги (`cqrs/command-changes-one-aggregate`).
- Write в query-handler (`cqrs/query-is-read-only`); загрузка агрегата целиком ради DTO (`cqrs/read-via-projection-not-aggregate`); агрегат наружу из query-handler (`cqrs/query-returns-read-model`).
- Синхронный INSERT read-model в command-транзакции (`cqrs/read-model-synced-by-events`); PG-триггеры (`cqrs/read-model-synced-by-events`); sqlc write-struct как event-payload (`cqrs/events-not-coupled-to-write-schema`); bidirectional sync (`cqrs/projection-has-no-logic-or-backflow`).
- `fmt.Errorf("...%v", err)` вместо `%w`; `_ = call()` / проглатывание ошибок; `panic` для бизнес-правила.

После работы скилла — обязательно `ucp-go-cqrs-review`.

$ARGUMENTS
