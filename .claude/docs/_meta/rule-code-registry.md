# Rule-Code Registry — реестр префиксов правил

Единый источник правды: какой префикс — общий (язык-нейтральный, один на все языки) и какой —
языко-специфичный. Новый код — **сначала запись здесь**, потом использование (см. `authoring-contract.md` §5).

Scope:
- **shared** — код означает одно на всех языках; меняется только реализация в `<concern>/<lang>/<concern>-style-guide.md`.
- **java** / **python** — языко-специфичный concern, у каждого языка своя пара гайдов.
- **meta** — про сам процесс/формат, вне языков.

| Префикс | Concern | Scope | Статус генерализации |
|---|---|---|---|
| `R-API-*` | rest-api (URL/MTH/RSP/ERR/OAS) | shared | ✅ генерализован (java + python) |
| `R-UC-*` / `R-HND-*` / `R-LAY-*` | usecase-pattern | shared | ✅ генерализован (java + python) |
| `R-ENT-*` / `R-AGG-*` / `R-VO-*` / `R-EVT-*` / `R-REP-*` / `R-DS-*` / `R-FAC-*` / `R-SPEC-*` / `R-MOD-*` | ddd-tactical | shared | ✅ генерализован (java + python) |
| `R-ERR-*` | error-handling | shared | **✅ генерализован (пилот)** |
| `R-VLD-*` | validation | shared | ✅ генерализован (java + python) |
| `R-CACHE-*` | caching | shared | ✅ генерализован (java + python) |
| `R-RES-*` | resilience | shared | ✅ генерализован (java + python) |
| `R-KFK-*` | kafka | shared | ✅ генерализован (java + python) |
| `R-OBS-*` | observability | shared | ✅ генерализован (java + python) |
| `R-CQRS-*` | cqrs | shared | ✅ генерализован (java + python) |
| `R-DIST-*` | distributed-patterns | shared | ✅ генерализован (java + python) |
| `R-HEX-*` | hexagonal | shared (концепт) | ✅ генерализован (java + python) |
| `R-ARCH-*` | arch (платформа) | shared | язык-нейтрален |
| `R-SHUT-*` | graceful-shutdown | shared (интент; k8s-часть нейтральна) | ✅ генерализован (java + python) |
| `R-SEC-*` | security (принципы) | shared | ✅ генерализован (java + python) |
| `AUTH-*` | auth-patterns | shared (интент) | ✅ генерализован (java + python) |
| `PG-T/N/I/E/P/M/W/V/L/CP/IS-*` | pg-* (сам PostgreSQL) | shared | нейтрален (инструмент миграций — в style-guide) |
| `RFF-*` | review-finding-format | meta | нейтрален |
| `R-META-*` | authoring-contract (LAYOUT/FMT/LANG/CODE/SKILL/TIER) | meta | нейтрален |
| `JS-*` | java-style | java | — |
| `BS-*` | spring-bootstrap | java | — |
| `R-JOOQ-*` | jooq (persistence) | java | — |
| `TS-*` | test-strategy (JUnit+Testcontainers) | java | — |
| `PY-*` | python-style (ruff/black/mypy) | python | реализован (rules + review) |
| `R-SQLA-*` | sqlalchemy (persistence) | python | реализован (rules + design/review) |
| `PYBOOT-*` | python-bootstrap (FastAPI/uv/pydantic-settings) | python | реализован (rules + design/review) |
| `PYTS-*` | python test-strategy (pytest+testcontainers) | python | реализован (rules + design/review) |
| `NODE-*` | node-style (eslint/prettier/tsconfig strict) | node | зарезервирован |
| `R-TYPEORM-*` | persistence (TypeORM; Prisma — альт.) | node | зарезервирован |
| `NESTBOOT-*` | nest-bootstrap (NestJS modules/config/DI) | node | зарезервирован |
| `NODETEST-*` | node test-strategy (jest/vitest + testcontainers-node) | node | зарезервирован |
| `GO-*` | go-style (gofmt/golangci-lint: errcheck/errorlint/...) | go | зарезервирован |
| `R-SQLC-*` | persistence (sqlc; pgx/squirrel — альт.) | go | зарезервирован |
| `GOBOOT-*` | go-bootstrap (net/http+chi, config, graceful) | go | зарезервирован |
| `GOTEST-*` | go test-strategy (testing + testcontainers-go) | go | зарезервирован |
| `FE-CMP-*` | frontend components (React+TS) | frontend | каркас (эталон наполнен) |
| `FE-ST-*` | frontend state | frontend | каркас (stub) |
| `FE-DATA-*` | frontend data-fetching | frontend | каркас (stub) |
| `FE-FORM-*` | frontend forms | frontend | каркас (stub) |
| `FE-RT-*` | frontend routing | frontend | каркас (stub) |
| `FE-STY-*` | frontend styling/design-system | frontend | каркас (stub) |
| `FE-A11Y-*` | frontend accessibility | frontend | каркас (stub) |
| `FE-TEST-*` | frontend test (Vitest+Testing Library) | frontend | каркас (stub) |
| `FE-STYLE-*` | frontend code style (eslint/prettier/tsconfig) | frontend | каркас (stub) |

## Классификация concern'ов (kind: NEUTRAL / IMPL-SHAPED / LANG-SPECIFIC)

Задаёт, сколько живёт в shared-слое и как строго держать нейтральность (см. `authoring-contract.md` §11).
Граница нейтральности shared-индексов enforced машинно: `_meta/check-shared-neutral.py` (D).

| Kind | Concern'ы |
|---|---|
| **NEUTRAL** (полный нейтральный shared-индекс) | usecase-pattern, ddd-tactical, cqrs, distributed-patterns, rest-api, error-handling, validation, pg-* (типы/именование/индексы/миграции/runtime), arch |
| **IMPL-SHAPED** (тонкие принципы в shared, механизм/тюнинг в биндинге) | resilience, kafka, caching, observability, graceful-shutdown, hexagonal, auth-patterns, security |
| **LANG-SPECIFIC** (нет shared-слоя) | `backend/java/`: jooq, java-style, spring-bootstrap, test-strategy · `backend/python/`: sqlalchemy, python-style, python-bootstrap, python-test-strategy |

## Ось специализации (track)

Вторая ось, ортогональная языку (см. `authoring-contract.md` §10). Все префиксы выше — **backend-трек**
(implicit-default). Новые специализации резервируют свой префикс здесь до использования.

| Track | Concern-набор (черновик) | Стек | Префикс | Статус |
|---|---|---|---|---|
| `backend` | usecase-pattern, ddd, cqrs, kafka, … (всё выше) | java/python/node/go | (без track-токена) | инкумбент |
| `frontend` | component, state, data-fetching, forms, a11y, styling, routing, bundling, fe-test | React + TS | `FE-*` | зарезервирован |
| `e2e` | journeys, fixtures, network-mock, ci, flakiness (API-e2e + UI-e2e) | Playwright | `E2E-*` | зарезервирован |
| `any` | spec, arch, meta, review-finding-format, new-service | — | (свои: `R-ARCH-*`, `RFF-*`) | кросс-трековое ядро |

Дальше — `mobile`/`data`/`infra` по рецепту `authoring-contract.md` §10. Скиллы: `ucp-fe-*` / `ucp-e2e-*`.

**Замечание по «flavored».** Большинство shared-индексов сейчас содержат Java-флейвор в формулировках
(annotations в скобках). При добавлении Python-реализации соответствующий `<concern>-rules.md`
генерализуется (как сделано для `error-handling`) — framework-токены уходят в per-language style-guide,
коды и интент остаются. Это разовая работа на concern в момент, когда к нему добавляют второй язык.
