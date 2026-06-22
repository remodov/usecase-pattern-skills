---
name: ucp-go-hexagonal-design
lang: go
description: Сгенерировать или реструктурировать Go-сервис под Hexagonal Architecture (коды R-HEX-*) — core/adapter/bootstrap, архитектурный тест packages.Load, порты-interface в core/port/out/, chi-handler через UseCase Handler, sqlc+pgx, apperr.Kind+errors.As.
when_to_use: Старт сервиса Уровня 3 или upgrade 2→3 на Go. Триггеры — «hexagonal layout на Go», «реструктурируй под core/adapter», «добавь порты и адаптеры».
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Hexagonal Architecture — проектирование (Go / net/http + chi)

Ты генерируешь раскладку сервиса по **общему контракту** `backend/hexagonal/hexagonal-rules.md` (`R-HEX-*`) и
**Go-реализации** `backend/hexagonal/go/hexagonal-style-guide.md`. Изоляция границ — через архитектурный тест
(`packages.Load` + forbidden-imports), не compile-time Gradle-модули.

## Инструкции

1. **Прочитай** контракт `backend/hexagonal/hexagonal-rules.md` + Go style-guide. Коды `R-HEX-*` в design-обосновании, не в коде. Связанные: `backend/usecase-pattern/go/...` (UseCase/Handler), `backend/ddd-tactical/go/...` (домен в core/), `backend/error-handling/go/error-handling-style-guide.md` (apperr/Kind в port-ошибках), `backend/go/sqlc/sqlc-rules.md` (out-persistence при наличии).

2. **Реши уровень** (`R-HEX-WHEN-*`): Уровень 3 (DDD + ports/adapters) → полная раскладка; Уровень 1–2 → плоский `internal/<bc>/`, не плоди ceremony. Назови выбор в начале.

3. **Произведи дерево пакетов** (`R-HEX-MOD-*`):
   ```
   internal/
     core/<bc>/{aggregate,entity,value_object,event,port,usecase,service}/
     adapter/in/http/       # chi-роутеры + middleware (R-HEX-AIN)
     adapter/in/kafka/      # kafka-consumer (segmentio/kafka-go, отдельный пакет)
     adapter/out/persistence/  # sqlc + pgx (R-HEX-AOUT)
     adapter/out/<system>/  # HTTP-клиент к внешней системе (per-system)
   bootstrap/
     main.go                # composition root: wiring, chi.Router, http.Server
     config.go              # envconfig / os.Getenv
     architecture_test.go   # packages.Load forbidden-imports
     Dockerfile
   ```
   `core/` — без chi/pgx/kafka-go/redis/slog; стрелка `bootstrap → adapter/* → core`.

4. **Архитектурный тест** (`R-HEX-TEST-*`) — в Go нет ArchUnit; обязательный тест в `bootstrap/architecture_test.go` с тегом `//go:build arch`, использует `golang.org/x/tools/go/packages`. Проверяет: `core/` не импортирует forbidden-пакеты; `adapter/in/http/` не импортирует `adapter/out/*`; `adapter/out/<system>/` не импортирует другой `adapter/out/<other>/`. CI запускает как required check (`R-HEX-TEST-1/2`).

5. **Порты** (`R-HEX-PORT-*`) — `interface` в `core/<bc>/port/out/`, domain-типы в сигнатурах, port-ошибки с `apperr.Kind` в `core/`. **In-adapter** (`R-HEX-AIN-*`) — chi-handler → маппер → `UseCase Handler`; маппер `OrderRequestMapper` — отдельная структура в пакете адаптера. **Out-adapter** (`R-HEX-AOUT-*`) — реализует порт, compile-time assertion `var _ out.XxxPort = (*XxxAdapter)(nil)`, маппер domain↔system-DTO. **bootstrap/** (`R-HEX-BOOT-*`) — только wiring; конструкторы (`NewXxx`), не `init()`/глобальные синглтоны.

6. **Placeholder-файлы**: `bootstrap/main.go` (wiring + `http.Server` + `signal.NotifyContext`), `core/<bc>/aggregate/<name>.go` (rich-domain struct + методы), `core/<bc>/port/out/<port>.go` (interface + port-ошибки), `adapter/in/http/<handler>.go` (chi-handler + маппер), `adapter/out/persistence/<repo>.go` (sqlc + pgx). Самопроверка по §9 (чеклист из style-guide). Предложи `ucp-go-hexagonal-review`.

## Антипаттерны, которые НЕ генерировать

- Отсутствие архитектурного теста (`R-HEX-MOD-X1`, `R-HEX-TEST-X1`); `core/` импортит chi/pgx/kafka-go/redis (`R-HEX-CORE-X1/X2`); sqlc-generated struct как domain в core (`R-HEX-CORE-X4`); HTTP-DTO в core (`R-HEX-CORE-X5`).
- Interface `PaymentPort` объявлен в out-adapter (`R-HEX-PORT-X1`); DTO внешней системы в port-сигнатуре (`R-HEX-PORT-X2`); port как struct, не interface (`R-HEX-PORT-X4`).
- Handler зовёт репозиторий напрямую (`R-HEX-AIN-X2`); domain entity возвращается как HTTP-ответ без маппера (`R-HEX-AIN-X3`); `adapter/in/http/` импортирует `adapter/out/*` (`R-HEX-AIN-X4`).
- Бизнес-логика в out-adapter (`R-HEX-AOUT-X2`); один адаптер реализует несколько port'ов разных BC (`R-HEX-AOUT-X3`); адаптеры зависят друг от друга (`R-HEX-AOUT-X4`).
- Бизнес-логика или chi-handler'ы в `bootstrap/` (`R-HEX-BOOT-X1`); `init()` для wiring вместо конструкторов; `var db *pgx.Pool` глобально в core.

После работы скилла — обязательно `ucp-go-hexagonal-review`.

$ARGUMENTS
