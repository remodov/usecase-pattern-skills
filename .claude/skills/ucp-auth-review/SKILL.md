---
name: ucp-auth-review
description: Review Spring Boot service for auth/authz compliance — JWT validation at edge, RBAC at BFF, ABAC for resource ownership in domain handlers, mTLS or Client Credentials for service-to-service, audit log for admin actions, PII hygiene, idempotency for money operations. Use when reviewing security config, controllers, handlers, or PR touching auth flow.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(./gradlew*) Bash(mvn*) Agent
---

# Auth Patterns Review

You are reviewing Spring Boot code for compliance with the team's auth-patterns style guide. The skill is intentionally narrow — it covers what the methodology dictates, not the full OWASP / appsec landscape.

## Instructions

1. **Read the style guide** from `.claude/docs/auth-patterns-style-guide.md`. Cite codes (`AUTH-7`, `AUTH-15`) in findings.

2. **Identify what to review.** Default scope:
   - `**/SecurityConfig*.java` and any `@Configuration` that talks to Spring Security or `OAuth2ResourceServer`.
   - REST controllers (`@RestController`) — check `@PreAuthorize` on each endpoint.
   - UseCase handlers — check ABAC by ownership.
   - Outbound HTTP clients (`adapter-out-*`) — check mTLS / Bearer.
   - Logging configurations and exception handlers — check PII leaks.
   - `application*.yml` — check secrets, JWK URIs.

   If user named files — limit to those. Otherwise use `git diff` (working tree, staged, last commit).

3. **Walk through each rule group:**

   - **§1 Where checks live (`AUTH-1`..`AUTH-3`):** is the gateway doing JWT validation? Is BFF doing RBAC? Is domain doing ABAC? Wrong layer = critical finding.
   - **§2 JWT (`AUTH-4`..`AUTH-6`):** `oauth2ResourceServer().jwt()` used (not custom filter); JWK URL configured; 401 vs 403 distinction correct.
   - **§3 RBAC (`AUTH-7`..`AUTH-9`):** `JwtAuthenticationConverter` with `ROLE_` prefix; allowed roles only `customer`/`seller`/`admin`/`system`; **every REST endpoint has `@PreAuthorize`**.
   - **§4 ABAC (`AUTH-10`..`AUTH-12`):** if the endpoint takes a path-id of a domain aggregate, ownership check is present (in `@PreAuthorize` SpEL, in `@Component("access")` bean, or in handler); admin override is logged.
   - **§5 S2S (`AUTH-13`..`AUTH-14`):** outbound clients in `adapter-out-*` have mTLS config or Bearer token interceptor.
   - **§6 Audit (`AUTH-15`):** every command from `admin` writes to `<bc>_audit_log` table.
   - **§7 PII / secrets (`AUTH-16`..`AUTH-18`):**
     - search log statements (`logger.info(...)`, `log.debug(...)`) for fields like `email`, `phone`, `address`, `password`, `token`, `secret`;
     - check `OrderExceptionHandler` (or equivalent) — does it leak `cause.getMessage()` into `ProblemDetails.detail`?
     - search `application*.yml` for hardcoded secrets / passwords.
   - **§8 Idempotency (`AUTH-19`):** money-changing endpoints declare `Idempotency-Key` header in OpenAPI and check it in handler.
   - **§9 Client-side (`AUTH-20`..`AUTH-21`):** for BFF — HttpOnly + Secure + SameSite cookies; refresh-token rotation; no `localStorage` in returned JS hints.

4. **Report findings** in the standard format:

   ```
   <FilePath>:<LineNumber>  [<RuleCode>]  <Severity>
     Problem: <one-line>
     Why: <quote rule briefly>
     Fix: <concrete suggestion + code snippet>
   ```

   Severities:
   - **Critical** — endpoint without `@PreAuthorize`, ABAC missing on resource-bound action, JWT custom filter, plaintext secrets in repo, PII в `ProblemDetails.detail`.
   - **Warning** — weak rule mapping (`hasAuthority` где должно `hasRole`), audit log missing на admin-команде, refresh-token без rotation.
   - **Info** — улучшения: переименовать роль, вынести ABAC в `@Component("access")`, добавить `@AuditLog`-аспект.

5. **End with summary** — counts by severity + verdict.

6. **Don't fix code** — only report.

$ARGUMENTS
