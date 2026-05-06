---
name: ucp-spec-review
description: Review a Use Case specification (or Event Storming draft) for design-quality issues — Ubiquitous Language consistency, Bounded Context boundaries, aggregate invariant load, missing actors, command/event ownership, failure domain coverage, data ownership, acceptance criteria coverage. AI as design critic, not code reviewer. Use when validating a spec produced by `ucp-spec-design`, reviewing an Event Storming draft, or onboarding a brownfield service whose existing spec needs honest audit.
allowed-tools: Read Glob Grep Bash(git diff*) Agent
---

# Use Case Specification — review (design critic)

You are reviewing a Use Case specification (or an Event Storming draft) for **design quality**, not for code-level compliance. The goal is to catch what a careful architect catches but that often slips past:

- contradictions in domain language;
- aggregates that quietly grew too many invariants;
- commands without a clear owner or error path;
- domain events without consumers;
- entities with unclear data ownership;
- failure domains the team forgot to consider;
- acceptance criteria that don't actually cover the business rules.

This is **AI as design critic**, the counterpart to `ucp-spec-design`: the spec was generated or hand-written, now we look for cracks before code is written against it.

## Instructions

1. **Read the spec template** from `.claude/docs/usecase-spec-template.md` in the project root. It defines the 16-section structure, Tier requirements (A / B / C), and what each section must contain. Treat the template as the source of truth for completeness rules.

2. **Locate the spec under review.** Three common cases:

   - **Generated spec from `ucp-spec-design`** — usually under `docs/spec/`, one folder per section.
   - **Hand-written spec in a single markdown file** (legacy or brownfield).
   - **Event Storming draft** — text export from Miro / Notion / Mermaid file. Less structured; review what's there against the same design-quality categories where applicable.

   If the user named files — review those. Otherwise discover the spec via `Glob` (`docs/spec/**/*.md`, `docs/**/*-spec*.md`).

3. **Determine the declared Tier** (A / B / C):
   - Look for explicit "(Tier A/B/C)" in the title or §«Уровни спеки» of the spec.
   - If absent — infer from content: presence of aggregates / domain events → Tier C; UseCase-Handler vocabulary → Tier B; only Controller/Service → Tier A.
   - State the detected Tier at the start of the report.

4. **Run the review categories below.** Each rule has a code (`SR-UL-1`, `SR-AG-3`, etc.) — cite the code in every finding. Don't skip categories: if a category is irrelevant for the declared Tier (e.g., events on Tier A), state that explicitly with `not applicable on Tier A`.

### SR-T (Tier consistency)

- **SR-T-1** Declared Tier matches content depth. *Tier C* claim with no aggregates or events → **Critical**. *Tier A* claim with full aggregates → **Warning** (mis-classified).
- **SR-T-2** Sections required for the declared Tier are present (per template's coverage table). Missing = **Critical** for required, **Warning** for optional-on-Tier.

### SR-UL (Ubiquitous Language)

- **SR-UL-1** Each glossary term is used in at least one other section.
- **SR-UL-2** A concept appears under exactly one name. Synonyms outside the glossary (e.g., `Order` vs `Purchase` vs `Sale` for the same thing) → **Critical**.
- **SR-UL-3** Use-case names, command names, and event names use glossary terms — no domain words invented in §7/§8/§10 that aren't in §2.
- **SR-UL-4** Each glossary term has a definition (≥ one sentence). Bare entries → **Warning**.

### SR-BC (Bounded Context)

- **SR-BC-1** §1 has explicit `scope` AND `not-scope`. Missing not-scope → **Warning** (boundary unclear).
- **SR-BC-2** Every command in §7 belongs to this context. Cross-context commands → **Critical** (move to neighbour context or document via §14 Context Mapping).
- **SR-BC-3** No silent overlap with neighbours: if §14 lists `Catalog` as upstream, this spec must not also own product entities.
- **SR-BC-4** Tier B/C: §1 names neighbour contexts and the relationship type (Upstream/Downstream, Customer/Supplier, ACL, etc.).

### SR-AG (Aggregates / Domain Model — Tier C, partial Tier B)

- **SR-AG-1** Each aggregate has ≤ 7 invariants. More → **Warning** (split candidate; document why if intentional).
- **SR-AG-2** Aggregate root is explicit. Sub-entities live inside one root, accessed only through it.
- **SR-AG-3** No cyclic references between aggregates. If A holds `B.id` and B holds `A.id` → **Critical**.
- **SR-AG-4** Value Objects are documented as immutable. Mutable VOs → **Warning**.
- **SR-AG-5** Each aggregate has a clear identity type (`OrderId`, not `Long`). Primitive obsession in IDs → **Warning**.
- **SR-AG-6** Tier C: every state-changing command on the aggregate registers a domain event (cross-check with §8). Silent state changes → **Warning**.

### SR-AR (Actors / Roles)

- **SR-AR-1** Every actor mentioned in §10 use-cases or §7 commands appears in §5 roles. Orphan actor → **Critical**.
- **SR-AR-2** Every role in §5 has a permissions matrix against §7 commands and §9 queries. Missing matrix → **Warning**.
- **SR-AR-3** Each command in §7 declares which role(s) can invoke it. Missing permission tag → **Warning**.

### SR-CM (Commands)

- **SR-CM-1** Each command has: success result type, set of business errors (referencing §13), and pre-conditions. Missing any → **Warning**.
- **SR-CM-2** Tier C: each command names the aggregate it targets. Free-floating commands → **Critical**.
- **SR-CM-3** CQRS service (Tier B+ with markers): commands return identifier or empty result, not full read DTO. Read DTO in command → **Warning** (CQRS leak).
- **SR-CM-4** Commands have explicit idempotency contract: idempotent / not idempotent / requires `Idempotency-Key`. Money-touching commands without idempotency → **Critical**.

### SR-EV (Domain Events — Tier B with Kafka, Tier C always)

- **SR-EV-1** Each event has at least one consumer (internal handler or external subscriber documented in §14). Orphan events → **Critical** (either remove or document subscriber).
- **SR-EV-2** Event names are verbs in past tense (`OrderPaid`, not `PayOrder` / `OrderPayment`).
- **SR-EV-3** Each event with `retryable=true` requires an idempotent consumer. Missing idempotency note → **Warning**.
- **SR-EV-4** Event payload is documented (fields, types). Just a name without payload → **Warning**.
- **SR-EV-5** Tier C: events are published transactionally (Outbox). If §8 mentions `eventBus.publish()` after `save()` outside Outbox → **Critical**.

### SR-FD (Failure Domains)

- **SR-FD-1** Every external dependency in §14 has a documented strategy at failure: graceful degradation / queue / fallback / refusal. Missing → **Warning**.
- **SR-FD-2** §16 NFR specifies where eventual consistency is acceptable and where strong consistency is required. Silent on this → **Warning**.
- **SR-FD-3** External call has either timeout or circuit breaker documented. Missing both → **Critical** (production hazard).

### SR-DO (Data Ownership)

- **SR-DO-1** Every entity in §3 has exactly one owner service. Shared ownership → **Critical**.
- **SR-DO-2** Read-only access to neighbour data is via documented integration (§14: REST, Kafka projection, CDC). Direct DB access to another service's tables → **Critical**.
- **SR-DO-3** PII / regulated fields have explicit retention and deletion policy (§16 NFR or §6 Security cross-link). Missing for fields tagged PII → **Critical**.

### SR-ACR (Acceptance Criteria — §15)

- **SR-ACR-1** Every business rule in §6 has at least one `AC-N` covering it. Uncovered rule → **Warning**.
- **SR-ACR-2** Every command in §7 has at least one happy-path AC and one error-path AC. Missing error-path → **Warning**.
- **SR-ACR-3** AC are written as `Given / When / Then`, not free-form prose. Free-form → **Warning**.

### SR-NFR (Non-Functional — §16)

- **SR-NFR-1** Each NFR has measurable threshold (`p95 ≤ 200 ms`, `RPS = 50`), not just words. Vague NFR → **Warning**.
- **SR-NFR-2** Each NFR has a measurement / alert mechanism. Threshold without «как меряем» → **Warning**.

## Output

5. **Report findings** in this exact format:

   ```
   <SpecPath>:<SectionRef>  [<RuleCode>]  <Severity>
     Problem: <one-line description>
     Why: <which design property is violated>
     Fix: <concrete suggestion — what to add/move/remove>
   ```

   `<SectionRef>` examples: `§7 Commands · CancelOrder`, `§3 Domain Model · Order aggregate`, `§14 Integrations · Catalog upstream`.

   Severities:
   - **Critical** — design defect that will produce wrong code or unsafe production behaviour. Fix before any code generation.
   - **Warning** — design weakness that won't crash the service but will create rework, hidden coupling, or knowledge debt.
   - **Info** — improvement / nit (optional glossary entry, more precise NFR threshold, etc.).

6. **End with a structured summary**:

   ```
   Tier: <A | B | C>  (declared / inferred)

   Findings:
     Critical: <n>
     Warning:  <n>
     Info:     <n>

   Categories with most findings: <top 3>

   Verdict: <ready for code generation | needs design rework | not enough material>
   ```

   - `ready for code generation` — 0 Critical, ≤ 5 Warnings.
   - `needs design rework` — any Critical OR > 5 Warnings.
   - `not enough material` — spec is too thin (< 5 of 16 required sections).

7. **Do not modify the spec.** This skill only reports. Suggestions in `Fix:` are textual.

## Modes

- **Default** — full review of all categories.
- **Fast** (user passes `fast` argument) — only Critical-eligible rules: SR-T-1, SR-UL-2, SR-BC-2, SR-AG-3, SR-AR-1, SR-CM-2, SR-CM-4, SR-EV-1, SR-EV-5, SR-FD-3, SR-DO-1, SR-DO-2, SR-DO-3.
- **ES-draft** (user passes `es` argument) — review an Event Storming export (less structured): focus on SR-UL, SR-BC, SR-AR, SR-EV. Skip rules that need fully filled spec sections.

## Pairing

This skill is the review counterpart to `ucp-spec-design`. Typical loop:

```
ucp-spec-design  →  spec in docs/spec/
                          ↓
                  ucp-spec-review  →  findings
                          ↓
              user fixes spec / re-runs ucp-spec-design with corrections
                          ↓
                  ucp-spec-review (Fast)  →  0 Critical → ready for code
                          ↓
              ucp-pattern-design / ucp-ddd-tactical-design / ucp-api-design
```

The skill validates **design before code**. AI catches contradictions a human reviewer would miss because a human reads top-to-bottom; AI cross-references all 16 sections in one pass.

$ARGUMENTS
