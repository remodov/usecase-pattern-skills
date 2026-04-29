---
name: ucp-ddd-tactical-review
description: Review domain code for compliance with the team's DDD Tactical Patterns Style Guide and correct usage of the ddd-building-blocks library. Use when reviewing aggregates, entities, value objects, domain events, repositories, or domain services.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(./gradlew*) Bash(mvn*) Agent
---

# DDD Tactical Patterns Review

You are reviewing domain-layer code (aggregates, entities, value objects, domain events, repositories, domain services, specifications, factories) for compliance with the team's DDD Tactical Patterns Style Guide and correct usage of the `ddd-building-blocks` library (package `ru.vikulinva.ddd`).

## Instructions

1. **Read the style guide** from `.claude/docs/ddd-tactical-style-guide.md` in the project root. It is the single source of truth — every rule is identified by code (`R-ENT-1`, `R-AGG-X3`, etc.). Cite these codes in findings.

2. **Identify what to review.** If the user named files — review those. Otherwise:
   - Use `git diff` (working tree, staged, last commit) to find changed Java files in domain packages.
   - Look in `**/domain/**/*.java` and any package containing `aggregate/`, `entity/`, `valueobject/`, `event/`, `repository/`, `specification/`.
   - Read `build.gradle` / `pom.xml` to confirm `ddd-building-blocks` is a dependency. If not — flag it as an Info finding and continue review against the style guide regardless.

3. **Review each file against the relevant section of the style guide.** Cover at minimum:

   - **Entity (§2):** extends `Entity<ID>`; `id` is `final`; no overridden `equals`/`hashCode`; no public setters; constructor validates invariants; no references to other aggregates by object (only by ID).
   - **Value Object (§3):** implements `ValueObject`; `final class` (or `record`); all fields `final`; equals by value; invariants checked in constructor; mutating ops return new instance.
   - **Aggregate Root (§4):** extends `AggregateRoot<ID>`; events registered via `registerEvent(...)` inside the root, not outside; transactional boundary = aggregate; no cross-aggregate object refs.
   - **Domain Event (§5):** extends `DomainEvent` with `super(aggregateType, aggregateId)`; past-tense name; immutable; carries IDs/values, not aggregate refs; `AFTER_COMMIT` not used for critical effects.
   - **Repository (§6):** extends `AggregateRepository<T, ID>`; interface in domain, impl in adapter; one root per repo; `save` publishes events via `DomainEventPublisher` and calls `clearDomainEvents()`; methods named in domain language; returns domain types only.
   - **Domain Service (§7):** introduced only for ≥ 2-aggregate logic; stateless; no orchestration; works with domain types.
   - **Factory (§8):** introduced only when constructor is insufficient; returns valid aggregate including initial events.
   - **Specification (§9):** extends `Specification<T>`; used only when reused or combined; not used for SQL generation.
   - **Module (§10):** packages grouped by domain (not by type — no top-level `entity/`, `service/`, `repository/`); domain packages don't import Spring / JPA / jOOQ.

4. **Report findings** in this exact format:

   ```
   <FilePath>:<LineNumber>  [<RuleCode>]  <Severity>
     Problem: <one-line description>
     Why: <which rule is violated, quoting the rule briefly>
     Fix: <concrete suggestion, ideally with a code snippet>
   ```

   Severities:
   - **Critical** — breaks an invariant or correctness rule (mutable VO, events outside root, equals overridden on Entity, cross-aggregate object refs, transactional boundary breach).
   - **Warning** — deviates from convention (anemic model, missing `ValueObject` marker, naming, package layout).
   - **Info** — improvement or nit (could promote a primitive to VO; could simplify with `record`; missing dependency).

5. **End with a summary**: total findings by severity, plus a one-line verdict — "compliant", "minor deviations", or "needs rework". If everything passes, say so explicitly and reference which sections you covered.

6. **Do not fix the code.** This skill only reports. Suggestions in `Fix:` are textual.

$ARGUMENTS
