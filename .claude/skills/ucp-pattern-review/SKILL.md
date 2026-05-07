---
name: ucp-pattern-review
description: Проверить Java/Spring-код на соответствие командному Use Case Pattern Style Guide и правильное использование библиотеки usecase-pattern. Применяется при разборе контроллеров, классов UseCase, UseCaseHandler-ов, диспетчеров или маппинга слоёв (JsonBean / Pojo / Domain).
allowed-tools: Read Glob Grep Bash(git diff*) Bash(./gradlew*) Bash(mvn*) Agent
---

# Ревью Use Case Pattern

Ты ревьюишь Java/Spring-код на соответствие Use Case Pattern Style Guide и правильное использование библиотеки `usecase-pattern` (пакеты `ru.vikulinva.usecase`, `ru.vikulinva.usecase.cqrs`).

## Инструкции

1. **Прочитай style guide** из `.claude/docs/usecase-pattern-style-guide.md` в корне проекта. У каждого правила есть код (`R-UC-1`, `R-HND-X2` и т.п.) — цитируй коды в замечаниях. Если в diff есть DDL (`*.sql`, Liquibase changeset) или новые миграции — отдельно вызови `ucp-pg-schema-review` для проверки типов колонок (правила `PG-T-NNN`).

2. **Определи уровень внедрения** осмотрев проект (style guide §2):
   - Найди `core/<bc>/` + `adapter/in/`, `adapter/out/` → **Уровень 4 (Hexagonal)**.
   - Найди `domain/aggregate/`, `Entity<ID>`, `AggregateRoot<ID>` → **Уровень 3 (DDD)**.
   - Найди маркеры `UseCaseCommand` / `UseCaseQuery` → **Уровень 2 (CQRS)**.
   - Иначе → **Уровень 1 (базовый)**.

   Назови определённый уровень в начале отчёта. Применяй правила, перечисленные для этого уровня в §2 style guide. На Уровне 3+ дополнительно загрузи `.claude/docs/ddd-tactical-style-guide.md` и применяй его правила к доменному коду.

3. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - Используй `git diff` (working tree, staged, last commit), чтобы найти изменённые Java-файлы.
   - Смотри `**/usecase/**`, `**/controller/**`, `**/handler/**`, `**/core/**`, `**/adapter/**`.
   - Проверь `build.gradle` / `pom.xml` на `ru.vikulinva:usecase-pattern-starter` (или `usecase-pattern`). Если нет — замечание уровня **Замечание**, но продолжай.

4. **Прогон по соответствующим разделам style guide** как минимум:

   - **§3 UseCase**: record / final immutable; внутри без логики; одна операция = один UseCase; `R` — тип результата; нет `void`.
   - **§4 UseCaseHandler**: `@Component`; `useCaseType()` возвращает правильный класс; `@Transactional` (или `readOnly = true` для запросов); без состояния; один обработчик на один UseCase; constructor injection; никаких инфраструктурных исключений наружу.
   - **§5 Dispatcher / Controller**: контроллер диспатчит через `UseCaseDispatcher`; контроллеры делают только маппинг + диспатч + ответ; никакой бизнес-логики; никакого `HttpServletRequest` внутри UseCase.
   - **§6 CQRS** (Уровень 2+): команды реализуют `UseCaseCommand`, запросы — `UseCaseQuery`; запросы не меняют состояние; команды не возвращают огромные read DTO.
   - **§7 Слои**: JsonBean ≠ Pojo ≠ Domain; маппинг через MapStruct или явные `@Component`-мапперы; никакого `BeanUtils.copyProperties` / рефлекшн-мапперов.
   - **§8 Hexagonal** (Уровень 4): `core/` не импортирует Spring/jOOQ/REST/Kafka; внешние взаимодействия — через порты.
   - **§9 UseCaseStep**: выделять только если переиспользуется в ≥ 2 обработчиках; не вложен; без состояния.
   - **§10 Транзакции**: `@Transactional` на Handler, не на Repository / Service; одна транзакция на UseCase; события публикуются после `repository.save(...)`.

5. **Формат finding, локализация, серьёзность, резюме, запрет правок** — см. `.claude/docs/review-finding-format.md` (правила `RFF-1`..`RFF-16`). Перед каждым finding обязательна Read-проверка строки (`RFF-1`..`RFF-5`), поле `Строка` в формате обязательно (`RFF-7`). В резюме (`RFF-13`) дополнительно явно укажи определённый в шаге 2 уровень внедрения.

6. **Доменные ориентиры для серьёзности** (`RFF-12`):
   - **Критично** — ломает корректность или инварианты: нарушение транзакционной границы, команда в query-handler, протечка Spring/jOOQ в core, анемичный UseCase с логикой, контроллер в обход диспетчера.
   - **Предупреждение** — отклонение от конвенции: форма анемичного UseCase, отсутствие маркеров, нейминг, раскладка пакетов.
   - **Замечание** — улучшение / придирка: можно сделать `record`, отсутствует зависимость, можно вынести в `UseCaseStep`.

$ARGUMENTS
