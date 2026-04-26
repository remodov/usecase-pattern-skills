---
name: ucp-ddd-tactical-design
description: Design or scaffold a new domain model (aggregate, entities, value objects, events, repository) following the team's DDD Tactical Patterns Style Guide and using the ddd-building-blocks library. Use when modelling a new bounded context, adding an aggregate, or introducing a new domain event.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# DDD Tactical Patterns Design

You are designing or scaffolding a new domain model: a bounded context, an aggregate, a value object, or a domain event. The implementation must follow the team's DDD Tactical Patterns Style Guide and use the abstractions from the `ddd-building-blocks` library (package `ru.badgermock.ddd`).

## Instructions

1. **Read the style guide** from `docs/ddd-tactical-style-guide.md`. Treat every `R-*` rule as binding. Cite the rules you rely on in your design notes.

2. **Confirm the library is available.** Check `build.gradle` / `pom.xml` for `ru.vikulinva:ddd-building-blocks`. If absent, instruct the user to add it (and offer the dependency snippet) — do not invent local copies of `Entity`/`AggregateRoot`/`ValueObject`.

3. **Clarify the model from the user's description.** Determine:
   - The bounded context name and the package root for it (`core/<bc>/domain/...`).
   - The aggregate root: what business invariant does it protect?
   - Internal entities (if any) and their lifecycle within the root.
   - Value Objects to extract (kill primitive obsession: `Money`, `Email`, `OrderId`, etc.).
   - Domain events emitted by the root, named in past tense.
   - Cross-aggregate references — must be by ID only.
   - Whether a Factory, Domain Service or Specification is justified (default: no).

4. **Produce the code.** For each class, write a complete Java file (Java 21+, no Lombok unless project already uses it):

   - **Value Objects** as Java `record`s implementing `ValueObject`, with compact constructor validating invariants. If a record is not a fit (mutable algorithms, custom equals semantics), use `final class` with `final` fields.
   - **Entities** extending `Entity<ID>`, `id` `final`, only business methods (no setters), validation in constructor. Do not override `equals`/`hashCode`.
   - **Aggregate Roots** extending `AggregateRoot<ID>`, mutating methods enforce invariants and call `registerEvent(new SomethingHappened(...))`.
   - **Domain Events** as `final class` extending `DomainEvent`, calling `super(aggregateType, aggregateId)`; all fields `final`; past-tense name (`OrderPaid`, not `PayOrder`).
   - **Repository** as an interface in `domain/repository/` extending `AggregateRepository<T, ID>` with domain-named methods. Place implementation under `adapter/out/<storage>/`.
   - **Domain Service / Factory / Specification** only if the rules in the style guide say they're warranted. State the justification.

5. **Lay out the packages by domain, not by type** (style guide §10):

   ```
   core/<bc>/domain/
     aggregate/<Root>.java
     entity/<InnerEntity>.java
     valueobject/<VO>.java
     event/<Event>.java
     repository/<Repository>.java
   core/<bc>/usecase/
     command/<Operation>Command.java
     command/<Operation>CommandHandler.java
     query/<Operation>Query.java
     query/<Operation>QueryHandler.java
   adapter/in/rest/<Controller>.java
   adapter/out/<storage>/<RepositoryImpl>.java
   ```

   Domain packages must not import Spring, JPA, jOOQ, or the persistence schema.

6. **Self-review before presenting.** Walk through these checks (style guide §11) and only output when they pass:
   - Entity equals/hashCode not overridden; ID `final`.
   - Every VO is immutable and equals by value.
   - All state changes go through aggregate-root methods.
   - Events created inside the root, not in services or repositories.
   - Cross-aggregate references are IDs only.
   - Repository interface in domain, impl in adapter, returns domain types, publishes & clears events on `save`.
   - Package layout grouped by domain.

7. **Output structure:**
   1. Short design summary (3–8 bullet points): aggregate, invariants protected, events emitted, repositories, anything intentionally omitted.
   2. File tree of new files.
   3. Each file as a separate code block titled with its path.
   4. **Implementation notes**: dependencies needed, suggested test cases (one per invariant + one per event).

$ARGUMENTS
