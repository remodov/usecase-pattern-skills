# Error Handling — индекс правил (язык-нейтральный)

> **Что это.** Сжатый индекс правил error-handling: код + интент, по разделам — **общий контракт для всех языков**.
> Рабочий вход скиллов: review цитирует код в findings, design сверяется по чек-листу.
> **Реализация по языкам** (примеры кода, framework-специфика, обоснование) — в
> `java/error-handling-style-guide.md` (Spring) и `python/error-handling-style-guide.md` (FastAPI);
> открывай нужный точечно по разделу.
> Коды: `R-ERR-<GROUP>-<N>` — обязательно, `R-ERR-<GROUP>-X<N>` — антипаттерн (запрещено). **Коды общие для всех языков** — меняется только реализация.
> Сшивает: REST-формат (`R-API-ERR-*`), валидация (`R-VLD-*`), резилианс (`R-RES-*`), security (`AUTH-6`/`AUTH-18`/`AUTH-19`), observability (`R-OBS-*`).

**MUST:**
- **R-ERR-1.** Исключение — часть контракта, не неожиданность: каждое в публичной сигнатуре имеет тип, документированный смысл, однозначный handler. «Поймать всё → залогировать → вернуть пустоту» (`catch(Exception)→log→return null` / `except Exception: return None`) — главный антипаттерн гайда.
- **R-ERR-2.** Только три места catch: **edge** (HTTP exception-handler / message-consumer error-handler / scheduler-обёртка), **integration boundary** (out-adapter ловит низкоуровневые ошибки клиента → port-specific exception), **резильянс-обёртка** (circuit breaker / retry / bulkhead — формальный catch конфигом/декоратором). Везде ещё — никаких try/except, доменное исключение проходит насквозь до edge.

## 1. Иерархия исключений
**MUST:**
- **R-ERR-HIER-1.** 4 базовых типа: **Domain** (409/422, no-retry), **Validation** (400, no-retry), **Integration** (502/503/504, retry-safe), **Technical** (500, retry-возможно). Domain — в доменном слое (`core`), Integration — в каждом out-adapter, Validation — на edge.
- **R-ERR-HIER-2.** Все четыре наследуют один корневой app-exception, а не «голый» базовый класс языка; checked-exceptions (где есть) не используются — тип не должен теряться в сигнатурах.
- **R-ERR-HIER-3.** Доменные исключения именуются по бизнес-смыслу (`OrderAlreadyShipped…`), не по техническому формату (`BusinessError`, `IllegalState…`).
- **R-ERR-HIER-4.** Integration-наследники с префиксом системы (`PaymentGateway…`, `CatalogPort…`) — edge различает «у платёжки» vs «у каталога».
- **R-ERR-HIER-5.** Конструкторы фиксируют контекст обязательно (`InsufficientFunds(customerId, requested, available)`), не пустые; поля доступны для маппинга в response.

**MUST NOT:**
- **R-ERR-HIER-X1.** Бросать «голый» базовый exception (`raise Exception("...")` / `throw new RuntimeException("...")`) — тип теряется; кидать конкретный наследник.
- **R-ERR-HIER-X2.** Бросать «программистскую» ошибку (`IllegalState`/`assert`/`AssertionError`) в доменном коде как бизнес-правило: бизнес-правило → Domain-исключение, нарушение инварианта агрегата → ловит unit-тест, не endpoint.

## 2. Где throw, где catch
**MUST:**
- **R-ERR-WHERE-1.** Throw — везде где нужно (domain handler → Domain, validator → Validation, out-adapter → Integration); не накручивать `Result`/either везде ради избежания исключений.
- **R-ERR-WHERE-2.** Catch только в трёх местах (см. `R-ERR-2`): один глобальный edge-handler с per-type обработчиками + catch-all; out-adapter мапит низкоуровневые в port-specific; резильянс-обёртки.
- **R-ERR-WHERE-3.** В UseCase Handler / Domain Service / Aggregate — ноль try/except.

**MUST NOT:**
- **R-ERR-WHERE-X1.** `catch/except (широкий тип) { log; }` в handler/service — глушит, теряет тип, возвращает «успех». Главный силент-фейл.
- **R-ERR-WHERE-X2.** Перехват и переброс в «голом» базовом типе (`raise RuntimeError(e)` / `throw new RuntimeException(e)`) — теряется тип, edge отдаёт 500 на всё; оборачивать в типизированный наследник.
- **R-ERR-WHERE-X3.** `catch/except → вернуть пустоту` (`None` / `Optional.empty()` / `null`) — скрывает проблему ещё глубже.

## 3. Mapping в problem+json (RFC 9457, `application/problem+json`)
**MUST:**
- **R-ERR-MAP-1.** Domain → 409 (нарушение текущего состояния) / 422 (нарушение инвариантов); `type` = URL на код ошибки в `docs/spec/errors/`; контекст через extension-поля + `traceId`.
- **R-ERR-MAP-2.** Validation → 400 с `errors`-массивом per-field; ошибки валидатора (фреймворк-валидации / Pydantic) приводить к этой же форме на edge.
- **R-ERR-MAP-3.** Integration → 502 (внешка 5xx с телом) / 503 (CB открыт или bulkhead reject) / 504 (timeout); сырое тело внешки в `detail` не вкладывать (PII) — фраза + `traceId`.
- **R-ERR-MAP-4.** Technical → 500, минимум в response («Internal Server Error» + traceId), детали в логи (`AUTH-18`).
- **R-ERR-MAP-5.** Catch-all → 500, ERROR-лог + полный stacktrace + контекст; сигнал бага — создавать issue.

**MUST NOT:**
- **R-ERR-MAP-X1.** HTTP 200 при ошибке с `{"success": false}` в body — мониторинг прозевает (всё не-4xx/5xx считается успехом).
- **R-ERR-MAP-X2.** stacktrace в `detail`-поле — утечка классов/версий/paths; только в логи.
- **R-ERR-MAP-X3.** Сообщение исключения как `detail` без санитизации (`relation "order_doc" does not exist`) — раскрытие схемы БД.

## 4. Логирование исключений
**MUST:**
- **R-ERR-LOG-1.** Domain — `WARN` в edge-handler (ожидаемая ошибка, не баг; ERROR создаст false-positive алёрты).
- **R-ERR-LOG-2.** Integration — `WARN` если CB закрыт (одиночный fail), `ERROR` если CB открылся (инцидент).
- **R-ERR-LOG-3.** Technical и catch-all — `ERROR` + полный stacktrace + контекст (request-id, customer-id, operation).
- **R-ERR-LOG-4.** Логируем один раз — на edge-handler, не на каждом уровне call stack.

**MUST NOT:**
- **R-ERR-LOG-X1.** Залогировать и тут же пробросить (`log.error(...); raise/throw`) — двойное логирование; либо логируй и обработай, либо проброс.
- **R-ERR-LOG-X2.** Логировать только текст ошибки без объекта exception — теряется stacktrace; передавать исключение в логгер (`logger.exception(...)` / `log.error(msg, e)`).

## 5. Retry / no-retry семантика
**MUST:**
- **R-ERR-RETRY-1.** По типу: Domain/Validation — никогда не retry; Integration — retry-safe при идемпотентности (`AUTH-19`); Technical — обычно retry после latency.
- **R-ERR-RETRY-2.** HTTP 4xx от внешней системы — не retry («послали некорректное»); → port-specific exception, edge отдаёт 422.
- **R-ERR-RETRY-3.** HTTP 5xx и timeout — retry-safe только при идемпотентности; без `Idempotency-Key` на write — `R-RES-RE-X1`, money может списаться дважды.

**MUST NOT:**
- **R-ERR-RETRY-X1.** Retry на edge-handler — он уже вне retry-цикла, повтор бессмысленен.

## 6. Result-types vs exceptions
**MUST:**
- **R-ERR-RESULT-1.** `Result`/either допустим точечно в чисто-функциональных модулях (парсер, calc engine), где ошибка семантически часть результата.
- **R-ERR-RESULT-2.** В цепочке UseCase Handler → Domain → Adapter — исключения, не Result (иначе каждый caller разбирает результат, ломает читаемость).

**MUST NOT:**
- **R-ERR-RESULT-X1.** Глобальная замена исключений на Result ради «type-safe error handling» — без полноценного pattern-matching вырождается в `if not result.ok: raise result.error`.

## 7. Observability
**MUST:**
- **R-ERR-OBS-1.** Метрика `app_errors_total{type=…,exception=…}` (Counter); `type` = domain/validation/integration/technical/unexpected, `exception` = имя класса.
- **R-ERR-OBS-2.** Trace span на исключение помечается `ERROR` (OTel `SpanStatus.ERROR` + record exception).
- **R-ERR-OBS-3.** Алёрты на необычные паттерны (рост `unexpected` → баг; `integration` → деградация внешки; `domain` для одного кода → изменилось бизнес-условие; `validation` рост → клиент сломал контракт), не на каждое исключение.

**MUST NOT:**
- **R-ERR-OBS-X1.** Алёрт «любое исключение в логах» — Domain нормально частая; алёртить только на `unexpected`/`technical`.
