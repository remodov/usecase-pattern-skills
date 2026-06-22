---
name: ucp-node-hexagonal-review
lang: node
description: Ревью Hexagonal Architecture NestJS-сервиса (коды R-HEX-*) — папки core/adapters/app, контракт dependency-cruiser, core без NestJS/TypeORM/class-validator, порты + Symbol-токены в core/<bc>/port, контроллеры через Dispatcher, app только композиция.
when_to_use: Ревью раскладки сервиса Уровня 3 — core/, adapters/, app/, конфиг dependency-cruiser.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(depcruise*)
---

# Ревью Hexagonal (Node / папки + dependency-cruiser)

Ты ревьюишь раскладку сервиса на соответствие **контракту** `backend/hexagonal/hexagonal-rules.md` (`R-HEX-*`) и
**Node-реализации** `backend/hexagonal/node/hexagonal-style-guide.md`. Изоляция — через dependency-cruiser (или eslint-plugin-boundaries).

## Зависимости

- **`.claude/docs/backend/hexagonal/hexagonal-rules.md`** + **`backend/hexagonal/node/hexagonal-style-guide.md`**.
- Парные: `backend/usecase-pattern/node/...` (`R-HEX-3`/Dispatcher), `backend/ddd-tactical/node/...` (rich domain), `backend/node/typeorm/typeorm-rules.md` (out-persistence), `backend/node/nest-bootstrap/nest-bootstrap-rules.md` (`NESTBOOT-5/6/15`).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй коды (`R-HEX-CORE-X1`, `R-HEX-AOUT-X4`), не префикс.

2. **Скоп.** `src/{core,adapters,app}/**`, `.dependency-cruiser.cjs` (или eslint-boundaries-конфиг), `package.json`-скрипты, CI-конфиг, `git diff`.

3. **Прогон.**
   - **Структура (`R-HEX-MOD-*`):** дерево core/adapters/app; контракт dependency-cruiser present (`R-HEX-MOD-X1` если нет); `core/` не импортит `adapters/*` (`R-HEX-MOD-X2`); user/admin-контроллеры разделены (`R-HEX-MOD-X3`).
   - **Core (`R-HEX-CORE-*`):** без `@nestjs/*` и NestJS-декораторов (`R-HEX-CORE-X1`, wiring — `useFactory` в `app/`)/TypeORM (`R-HEX-CORE-X2`)/class-validator-DTO (`R-HEX-CORE-X5`); TypeORM-Entity не используется как domain (`R-HEX-CORE-X4`); rich domain, не анемия (`R-HEX-CORE-X3`).
   - **Ports (`R-HEX-PORT-*`):** интерфейс + Symbol-токен в `core/<bc>/port/out/`, domain-типы в сигнатурах; не в out-adapter (`R-HEX-PORT-X1`); не DTO внешней системы (`R-HEX-PORT-X2`); не `X | null` где отсутствие=ошибка (`R-HEX-PORT-X3`); не класс с реализацией (`R-HEX-PORT-X4`).
   - **In (`R-HEX-AIN-*`):** контроллер через `Dispatcher` (`R-HEX-AIN-X2`), не возвращает domain наружу (`R-HEX-AIN-X3`), без бизнес-логики (`R-HEX-AIN-X1`), не импортит `adapters/out/*` (`R-HEX-AIN-X4`).
   - **Out (`R-HEX-AOUT-*`):** реализует порт и биндится на его токен, мапит domain↔DTO, per-system папка; не возвращает DTO внешней системы (`R-HEX-AOUT-X1`), без бизнес-логики (`R-HEX-AOUT-X2`), не реализует порты разных доменов (`R-HEX-AOUT-X3`), не инжектит другой адаптер (`R-HEX-AOUT-X4`).
   - **app/ (`R-HEX-BOOT-*`):** только композиция/конфиг (`R-HEX-BOOT-X1`); `NestFactory.create`/wiring не в core/adapters (`R-HEX-BOOT-X2`); все порты забинжены (`R-HEX-BOOT-3`).
   - **Тесты (`R-HEX-TEST-*`):** `depcruise --validate` (или eslint-boundaries) в CI как required check (`R-HEX-TEST-X1` если enforcement только через review); единый корень скана (`R-HEX-TEST-3`).

4. **Cross-check:** домен/агрегаты — `ucp-node-ddd-tactical-review`; Dispatcher/граница TX — `ucp-node-pattern-review`; per-system resilience — `ucp-node-resilience-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `core/` импортит фреймворк (`R-HEX-CORE-X1/X2`), нет dependency-cruiser-контракта (`R-HEX-MOD-X1`), `core/`→`adapters` (`R-HEX-MOD-X2`), контроллер зовёт репозиторий (`R-HEX-AIN-X2`), порт-метод возвращает/принимает DTO внешней системы (`R-HEX-PORT-X2`/`R-HEX-AOUT-X1`).
   - **Предупреждение** — анемичный домен (`R-HEX-CORE-X3`), порт-класс (`R-HEX-PORT-X4`), бизнес-логика в адаптере (`R-HEX-AIN-X1`/`R-HEX-AOUT-X2`), адаптеры зависят друг от друга, depcruise не в CI (`R-HEX-TEST-X1`).
   - **Замечание** — user/admin не разделены (`R-HEX-MOD-X3`), domain наружу как ответ (`R-HEX-AIN-X3`).

## Что не входит

- Бизнес-операции/Dispatcher — `ucp-node-pattern-review`. DDD-инварианты — `ucp-node-ddd-tactical-review`.
- Persistence — `ucp-node-typeorm-review`. Resilience внешних вызовов — `ucp-node-resilience-review`.

$ARGUMENTS
