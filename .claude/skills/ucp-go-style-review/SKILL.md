---
name: ucp-go-style-review
lang: go
description: Ревью Go-исходников по UCP Go Style Guide (коды GO-*) — нейминг, пакеты/импорты, управляющие структуры, контекст, конкурентность, типы/интерфейсы, тесты + golangci-lint; chi/sqlc/pgx/slog/gobreaker/validator.
when_to_use: Ревью PR, перед коммитом, онбординг модуля; изменённые .go в git diff.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Go-стиля (gofmt / golangci-lint)

Ты ревьюишь Go-исходники на соответствие `backend/go/go-style/go-style-rules.md` (`GO-*`). Скилл намеренно
узкий — только **стиль** (нейминг, пакеты, управляющие структуры, контекст, конкурентность, типы, тесты,
форматирование, комментарии). Архитектура, DDD-инварианты, Use Case Pattern, валидация — другие скиллы.

## Зависимости

- **`.claude/docs/backend/go/go-style/go-style-rules.md`** — правила `GO-*` (код-примеры включены).
- `shared/review-finding-format.md` (`RFF-*`). Связанные коды для cross-ref: `R-ERR-WHERE-X1` (проглоченные ошибки), `R-HEX-3` (интерфейс-порт), `GO-5.*` (ошибки-значения — если нарушение граничит со стилем).

## Инструкции

1. **Прочти** `go-style-rules.md`. Цитируй конкретные коды (`GO-2.3`, `GO-4.X1`), не префикс. Гайд обязателен,
   кроме явного `GO-1.1` (нарушение улучшает читаемость или производительность) — тогда автор обосновывает в PR.

2. **Скоп.** Если пользователь назвал файлы — бери их. Иначе `git diff` (working tree/staged/last commit) на `.go`.
   По умолчанию — изменённые строки; нарушения в окружении — как **Замечание**.

3. **Прогон.**

   - **Общие принципы (`GO-1.*`):** `gofmt`/`goimports` запущены (`GO-1.2`); `golangci-lint` зелёный (`GO-1.3`);
     публичный символ без doc-комментария (`GO-1.4`); внутренний `//`-комментарий или закомментированный код
     (`GO-1.X1`).

   - **Именование (`GO-2.*`):** пакет `lowercase` одно слово = имя директории (`GO-2.1`); экспортируемые —
     `MixedCaps`, неэкспортируемые — `mixedCaps` (`GO-2.2`); аббревиатуры целиком заглавные или строчные
     (`userID`, `HTTPClient`) — нарушение `GO-2.3`; интерфейс с одним методом → `<Method>er` (`GO-2.4`);
     конструктор `New<Type>` / `new<Type>` (`GO-2.5`); булевые `isX`/`hasX`/`canX`/`ok` (`GO-2.6`); имена
     тестов `TestFuncName_WhenCondition_ExpectedBehavior` (`GO-2.7`). Пакет `util`/`helper`/`common` →
     `GO-2.X1`. Тип в имени метода: `order.OrderCreate` → `order.Create` (`GO-2.X2`).

   - **Пакеты и импорты (`GO-3.*`):** `goimports`-группировка stdlib/внешние/internal (`GO-3.1`); dot-импорт
     (`GO-3.2`); blank-импорт вне `main`/`init` без тега (`GO-3.3`); нарушение барьера `internal/` (`GO-3.4`);
     пакет-«бог» >500 строк без роли (`GO-3.5`). Циклические зависимости → `GO-3.X1`.

   - **Управляющие структуры (`GO-4.*`):** guard clause (ранний `return err`), уровень вложенности ≤ 3
     (`GO-4.1`); `switch` без `default` вне exhaustive-enum (`GO-4.2`); горутина без `WaitGroup`/`errgroup`
     (`GO-4.3`); `defer` после `Open`/`Lock`/`Begin`, не в ветви `if` (`GO-4.4`); функция > 40 строк
     (`GO-4.5`); бизнес-логика в `init()` (`GO-4.6`). Горутина без `case <-ctx.Done()` → `GO-4.X1`. Захват
     переменной цикла в горутину (`for i := 0; ...`) → `GO-4.X2`.

   - **Обработка ошибок-значений (`GO-5.*`):** `errors.As`/`errors.Is` вместо прямого сравнения (`GO-5.1`);
     проверка каждого `error` явно (`GO-5.2`); доменная ошибка — типизированная структура с `Kind() apperr.Kind`
     (`GO-5.3`); `panic` только для невосстановимого программистского сбоя (`GO-5.4`); единственный `recover()` —
     в edge-middleware (`GO-5.5`); `errorlint` зелёный (`GO-5.6`). `fmt.Errorf("%v", err)` вместо `%w` →
     `GO-5.X1`. `return Struct{}, nil` при ошибке → `GO-5.X2`. `panic/recover` как control-flow → `GO-5.X3`.

   - **Контекст (`GO-6.*`):** `ctx` первым аргументом, не в поле структуры (`GO-6.1`/`GO-6.X2`); `ctx`
     в каждый IO-вызов — pgx, HTTP-клиент, Kafka, Redis (`GO-6.2`); таймаут из конфига (`envconfig`) через
     `context.WithTimeout` в out-adapter (`GO-6.3`); в контексте только cross-cutting data (`GO-6.4`);
     проверка `ctx.Err()` в долгих циклах (`GO-6.5`). `context.Background()` внутри handler/usecase →
     `GO-6.X1`.

   - **Конкурентность (`GO-7.*`):** горутина завершается при shutdown через `ctx`-отмену или `close(stopCh)`
     (`GO-7.1`); `sync.Mutex`/`RWMutex` для разделяемого состояния (`GO-7.2`); каналы для передачи владения
     (`GO-7.3`); `errgroup` вместо ручного `WaitGroup` для fan-out (`GO-7.4`); `semaphore` для булкхеда
     (`GO-7.5`); `go test -race` в CI (`GO-7.6`). Горутина без механизма ожидания → `GO-7.X1`. Запись в
     закрытый канал → `GO-7.X2`.

   - **Форматирование (`GO-8.*`):** `gofmt`/`goimports` обязательны, CI блокирует (`GO-8.1`); строка
     100–120 символов (`GO-8.2`); множественное присваивание только для связанных значений (`GO-8.3`);
     одна пустая строка между логическими блоками, не более одной подряд (`GO-8.4`); `const` блок для
     перечислений, `iota` внутри одного блока (`GO-8.5`). Горизонтальное выравнивание пробелами →
     `GO-8.X1`.

   - **Типы, структуры, интерфейсы (`GO-9.*`):** интерфейс 1–3 метода (`GO-9.1`); принимай интерфейс,
     возвращай конкретный тип (`GO-9.2`); embedding для переиспользования метода, не для наследования
     (`GO-9.3`); value objects без сеттеров, создаются через конструктор с валидацией (`GO-9.4`); деньги —
     `int64` (минорные единицы) или `shopspring/decimal`, **не `float64`** (`GO-9.5`); время — `time.Time`
     UTC внутри сервиса (`GO-9.6`). `any`/`interface{}` для обхода типизации → `GO-9.X1`. `type Alias =
     Existing` ради переименования без поведения → `GO-9.X2`.

   - **Тестирование (`GO-10.*`):** файлы `package order` (white-box) или `package order_test` (black-box),
     не смешивать (`GO-10.1`); `testify/require` для fatal-assert, `assert` для накапливающих (`GO-10.2`);
     `t.Parallel()` в unit-тестах без разделяемого состояния (`GO-10.3`); integration через
     `testcontainers-go` + `setupDB(t)` без глобального стейта (`GO-10.4`); table-driven tests с именованными
     case (`GO-10.5`); моки — интерфейсы от `mockery`, без бизнес-логики в моке (`GO-10.6`); `go test -race`
     в CI (`GO-10.7`). `TestMain` с глобальным состоянием без очистки → `GO-10.X1`. `time.Sleep` для
     синхронизации горутин → `GO-10.X2`.

   - **Enforcement (`GO-LINT-*`):** `.golangci.yml` в корне с минимум `errcheck`/`errorlint`/`gocritic`/
     `revive`/`gosimple`/`staticcheck`/`unused`/`lll` (`GO-LINT-1`); `//nolint:<linter>` без обоснования →
     `GO-LINT-6`. Глобальное `nolint:all` или отключение `errcheck` → `GO-LINT-X1`.

4. **Не дублируй golangci-lint.** Если в проекте есть `.golangci.yml` — упомяни в начале отчёта, что механика
   (форматирование, импорты, проглоченные ошибки) ловится им, и сосредоточься на семантике, требующей
   человеческого судьи: деньги в `float64` (`GO-9.5`), `context.Background()` в handler (`GO-6.X1`),
   горутины без shutdown-сигнала (`GO-7.X1`), `panic` для бизнес-правила (`GO-5.4`), doc-комментарии
   (`GO-1.4`), читаемость table-driven/моков.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — деньги в `float64` (`GO-9.5`), `context.Background()` в handler/usecase (`GO-6.X1`),
     горутина без условия выхода / `ctx.Done()` (`GO-4.X1`/`GO-7.X1`), `panic` для бизнес-правила
     (`GO-5.4`), `fmt.Errorf("%v")` вместо `%w` (`GO-5.X1`), `return Struct{}, nil` при ошибке
     (`GO-5.X2`), `//nolint:all` или отключение `errcheck` (`GO-LINT-X1`).
   - **Предупреждение** — пакет `util`/`helper` (`GO-2.X1`), `context.Context` в поле структуры
     (`GO-6.X2`), `switch` без `default` (`GO-4.2`), dot-импорт (`GO-3.2`), `any` для обхода типизации
     (`GO-9.X1`), `time.Sleep` в тесте (`GO-10.X2`), `//nolint` без обоснования (`GO-LINT-6`), функция
     > 40 строк (`GO-4.5`), захват переменной цикла в горутину (`GO-4.X2`).
   - **Замечание** — тип в имени метода (`GO-2.X2`), embedding вместо явной делегации при неочевидности
     (`GO-9.3`), `WaitGroup` вместо `errgroup` для fan-out (`GO-7.4`), doc-комментарий пересказывает
     сигнатуру (`GO-1.4`), `t.Parallel()` пропущен в unit-тесте (`GO-10.3`).

## Что не входит

- Архитектура/слои — `ucp-go-pattern-review`. DDD-инварианты — `ucp-go-ddd-tactical-review`. Валидация входа — `ucp-go-validation-review`.
- Обработка ошибок (иерархия/handlers) — `ucp-go-error-handling-review`. Persistence/sqlc — `ucp-go-sqlc-review`.

$ARGUMENTS
