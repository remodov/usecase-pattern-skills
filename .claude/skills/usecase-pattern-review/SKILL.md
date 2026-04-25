---
name: usecase-pattern-review
description: Review Java/Spring code for compliance with the team's Use Case Pattern Style Guide and correct usage of the usecase-pattern library. Use when reviewing controllers, UseCase classes, UseCaseHandlers, dispatchers, or layer mapping (JsonBean / Pojo / Domain).
allowed-tools: Read Glob Grep Bash(git diff*) Bash(./gradlew*) Bash(mvn*) Agent
---

# Use Case Pattern Review

You are reviewing Java/Spring code for compliance with the Use Case Pattern Style Guide and correct usage of the `usecase-pattern` library (packages `ru.vikulinva.usecase`, `ru.vikulinva.usecase.cqrs`).

## Instructions

1. **Read the style guide** from `docs/usecase-pattern-style-guide.md` in the project root. Every rule has a code (`R-UC-1`, `R-HND-X2`, etc.) — cite codes in findings.

2. **Detect the adoption level** by inspecting the project (style guide §2):
   - Look for `core/<bc>/` + `adapter/in/`, `adapter/out/` → **Level 4 (Hexagonal)**.
   - Look for `domain/aggregate/`, `Entity<ID>`, `AggregateRoot<ID>` → **Level 3 (DDD)**.
   - Look for `UseCaseCommand` / `UseCaseQuery` markers → **Level 2 (CQRS)**.
   - Otherwise → **Level 1 (basic)**.

   State the detected level at the start of your report. Apply the rules listed for that level in §2 of the style guide. On Level 3+, also load `docs/ddd-tactical-style-guide.md` and apply its rules to domain code.

3. **Identify what to review.** If the user named files — review those. Otherwise:
   - Use `git diff` (working tree, staged, last commit) to find changed Java files.
   - Look at `**/usecase/**`, `**/controller/**`, `**/handler/**`, `**/core/**`, `**/adapter/**`.
   - Check `build.gradle` / `pom.xml` for `ru.vikulinva:usecase-pattern-starter` (or `usecase-pattern`). If absent → Info finding, but continue.

4. **Review against the relevant style-guide sections** at minimum:

   - **§3 UseCase**: record/final immutable; no logic inside; one operation per UseCase; `R` is the result type; no `void`.
   - **§4 UseCaseHandler**: `@Component`; `useCaseType()` returns the correct class; `@Transactional` (or `readOnly = true` for queries); stateless; one handler per UseCase; constructor injection; no infrastructure exceptions leaking out.
   - **§5 Dispatcher / Controller**: controller dispatches via `UseCaseDispatcher`; controllers do mapping + dispatch + response only; no business logic; no `HttpServletRequest` leaking into UseCase.
   - **§6 CQRS** (Level 2+): commands implement `UseCaseCommand`, queries implement `UseCaseQuery`; queries don't mutate state; commands don't return huge read DTOs.
   - **§7 Layers**: JsonBean ≠ Pojo ≠ Domain; mapping via MapStruct or explicit `@Component` mappers; no `BeanUtils.copyProperties` / reflection mappers.
   - **§8 Hexagonal** (Level 4): `core/` doesn't import Spring/jOOQ/REST/Kafka; external interactions through ports.
   - **§9 UseCaseStep**: extracted only when reused in ≥ 2 handlers; not nested; stateless.
   - **§10 Transactions**: `@Transactional` on Handler, not Repository or Service; one transaction per UseCase; events published after `repository.save(...)`.

5. **Report findings** in this exact format:

   ```
   <FilePath>:<LineNumber>  [<RuleCode>]  <Severity>
     Problem: <one-line description>
     Why: <which rule is violated, quoting the rule briefly>
     Fix: <concrete suggestion, ideally with a small code snippet>
   ```

   Severities:
   - **Critical** — breaks correctness or invariants (transactional boundary breach, command in query handler, Spring/jOOQ leaking into core, anemic UseCase with logic, controller bypassing dispatcher).
   - **Warning** — deviates from convention (anaemic UseCase shape, missing markers, naming, package layout).
   - **Info** — improvement or nit (could be a `record`, missing dependency, could promote to `UseCaseStep`).

6. **End with a summary**: total findings by severity + a one-line verdict — "compliant", "minor deviations", or "needs rework". Mention the detected level explicitly.

7. **Do not modify code.** This skill only reports. Suggestions in `Fix:` are textual.

$ARGUMENTS
