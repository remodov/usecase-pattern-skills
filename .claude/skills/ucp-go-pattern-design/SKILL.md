---
name: ucp-go-pattern-design
lang: go
description: Спроектировать бизнес-операцию как UseCase + Handler в Go-сервисе (net/http + chi) по UCP (коды R-UC-*, R-HND-*, R-LAY-*) — Command[R]/Query[R]-маркеры, stateless Handler с UoW, Dispatcher реестр, тонкий chi-роутер, порты-интерфейс, sqlc-маппинг.
when_to_use: Триггеры — «добавь команду X в Go-сервисе», «новый UseCase на Go», «эндпоинт создания Y». При новом эндпоинте/команде/запросе в net/http+chi-сервисе.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Проектирование UseCase + Handler (Go / net/http + chi)

Ты проектируешь бизнес-операцию как **UseCase + Handler** согласно **общему контракту**
`backend/usecase-pattern/usecase-pattern-rules.md` (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`)
и его **Go-реализации** `backend/usecase-pattern/go/usecase-pattern-style-guide.md`
(net/http + chi + sqlc + pgx; ошибки-значения; конструкторная DI; dispatcher через `reflect.Type`).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/usecase-pattern/usecase-pattern-rules.md` — общий контракт, коды `R-*` (цитируй в design-обосновании, **не** в комментариях кода).
   - `.claude/docs/backend/usecase-pattern/go/usecase-pattern-style-guide.md` — Go-реализация (`Command[R]`/`Query[R]`, `Handler[UC, R]`, `UnitOfWork`, `Dispatcher`, явные маппинги, чеклист), открывай точечно по разделу.
   - На Уровне 3 — `.claude/docs/backend/ddd-tactical/ddd-tactical-rules.md` (домен, агрегаты).
   - Если есть новая таблица — `.claude/docs/backend/pg-types/pg-types-rules.md` (PostgreSQL-типы; язык-нейтрально).

2. **Идентифицируй сервис и слой.** Структура UCP на Go:
   `core/<bc>/` (usecases.go, *_handler.go, domain, port/), `adapters/in/http/` (chi-роутеры), `adapters/out/persistence/` (sqlc+pgx), `app/` (DI + dispatcher).

3. **Спроектируй операцию.** Для команды/запроса определи: имя (бизнес-операция), поля входа, тип результата `R`, Command или Query.

4. **Произведи код** (полные `.go`-файлы, gofmt; без комментариев — соответствие через имена/типы/структуру; коды правил в комментариях **не** цитируй).

   ### 4.1 UseCase — plain struct, маркер-интерфейс
   Имя по бизнес-операции; поля — только вход; без методов-логики (`R-UC-1..4`).
   Команда реализует `usecase.Command[R]` (приватный метод `commandResult() R`),
   запрос — `usecase.Query[R]` (`queryResult() R`). Пустой результат — отдельный тип `VoidResult{}` (`R-UC-X4`).

   ### 4.2 Handler — `*NameHandler` с `Handle(ctx, UC) (R, error)`
   Deps через конструктор `New*`; поля приватные, инициализируются один раз (`R-HND-5`).
   Граница транзакции на Handler: команда — `h.uow.Do(ctx, fn)` read-write,
   запрос — read-only (без UoW) (`R-HND-3`, `R-TX-1`).
   Один Handler — один UseCase (`R-HND-4`). Инфра-ошибки (`pgconn.PgError`, `net.Error`) маппятся
   в доменные в out-адаптере, **не** пробрасываются из Handler (`R-HND-X2`, cross-ref `error-handling/go`).

   ### 4.3 Регистрация в DI + Dispatcher
   `app/dispatcher/dispatcher.go` — реестр `reflect.Type → handlerFunc`. При конструкторной сборке
   в `app/di.go` вызываем `dispatcher.Register(d, New*Handler(...))` для каждого Handler-а (`R-HND-2`, `R-DSP-1/2`).
   Один Dispatcher на приложение. `google/wire` — опционально.

   ### 4.4 Тонкий chi-роутер
   `adapters/in/http/`: декодируем тело → UseCase (`UserID` из `auth.PrincipalFromCtx`, **не** из тела — `R-DSP-X2`)
   → `h.dispatcher.Dispatch(r.Context(), uc)` → Response + HTTP-код (`R-DSP-3`, `R-DSP-X1`).
   Ошибки — через `httperr.Write(w, r, err)` (cross-ref `error-handling/go`).

   ### 4.5 Слои моделей и порты
   API-DTO (`adapters/in/http/dto.go`) ≠ read-модель (`core/<bc>/views.go`) ≠ sqlc-struct (`db.*`);
   явный маппинг функциями (`adapters/out/persistence/*_mapper.go`) (`R-LAY-1/2/3`).
   Порты — интерфейсы в `core/<bc>/port/`; `core/` **не** импортирует `pgx`/`chi`/`kafka-go`/`go-redis`
   (`R-HEX-2/3`). Реализация pgx-репозитория и `PgxUnitOfWork` — в `adapters/out/persistence/`.

   ### 4.6 Step — переиспользуемая логика
   `core/usecase/step.go` — интерфейс `Step[I, O]` с методом `Execute`. Вводится только когда
   одна логика нужна ≥ 2 Handler-ам; Step stateless (`R-STEP-1/2`, `R-STEP-X1/X2`).

   ### 4.7 Публикация доменных событий (Уровень 3)
   После `repository.Save(ctx, aggregate)` внутри той же `UoW`-транзакции — `outbox.Publish(ctx, ev)`,
   затем `aggregate.ClearEvents()` (`R-TX-3`, cross-ref `distributed/go`).

5. **Самопроверка** — чеклист из `go/usecase-pattern-style-guide.md` §«Чеклист подключения к новому сервису (Go)».
   При наличии исходящих HTTP-вызовов — сверь с `error-handling/go` (маппинг интеграционных ошибок).

6. **Финальный шаг:** предложи «запусти `ucp-go-pattern-review`», а при добавлении обработки ошибок —
   `ucp-go-error-handling-design`; при новой схеме БД — `ucp-go-sqlc-design` (если есть).

## Антипаттерны, которые НЕ генерировать

- Логика в UseCase / mutable-поля/сеттеры (`R-UC-X1`, `R-UC-X3`); `VoidResult` пропущен (`R-UC-X4`).
- Handler зовёт Handler напрямую (`R-HND-X1`); `pgconn.PgError` / `net.Error` вылетают из Handler (`R-HND-X2`).
- Бизнес-логика в chi-хендлере (`R-DSP-X1`); `*http.Request` / `auth.Principal` в полях UseCase (`R-DSP-X2`).
- sqlc-struct (`db.Order`) уходит в JSON-ответ или в поля UseCase (`R-LAY-X1`).
- `import "github.com/jackc/pgx/v5"` или `import "github.com/go-chi/chi/v5"` в `core/` (`R-HEX-X1/X2`).
- `@Transactional`-аналог на репозитории вместо Handler; вложенные транзакции (`R-TX-1/2`).
- Step внутри Step / Step с состоянием (`R-STEP-X1`, `R-STEP-X2`).

После работы скилла — обязательно `ucp-go-pattern-review` для верификации.

$ARGUMENTS
