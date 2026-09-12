---
name: ucp-node-hexagonal-review
lang: node
description: Ревью Hexagonal Architecture NestJS-сервиса — папки core/adapters/app, контракт dependency-cruiser, core без NestJS/TypeORM/class-validator, порты + Symbol-токены в core/<bc>/port, контроллеры через Dispatcher, app только композиция.
when_to_use: Ревью раскладки сервиса Уровня 3 — core/, adapters/, app/, конфиг dependency-cruiser.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(depcruise*)
---

# Ревью Hexagonal (Node / папки + dependency-cruiser)

Ты ревьюишь раскладку сервиса на соответствие **контракту** `backend/hexagonal/spec.md` (`R-HEX-*`) и
**Node-реализации** `backend/hexagonal/references/node/implementation.md`. Изоляция — через dependency-cruiser (или eslint-plugin-boundaries).

## Зависимости

- **`.claude/docs/backend/hexagonal/spec.md`** + **`backend/hexagonal/references/node/implementation.md`**.
- Парные: `backend/usecase-pattern/node/...` (`hexagonal/outbound-port-interface-in-core`/Dispatcher), `backend/ddd-tactical/node/...` (rich domain), `backend/node/typeorm/spec.md` (out-persistence), `backend/node/nest-bootstrap/spec.md` (`NESTBOOT-5/6/15`).

## Инструкции

0. **Проверь, что гейты, обещанные требованиями, включены.** Поле **Гейт** в `spec.md` называет механизм — убедись, что он есть в проекте: правила в `.dependency-cruiser.cjs` (или eslint-boundaries) и их прогон в CI. Обещанный, но не включённый гейт — **отдельная находка**, и она важнее отдельного нарушения: без него граница держится только на внимательности.
   Требования с гейтом `ревью` (богатый домен, адаптер мапит а не решает, раздельные in-adapter'ы по аудиториям) не поймает никто, кроме тебя — смотри их внимательнее остальных.

1. **Прочти** требования `node-style/*`. Цитируй коды (`hexagonal/core-free-of-framework`, `hexagonal/adapters-do-not-know-each-other`), не префикс.

2. **Скоп.** `src/{core,adapters,app}/**`, `.dependency-cruiser.cjs` (или eslint-boundaries-конфиг), `package.json`-скрипты, CI-конфиг, `git diff`.

3. **Прогон.**
   - **Структура (`R-HEX-MOD-*`):** дерево core/adapters/app; контракт dependency-cruiser present (`hexagonal/module-per-part` если нет); `core/` не импортит `adapters/*` (`hexagonal/core-free-of-framework`); user/admin-контроллеры разделены (`hexagonal/in-adapter-per-audience`).
   - **Core (`R-HEX-CORE-*`):** без `@nestjs/*` и NestJS-декораторов (`hexagonal/core-free-of-framework`, wiring — `useFactory` в `app/`)/TypeORM (`hexagonal/core-free-of-framework`)/class-validator-DTO (`hexagonal/no-generated-types-in-core`); TypeORM-Entity не используется как domain (`hexagonal/no-generated-types-in-core`); rich domain, не анемия (`hexagonal/rich-domain-model`).
   - **Ports (`R-HEX-PORT-*`):** интерфейс + Symbol-токен в `core/<bc>/port/out/`, domain-типы в сигнатурах; не в out-adapter (`hexagonal/outbound-port-interface-in-core`); не DTO внешней системы (`hexagonal/port-speaks-domain-types`); не `X | null` где отсутствие=ошибка (`hexagonal/absence-is-not-error`); не класс с реализацией (`hexagonal/outbound-port-interface-in-core`).
   - **In (`R-HEX-AIN-*`):** контроллер через `Dispatcher` (`hexagonal/controller-dispatches-only`), не возвращает domain наружу (`hexagonal/rest-mapping-in-adapter`), без бизнес-логики (`hexagonal/controller-dispatches-only`), не импортит `adapters/out/*` (`hexagonal/adapters-do-not-know-each-other`).
   - **Out (`R-HEX-AOUT-*`):** реализует порт и биндится на его токен, мапит domain↔DTO, per-system папка; не возвращает DTO внешней системы (`hexagonal/port-speaks-domain-types`), без бизнес-логики (`hexagonal/adapter-maps-not-decides`), не реализует порты разных доменов (`hexagonal/out-adapter-per-system`), не инжектит другой адаптер (`hexagonal/adapters-do-not-know-each-other`).
   - **app/ (`R-HEX-BOOT-*`):** только композиция/конфиг (`hexagonal/bootstrap-composition-only`); `NestFactory.create`/wiring не в core/adapters (`hexagonal/bootstrap-composition-only`); все порты забинжены (`hexagonal/composition-covers-all-adapters`).
   - **Тесты (`R-HEX-TEST-*`):** `depcruise --validate` (или eslint-boundaries) в CI как required check (`hexagonal/architecture-tests-required` если enforcement только через review); единый корень скана (`hexagonal/single-scan-root`).

4. **Cross-check:** домен/агрегаты — `ucp-node-ddd-tactical-review`; Dispatcher/граница TX — `ucp-node-pattern-review`; per-system resilience — `ucp-node-resilience-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `core/` импортит фреймворк (`R-HEX-CORE-X1/X2`), нет dependency-cruiser-контракта (`hexagonal/module-per-part`), `core/`→`adapters` (`hexagonal/core-free-of-framework`), контроллер зовёт репозиторий (`hexagonal/controller-dispatches-only`), порт-метод возвращает/принимает DTO внешней системы (`hexagonal/port-speaks-domain-types`/`hexagonal/port-speaks-domain-types`).
   - **Предупреждение** — анемичный домен (`hexagonal/rich-domain-model`), порт-класс (`hexagonal/outbound-port-interface-in-core`), бизнес-логика в адаптере (`hexagonal/controller-dispatches-only`/`hexagonal/adapter-maps-not-decides`), адаптеры зависят друг от друга, depcruise не в CI (`hexagonal/architecture-tests-required`).
   - **Замечание** — user/admin не разделены (`hexagonal/in-adapter-per-audience`), domain наружу как ответ (`hexagonal/rest-mapping-in-adapter`).

## Что не входит

- Бизнес-операции/Dispatcher — `ucp-node-pattern-review`. DDD-инварианты — `ucp-node-ddd-tactical-review`.
- Persistence — `ucp-node-typeorm-review`. Resilience внешних вызовов — `ucp-node-resilience-review`.

$ARGUMENTS
