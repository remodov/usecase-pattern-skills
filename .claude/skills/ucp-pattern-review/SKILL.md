---
name: ucp-pattern-review
description: Ревью Java/Spring-кода по требованиям `usecase-pattern/*` и библиотеке usecase-pattern — контроллеры, UseCase, UseCaseHandler, диспетчеры, маппинг слоёв JsonBean/Pojo/Domain.
when_to_use: Ревью контроллеров, классов UseCase, UseCaseHandler-ов, диспетчеров или маппинга слоёв.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(./gradlew*) Bash(mvn*)
---

# Ревью Use Case Pattern

Ты ревьюишь Java/Spring-код на соответствие требованиям `usecase-pattern/*` и правильное использование библиотеки `usecase-pattern` (пакеты `ru.vikulinva.usecase`, `ru.vikulinva.usecase.cqrs`).

## Инструкции

1. **Прочитай** общий контракт `.claude/docs/backend/usecase-pattern/spec.md` (требования `usecase-pattern/*`) **и Java-реализацию** `.claude/docs/backend/usecase-pattern/references/java/implementation.md` (конкретика `usecase-pattern`-библиотеки для проверки Java-кода). У каждого правила есть код (`usecase-pattern/usecase-implements-marker`, `usecase-pattern/infrastructure-errors-become-domain` и т.п.) — цитируй коды в замечаниях. Если в diff есть DDL (`*.sql`, Liquibase changeset) или новые миграции — отдельно вызови `ucp-pg-schema-review` для проверки типов колонок (правила `PG-T-NNN`).

1a. **Контур безопасности — не вход.** Фильтр, конвертер токена и провайдер контекста читают через порт напрямую и диспетчер не зовут — это норма (`usecase-pattern/entry-calls-dispatcher`). Находка — только если такой компонент **меняет** состояние в обход операции.

1b. **Проверь направление между слоями:** handler разбирает команду и зовёт домен доменными типами; метод агрегата, принимающий `*Command`, — нарушение `ddd-tactical/domain-does-not-know-operations` (домен тянет за собой слой операций).

2. **Определи уровень зрелости** осмотрев проект (`hexagonal/level-three-only`, `cqrs/split-matches-maturity-level`):
   - Найди `core/` с `domain/aggregate/`, `usecase/`, `port/` и модули `*-in-adapter` / `*-out-adapter`, и/или `Entity<ID>`, `AggregateRoot<ID>` → **Уровень 3 (DDD + Hexagonal)**.
   - Найди `usecase-pattern` (UseCase + Handler) без агрегатов и ports/adapters → **Уровень 2 (Use Case Pattern)**; каждая операция — `UseCaseCommand` или `UseCaseQuery`.
   - Controller → Service → Repository без `usecase-pattern` → **Уровень 1 (Слоёный)**, этот гайд не применяется.

   Назови определённый уровень в начале отчёта. Применяй правила, перечисленные для этого уровня в требованиях домена. На Уровне 3 дополнительно загрузи `.claude/docs/backend/ddd-tactical/spec.md` и применяй его правила к доменному коду.

3. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - Используй `git diff` (working tree, staged, last commit), чтобы найти изменённые Java-файлы.
   - Смотри `**/usecase/**`, `**/controller/**`, `**/handler/**`, `**/core/**`, `**/adapter/**`.
   - Проверь `build.gradle` / `pom.xml` на `ru.vikulinva:usecase-pattern-starter` (или `usecase-pattern`). Если нет — замечание уровня **Замечание**, но продолжай.

4. **Прогон по соответствующим требованиям домена** как минимум:

   - **§3 UseCase**: record / final immutable; внутри без логики; одна операция = один UseCase; `R` — тип результата; нет `void`.
   - **§4 UseCaseHandler**: `@Component`; `useCaseType()` возвращает правильный класс; `@Transactional` (или `readOnly = true` для запросов); без состояния; один обработчик на один UseCase; constructor injection; никаких инфраструктурных исключений наружу.
   - **§5 Dispatcher / Controller**: контроллер диспатчит через `UseCaseDispatcher`; контроллеры делают только маппинг + диспатч + ответ; никакой бизнес-логики; никакого `HttpServletRequest` внутри UseCase. `UseCaseDispatcher` — только во входящих адаптерах: инжектирован в handler или сервис core, handler диспатчит другую команду/запрос — `usecase-pattern/handlers-do-not-call-handlers`, критично.
   - **§6 CQRS-маркеры** (обязательны): каждая операция — `UseCaseCommand` или `UseCaseQuery`, имя кончается на `Command` / `Query`, голого `UseCase` нет; запросы не меняют состояние; команды не возвращают огромные read DTO.
   - **§7 Слои**: JsonBean ≠ Pojo ≠ Domain; маппинг через MapStruct или явные `@Component`-мапперы; никакого `BeanUtils.copyProperties` / рефлекшн-мапперов.
   - **§8 Hexagonal** (Уровень 3): `core/` не импортирует jOOQ/web/Kafka-клиент, из Spring — только whitelist (`@Component`, `@Transactional`); конфигурация — через интерфейс `port/in`, не `@Value`; внешние взаимодействия — через порты.
   - **§9 UseCaseStep**: выделять только если переиспользуется в ≥ 2 обработчиках; не вложен; без состояния.
   - **§10 Транзакции**: `@Transactional` на Handler, не на Repository / Service; одна транзакция на UseCase; события публикуются после `repository.save(...)`.

5. **Формат finding, локализация, серьёзность, резюме, запрет правок** — см. `.claude/docs/shared/review-format/spec.md` (правила `review-format/*`). Перед каждым finding обязательна Read-проверка строки (`review-format/*`), поле `Строка` в формате обязательно (`review-format/finding-carries-line-and-rule`). В резюме (`review-format/report-ends-with-verdict`) дополнительно явно укажи определённый в шаге 2 уровень внедрения.

6. **Доменные ориентиры для серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — ломает корректность или инварианты: нарушение транзакционной границы, команда в query-handler, диспетчер или чужой handler внутри handler'а, протечка jOOQ/web/Kafka-клиента или Spring вне whitelist'а в core, анемичный UseCase с логикой, контроллер в обход диспетчера.
   - **Предупреждение** — отклонение от конвенции: форма анемичного UseCase, отсутствие маркеров, нейминг, раскладка пакетов.
   - **Замечание** — улучшение / придирка: можно сделать `record`, отсутствует зависимость, можно вынести в `UseCaseStep`.

$ARGUMENTS
