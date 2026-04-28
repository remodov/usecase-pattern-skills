---
name: ucp-pattern-design
description: Design or scaffold a new business operation as a UseCase + UseCaseHandler using the usecase-pattern library, following the team's Use Case Pattern Style Guide. Use when adding a new endpoint, command, or query to a Spring Boot service.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Use Case Pattern Design

You are designing or scaffolding a new business operation: one or more `UseCase` + `UseCaseHandler` pairs (and the controller path that dispatches them) using the `usecase-pattern` library.

## Instructions

1. **Read the style guide** from `docs/usecase-pattern-style-guide.md` and treat every `R-*` rule as binding. On Level 3+ also read `docs/ddd-tactical-style-guide.md`.

2. **Confirm the library is available.** Check `build.gradle` / `pom.xml` for `ru.vikulinva:usecase-pattern-starter`. If absent, instruct the user to add it (and offer the dependency snippet) — do not invent local copies of `UseCase` / `UseCaseHandler` / `UseCaseDispatcher`.

3. **Detect the adoption level** of the project (style-guide §2):
   - Hexagonal (`core/` + `adapter/`) → Level 4
   - Domain layer (`Entity`, `AggregateRoot`) → Level 3
   - `UseCaseCommand` / `UseCaseQuery` markers → Level 2
   - Otherwise → Level 1

   State the level explicitly. Match the design to it: don't introduce DDD aggregates on a Level-1 project, don't drop CQRS markers if the project is on Level 2+.

4. **Clarify the operation from the user's description.** Determine:
   - Whether it's a **command** (mutates) or a **query** (reads only).
   - Input data (REST body, path params, headers — translated to a JsonBean and IDs).
   - Output: JsonBean / read DTO / `UseCaseEmptyResult`.
   - Cross-cutting needs: idempotency, auth context, async vs sync, batch.
   - If Level 3+: which aggregate is touched, which invariants must hold, what events are emitted.

5. **Produce the code.** Write complete Java files (Java 21+). **Lombok-defaults обязательны** (`JS-6.1`–`JS-6.7` в `java-style-guide.md`): `@RequiredArgsConstructor` на каждом Spring-бине с DI, `@Slf4j` вместо ручного `Logger`, `@Getter` на доменных исключениях с payload-полями. Lombok **не** навешиваем на records.

   **Не цитировать коды правил в комментариях кода** (`JS-7.3`). Никаких `// R-UC-3`, `// R-LAY-2`, `// R-DSP-X2`, `// R-CQRS-1` в исходниках. Соответствие правилу выражается именами (`CreateProductUseCase`, `*Query*Handler`) и структурой (record + marker interface + `@Component` + `@Transactional`). Комментарий уместен только если WHY неочевиден из кода — и тогда без кода правила.

   - **`<Operation>UseCase`** — `record` implementing `UseCase<R>` (Level 1) or `UseCaseCommand<R>` / `UseCaseQuery<R>` (Level 2+). Immutable, no logic.
   - **`<Operation>UseCaseHandler`** — `@Component` + `@RequiredArgsConstructor`, implements `UseCaseHandler<MyUseCase, R>`, returns `MyUseCase.class` from `useCaseType()`, has `@Transactional` (or `readOnly = true`). Поля — `private final`, без явного constructor'а. Logic stays here.
   - **Controller method** — `@RestController` method that maps the request into the `UseCase`, calls `useCaseDispatcher.dispatch(...)`, returns the result. No business logic.
   - **Mapper** (if a new mapping is needed) — **MapStruct interface обязательно** (`R-LAY-3`): `@Mapper(componentModel = "spring")` + `default`-методы внутри интерфейса для нетривиальных конверсий. Hand-written `@Component`-маппер — только при stateful / DI-зависимом маппинге, что не покрывается MapStruct'ом.
   - **(Level 3+)** **Domain pieces** — only if the operation actually requires new aggregate state, value object, or event. Follow `ddd-tactical-style-guide.md`. If the operation is pure read, prefer a Read Model and skip the aggregate.
   - **(Level 4)** Place files: `core/<bc>/usecase/...`, `core/<bc>/port/...`, `adapter/in/rest/...`, `adapter/out/<storage>/...`. Domain stays in `core/<bc>/domain/...`.

6. **Self-review before presenting.** Walk through these checks (style-guide §12):
   - UseCase is record/final, no logic, name = business operation.
   - Handler is `@Component` + `@RequiredArgsConstructor`, returns useCaseType, transactional.
   - Controller calls only `UseCaseDispatcher`.
   - On Level 2+, the right CQRS marker is used, query handler has `readOnly = true`.
   - Layer models are not mixed (JsonBean ≠ Pojo ≠ Domain).
   - On Level 4, `core/` does not import Spring / jOOQ / REST / Kafka.
   - Lombok: `@RequiredArgsConstructor` на каждом бине; `@Slf4j` если нужны логи; явных multi-arg constructor'ов нет (`JS-6.1`).

7. **Output structure:**
   1. Detected level + one-paragraph design summary (operation, command/query, side effects, events).
   2. File tree of new files.
   3. Each file as a separate code block titled with its path.
   4. **Implementation notes**: dependency snippet (if missing), suggested unit tests (positive case + each invariant + each error path), and a tiny example of how a controller test would dispatch it.

$ARGUMENTS
