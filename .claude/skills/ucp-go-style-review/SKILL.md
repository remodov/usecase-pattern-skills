---
name: ucp-go-style-review
lang: go
description: Ревью Go-исходников по требованиям `go-style/*` — нейминг, пакеты/импорты, управляющие структуры, контекст, конкурентность, типы/интерфейсы, тесты + golangci-lint; chi/sqlc/pgx/slog/gobreaker/validator.
when_to_use: Ревью PR, перед коммитом, онбординг модуля; изменённые .go в git diff.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Go-стиля (gofmt / golangci-lint)

Ты ревьюишь Go-исходники на соответствие `backend/go/go-style/spec.md` (`GO-*`). Скилл намеренно
узкий — только **стиль** (нейминг, пакеты, управляющие структуры, контекст, конкурентность, типы, тесты,
форматирование, комментарии). Архитектура, DDD-инварианты, Use Case Pattern, валидация — другие скиллы.

## Зависимости

- **`.claude/docs/backend/go/go-style/spec.md`** — правила `GO-*` (код-примеры включены).
- `shared/review-format/spec.md` (`review-format/*`). Связанные коды для cross-ref: `error-handling/catch-does-not-swallow` (проглоченные ошибки), `hexagonal/outbound-port-interface-in-core` (интерфейс-порт), `GO-5.*` (ошибки-значения — если нарушение граничит со стилем).

## Инструкции

1. **Прочти** `go-style/spec.md`. Цитируй конкретные коды (`go-style/naming-conventions`, `go-style/loops-have-exit-condition`), не префикс. Гайд обязателен,
   кроме явного `go-style/idiomatic-over-clever` (нарушение улучшает читаемость или производительность) — тогда автор обосновывает в PR.

2. **Скоп.** Если пользователь назвал файлы — бери их. Иначе `git diff` (working tree/staged/last commit) на `.go`.
   По умолчанию — изменённые строки; нарушения в окружении — как **Замечание**.

3. **Прогон.**

   - **Общие принципы (`GO-1.*`):** `gofmt`/`goimports` запущены (`go-style/formatting-and-lint-enforced`); `golangci-lint` зелёный (`go-style/formatting-and-lint-enforced`);
     публичный символ без doc-комментария (`go-style/doc-comments-on-exported-only`); внутренний `//`-комментарий или закомментированный код
     (`go-style/doc-comments-on-exported-only`).

   - **Именование (`GO-2.*`):** пакет `lowercase` одно слово = имя директории (`go-style/naming-conventions`); экспортируемые —
     `MixedCaps`, неэкспортируемые — `mixedCaps` (`go-style/naming-conventions`); аббревиатуры целиком заглавные или строчные
     (`userID`, `HTTPClient`) — нарушение `go-style/naming-conventions`; интерфейс с одним методом → `<Method>er` (`go-style/naming-conventions`);
     конструктор `New<Type>` / `new<Type>` (`go-style/naming-conventions`); булевые `isX`/`hasX`/`canX`/`ok` (`go-style/naming-conventions`); имена
     тестов `TestFuncName_WhenCondition_ExpectedBehavior` (`go-style/test-naming`). Пакет `util`/`helper`/`common` →
     `go-style/packages-have-purpose`. Тип в имени метода: `order.OrderCreate` → `order.Create` (`go-style/packages-have-purpose`).

   - **Пакеты и импорты (`GO-3.*`):** `goimports`-группировка stdlib/внешние/internal (`go-style/imports-are-grouped-and-explicit`); dot-импорт
     (`go-style/imports-are-grouped-and-explicit`); blank-импорт вне `main`/`init` без тега (`go-style/imports-are-grouped-and-explicit`); нарушение барьера `internal/` (`go-style/internal-packages-are-a-barrier`);
     пакет-«бог» >500 строк без роли (`go-style/packages-have-purpose`). Циклические зависимости → `go-style/internal-packages-are-a-barrier`.

   - **Управляющие структуры (`GO-4.*`):** guard clause (ранний `return err`), уровень вложенности ≤ 3
     (`go-style/control-flow-stays-flat`); `switch` без `default` вне exhaustive-enum (`go-style/control-flow-stays-flat`); горутина без `WaitGroup`/`errgroup`
     (`go-style/goroutines-are-owned`); `defer` после `Open`/`Lock`/`Begin`, не в ветви `if` (`go-style/control-flow-stays-flat`); функция > 40 строк
     (`go-style/control-flow-stays-flat`); бизнес-логика в `init()` (`go-style/init-only-for-registration`). Горутина без `case <-ctx.Done()` → `go-style/loops-have-exit-condition`. Захват
     переменной цикла в горутину (`for i := 0; ...`) → `go-style/no-loop-variable-capture`.

   - **Обработка ошибок-значений (`GO-5.*`):** `errors.As`/`errors.Is` вместо прямого сравнения (`go-style/errors-are-values-and-checked`);
     проверка каждого `error` явно (`go-style/errors-are-values-and-checked`); доменная ошибка — типизированная структура с `Kind() apperr.Kind`
     (`go-style/domain-errors-are-typed`); `panic` только для невосстановимого программистского сбоя (`go-style/no-panic-as-control-flow`); единственный `recover()` —
     в edge-middleware (`go-style/no-panic-as-control-flow`); `errorlint` зелёный (`go-style/errors-are-values-and-checked`). `fmt.Errorf("%v", err)` вместо `%w` →
     `go-style/errors-are-values-and-checked`. `return Struct{}, nil` при ошибке → `go-style/no-panic-as-control-flow`. `panic/recover` как control-flow → `go-style/no-panic-as-control-flow`.

   - **Контекст (`GO-6.*`):** `ctx` первым аргументом, не в поле структуры (`go-style/context-is-first-argument`/`go-style/context-is-first-argument`); `ctx`
     в каждый IO-вызов — pgx, HTTP-клиент, Kafka, Redis (`go-style/context-is-first-argument`); таймаут из конфига (`envconfig`) через
     `context.WithTimeout` в out-adapter (`go-style/timeouts-before-io`); в контексте только cross-cutting data (`go-style/context-carries-cross-cutting-data`);
     проверка `ctx.Err()` в долгих циклах (`go-style/long-loops-check-cancellation`). `context.Background()` внутри handler/usecase →
     `go-style/context-is-first-argument`.

   - **Конкурентность (`GO-7.*`):** горутина завершается при shutdown через `ctx`-отмену или `close(stopCh)`
     (`go-style/goroutines-are-owned`); `sync.Mutex`/`RWMutex` для разделяемого состояния (`go-style/concurrency-primitives`); каналы для передачи владения
     (`go-style/concurrency-primitives`); `errgroup` вместо ручного `WaitGroup` для fan-out (`go-style/concurrency-primitives`); `semaphore` для булкхеда
     (`go-style/concurrency-primitives`); `go test -race` в CI (`go-style/race-detector-in-ci`). Горутина без механизма ожидания → `go-style/goroutines-are-owned`. Запись в
     закрытый канал → `go-style/only-sender-closes-channel`.

   - **Форматирование (`GO-8.*`):** `gofmt`/`goimports` обязательны, CI блокирует (`go-style/formatting-and-lint-enforced`); строка
     100–120 символов (`go-style/formatting-conventions`); множественное присваивание только для связанных значений (`go-style/formatting-conventions`);
     одна пустая строка между логическими блоками, не более одной подряд (`go-style/formatting-conventions`); `const` блок для
     перечислений, `iota` внутри одного блока (`go-style/formatting-conventions`). Горизонтальное выравнивание пробелами →
     `go-style/formatting-conventions`.

   - **Типы, структуры, интерфейсы (`GO-9.*`):** интерфейс 1–3 метода (`go-style/small-interfaces`); принимай интерфейс,
     возвращай конкретный тип (`go-style/small-interfaces`); embedding для переиспользования метода, не для наследования
     (`go-style/small-interfaces`); value objects без сеттеров, создаются через конструктор с валидацией (`go-style/value-types-are-precise`); деньги —
     `int64` (минорные единицы) или `shopspring/decimal`, **не `float64`** (`go-style/value-types-are-precise`); время — `time.Time`
     UTC внутри сервиса (`go-style/value-types-are-precise`). `any`/`interface{}` для обхода типизации → `go-style/no-empty-interface-or-alias`. `type Alias =
     Existing` ради переименования без поведения → `go-style/no-empty-interface-or-alias`.

   - **Тестирование (`GO-10.*`):** файлы `package order` (white-box) или `package order_test` (black-box),
     не смешивать (`go-style/tests-are-idiomatic`); `testify/require` для fatal-assert, `assert` для накапливающих (`go-style/tests-are-idiomatic`);
     `t.Parallel()` в unit-тестах без разделяемого состояния (`go-style/tests-are-idiomatic`); integration через
     `testcontainers-go` + `setupDB(t)` без глобального стейта (`go-style/tests-are-idiomatic`); table-driven tests с именованными
     case (`go-style/tests-are-idiomatic`); моки — интерфейсы от `mockery`, без бизнес-логики в моке (`go-style/tests-are-idiomatic`); `go test -race`
     в CI (`go-style/race-detector-in-ci`). `TestMain` с глобальным состоянием без очистки → `go-style/tests-avoid-sleep-and-shared-state`. `time.Sleep` для
     синхронизации горутин → `go-style/tests-avoid-sleep-and-shared-state`.

   - **Enforcement (`GO-LINT-*`):** `.golangci.yml` в корне с минимум `errcheck`/`errorlint`/`gocritic`/
     `revive`/`gosimple`/`staticcheck`/`unused`/`lll` (`go-style/lint-config-is-mandatory`); `//nolint:<linter>` без обоснования →
     `go-style/lint-config-is-mandatory`. Глобальное `nolint:all` или отключение `errcheck` → `go-style/lint-config-is-mandatory`.

4. **Не дублируй golangci-lint.** Если в проекте есть `.golangci.yml` — упомяни в начале отчёта, что механика
   (форматирование, импорты, проглоченные ошибки) ловится им, и сосредоточься на семантике, требующей
   человеческого судьи: деньги в `float64` (`go-style/value-types-are-precise`), `context.Background()` в handler (`go-style/context-is-first-argument`),
   горутины без shutdown-сигнала (`go-style/goroutines-are-owned`), `panic` для бизнес-правила (`go-style/no-panic-as-control-flow`), doc-комментарии
   (`go-style/doc-comments-on-exported-only`), читаемость table-driven/моков.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — деньги в `float64` (`go-style/value-types-are-precise`), `context.Background()` в handler/usecase (`go-style/context-is-first-argument`),
     горутина без условия выхода / `ctx.Done()` (`go-style/loops-have-exit-condition`/`go-style/goroutines-are-owned`), `panic` для бизнес-правила
     (`go-style/no-panic-as-control-flow`), `fmt.Errorf("%v")` вместо `%w` (`go-style/errors-are-values-and-checked`), `return Struct{}, nil` при ошибке
     (`go-style/no-panic-as-control-flow`), `//nolint:all` или отключение `errcheck` (`go-style/lint-config-is-mandatory`).
   - **Предупреждение** — пакет `util`/`helper` (`go-style/packages-have-purpose`), `context.Context` в поле структуры
     (`go-style/context-is-first-argument`), `switch` без `default` (`go-style/control-flow-stays-flat`), dot-импорт (`go-style/imports-are-grouped-and-explicit`), `any` для обхода типизации
     (`go-style/no-empty-interface-or-alias`), `time.Sleep` в тесте (`go-style/tests-avoid-sleep-and-shared-state`), `//nolint` без обоснования (`go-style/lint-config-is-mandatory`), функция
     > 40 строк (`go-style/control-flow-stays-flat`), захват переменной цикла в горутину (`go-style/no-loop-variable-capture`).
   - **Замечание** — тип в имени метода (`go-style/packages-have-purpose`), embedding вместо явной делегации при неочевидности
     (`go-style/small-interfaces`), `WaitGroup` вместо `errgroup` для fan-out (`go-style/concurrency-primitives`), doc-комментарий пересказывает
     сигнатуру (`go-style/doc-comments-on-exported-only`), `t.Parallel()` пропущен в unit-тесте (`go-style/tests-are-idiomatic`).

## Что не входит

- Архитектура/слои — `ucp-go-pattern-review`. DDD-инварианты — `ucp-go-ddd-tactical-review`. Валидация входа — `ucp-go-validation-review`.
- Обработка ошибок (иерархия/handlers) — `ucp-go-error-handling-review`. Persistence/sqlc — `ucp-go-sqlc-review`.

$ARGUMENTS
