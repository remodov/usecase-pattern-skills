---
name: ucp-pattern-design
description: Спроектировать новую бизнес-операцию как Command или Query + Handler с библиотекой usecase-pattern для Java/Spring (требования usecase-pattern/*) — контроллер с диспатчем, маппинг JsonBean/Pojo/Domain.
when_to_use: Добавление нового эндпоинта, команды или запроса в Spring Boot-сервис. После ucp-bootstrap-design в цепочке.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Use Case Pattern — проектирование

Ты проектируешь или генерируешь шаблон новой бизнес-операции: одну или несколько пар `<Operation>Command` / `<Operation>Query` + `Handler` (и путь контроллера, который их диспатчит) с использованием библиотеки `usecase-pattern`.

## Инструкции

1. **Прочитай** общий контракт `.claude/docs/backend/usecase-pattern/spec.md` (требования `usecase-pattern/*`) **и Java-реализацию** `.claude/docs/backend/usecase-pattern/references/java/implementation.md` (библиотека `usecase-pattern`, `record`/`@RequiredArgsConstructor`/`@Transactional`/MapStruct — конкретика для Java-кода). Считай каждое правило `R-*` обязательным. На Уровне 3 дополнительно прочитай `.claude/docs/backend/ddd-tactical/spec.md`. Если в дизайне есть DDL новой таблицы или колонки — также прочитай `.claude/docs/backend/pg-types/spec.md` и применяй правила `PG-T-NNN` к выбору типов (`bigint IDENTITY` или `uuid` v7 для PK, `timestamptz` для бизнес-времени, `numeric(p,s)` для денег, `Instant`/`OffsetDateTime` на Java-стороне для `timestamptz`).

2. **Подтверди наличие библиотеки.** Проверь `build.gradle` / `pom.xml` на `ru.vikulinva:usecase-pattern-starter`. Если нет — попроси пользователя добавить (и предложи сниппет зависимости) — не выдумывай локальные копии `UseCase` / `UseCaseHandler` / `UseCaseDispatcher`.

3. **Определи уровень зрелости** проекта (`hexagonal/level-three-only`, `cqrs/split-matches-maturity-level`):
   - Hexagonal (`core/` + `adapter/`) и/или доменный слой (`Entity`, `AggregateRoot`) → Уровень 3 (DDD + Hexagonal)
   - `usecase-pattern` (Command/Query + Handler) без агрегатов и ports/adapters → Уровень 2 (Use Case Pattern); каждая операция — `UseCaseCommand` или `UseCaseQuery`
   - Controller → Service → Repository без `usecase-pattern` → Уровень 1 (Слоёный)

   Назови уровень явно. Подбирай дизайн под него: не вводить DDD-агрегаты ниже Уровня 3, не отбрасывать CQRS-маркеры, если они уже используются.

4. **Уточни операцию из описания пользователя.** Определи:
   - Это **команда** (меняет состояние) или **запрос** (только чтение).
   - Входные данные (REST-тело, path-параметры, заголовки — переводятся в JsonBean и ID-ы).
   - Выход: JsonBean / read-DTO / `UseCaseEmptyResult`.
   - Сквозные потребности: идемпотентность, контекст авторизации, асинхронность vs синхронность, batch.
   - На Уровне 3: какой агрегат затрагивается, какие инварианты держатся, какие события публикуются.

5. **Произведи код.** Код — Java 21+, ровно то, что просят: полные файлы — по запросу на генерацию, иначе фрагменты. **Lombok-defaults обязательны** (`java-style/boilerplate-is-generated`–`java-style/builder-used-sparingly` в `backend/java/java-style/spec.md`): `@RequiredArgsConstructor` на каждом Spring-бине с DI, `@Slf4j` вместо ручного `Logger`, `@Getter` на доменных исключениях с payload-полями. На records — `@Builder` при многих необязательных полях; остальной Lombok там лишний (`java-style/no-generation-on-records`).

   **Не цитируй коды правил в комментариях кода** (`java-style/no-rule-codes-or-history-in-code`). Никаких `// R-UC-3`, `// R-LAY-2`, `// R-DSP-X2`, `// R-CQRS-1` в исходниках. Соответствие правилу выражается именами (`CreateProductCommand`, `*Query*Handler`) и структурой (record + marker interface + `@Component` + `@Transactional`). Комментарий уместен только если WHY неочевиден из кода — и тогда без кода правила.

   - **`<Operation>Command` / `<Operation>Query`** — `record`, реализует `UseCaseCommand<R>` (меняет состояние) или `UseCaseQuery<R>` (только читает); голого `UseCase<R>` нет, имя кончается маркером. Иммутабельный, без логики.
   - **`<Operation>CommandHandler` / `<Operation>QueryHandler`** — `@Component` + `@RequiredArgsConstructor`, реализует `UseCaseHandler<MyCommand, R>`, возвращает `MyCommand.class` из `useCaseType()`, имеет `@Transactional` (или `readOnly = true`). Поля — `private final`, без явного конструктора. Логика живёт здесь.
   - **Controller** — `@RestController class XController implements <Tag>Api` (`validation/controller-implements-generated-contract` — интерфейс генерируется openapi-generator-ом из `src/main/resources/openapi/<service>.openapi.yaml`). Методы — `@Override` интерфейсных, дополнительно навешиваются `@PreAuthorize`. Тело метода: маппинг request DTO → UseCase, `dispatcher.dispatch(...)`, обёртка в `ResponseEntity`. Никакого `@RequestMapping` на классе, никаких ручных request/response DTO в `jsonbean/`. Если openapi-generator не подключён — это повод вызвать `ucp-bootstrap-design`, а не писать ручной контроллер.
   - **Mapper** (если нужен новый маппинг) — **MapStruct-интерфейс обязателен** (`usecase-pattern/explicit-mapper-between-layers`): `@Mapper(componentModel = "spring")` + `default`-методы внутри интерфейса для нетривиальных конверсий. Ручной `@Component`-маппер — только при stateful / DI-зависимом маппинге, что не покрывается MapStruct.
   - **(Уровень 3)** Handler разбирает команду сам: в агрегат уходят доменные типы, не объект команды (`ddd-tactical/domain-does-not-know-operations`). Если атрибуты приходят одним целым — заводится `<Aggregate>Snapshot` в `domain/valueobject/`, и маппер границы собирает его.
   - **(Уровень 3)** **Доменные части** — только если операция реально требует нового состояния агрегата, value object'а или события. Следуй `backend/ddd-tactical/spec.md`. Если операция чисто read — предпочитай Read Model и пропускай агрегат.
   - **(Уровень 3, Hexagonal-раскладка)** Раскладка файлов: `core/usecase/{command,query}/<фича>/`, `core/port/{in,out/{repository,filter,publisher,client}}/`, `core/view/`; адаптеры — модули `*-in-adapter` / `*-out-adapter` с пакетами `adapter.in.*` / `adapter.out.*`. Домен живёт в `core/domain/{aggregate,entity,valueobject,event,factory,service}/` — слоя bounded context'ов в `core/` нет.

6. **Самопроверка перед выдачей:**
   - Command/Query — record, без логики, имя = бизнес-операция + суффикс `Command` / `Query`.
   - Handler — `@Component` + `@RequiredArgsConstructor`, возвращает useCaseType, транзакционный.
   - Controller вызывает только `UseCaseDispatcher`; сам диспетчер — только во входящих адаптерах: handler и сервисы core не диспатчат других команд/запросов и не зовут чужие handler'ы (`usecase-pattern/handlers-do-not-call-handlers`).
   - Маркер соответствует операции (команда → `UseCaseCommand`, запрос → `UseCaseQuery`), query handler имеет `readOnly = true`.
   - Модели слоёв не смешаны (JsonBean ≠ Pojo ≠ Domain).
   - На Уровне 3 `core/` не импортирует jOOQ / web / Kafka-клиент; из Spring — только whitelist (`@Component`, `@Transactional`); конфигурация — через интерфейс `port/in`, не `@Value`.
   - Lombok: `@RequiredArgsConstructor` на каждом бине; `@Slf4j` если нужны логи; явных multi-arg-конструкторов нет (`java-style/boilerplate-is-generated`).

7. **Вывод** — по общему правилу: размер ответа равен размеру вопроса; решения и затронутые файлы — всегда, полные файлы — только когда просят сгенерировать; ревью — по запросу, не автоматически.

$ARGUMENTS
