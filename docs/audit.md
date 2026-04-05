# Code Audit Playbook

Reusable audit procedure for the unefy codebase. Four parallel Explore agents
cover the areas that matter for an open-source EU-focused multi-tenant SaaS.

## How to trigger

Ask the assistant:

> **"Run the full code audit"** — executes all four audit agents in parallel
> and returns consolidated findings.

Or run a single dimension:

> **"Run the backend auth audit"**
> **"Run the tenant isolation audit"**
> **"Run the frontend security audit"**
> **"Run the code quality audit"**

The assistant should recognize these phrases and dispatch the matching
prompt(s) from the sections below using the `Explore` subagent.

## Audit dimensions

Each dimension has a fixed prompt so findings stay comparable across runs.

### 1. Backend auth + session

**Prompt:**

```
Security audit of the backend auth + session system in
/Users/andreas/Projects/unefy/backend/app.

Focus on:
1. Session cookie handling — is the cookie httpOnly, Secure, SameSite set
   correctly?
2. OAuth flow — CSRF protection, state parameter, PKCE handling
3. Session storage — Redis, TTL, token rotation
4. Internal API secret handling between Next.js BFF and backend
5. CORS configuration
6. Rate limiting on auth endpoints
7. User resolution — is current_user correctly scoped?
8. How tenant_id is resolved from session
9. Error messages — do they leak sensitive info?
10. Password/token handling — any secrets logged?

Files to examine:
- backend/app/api/v1/auth.py
- backend/app/core/security.py
- backend/app/dependencies.py (for current_user, current_tenant)
- backend/app/main.py (for CORS, middleware)
- backend/app/config.py

Return a list of concrete findings: file:line, severity
(critical/high/medium/low), issue description, and suggested fix. Be
specific, don't generalize. Flag anything that could leak user data, bypass
auth, or enable account takeover. Also check that sensitive data (passwords,
tokens, session IDs) are never logged or returned in responses.
```

### 2. Tenant isolation

**Prompt:**

```
Audit tenant isolation in the backend at
/Users/andreas/Projects/unefy/backend/app.

Critical invariant: EVERY database query on tenant-scoped data MUST be
filtered by tenant_id. Bypassing this is a cross-tenant data leak (GDPR
nightmare for this EU-focused project).

Check:
1. Every repository inherits or manually uses tenant_id scoping
2. No raw SQL queries that bypass the BaseRepository
3. Service layer never passes tenant_id from user input
4. All endpoints use Depends(require_role(...)) or similar auth guards
5. Bulk operations (bulk-delete, batch-update) correctly scope to tenant
6. Search/filter queries don't allow leaking across tenants via clever input
7. member_id / entity_id parameters from URL are always verified against
   tenant
8. Any queries joining tables include tenant_id in BOTH sides
9. Soft-delete queries respect tenant scope

Files to examine:
- backend/app/repositories/ (all files)
- backend/app/services/ (all files)
- backend/app/api/v1/ (all endpoints)
- backend/app/dependencies.py

For each finding, provide: file:line, severity (critical/high/medium/low),
the exact query/code that's problematic, and the fix. Be paranoid — if a
query uses entity_id from URL without checking tenant, that's critical.
```

### 3. Frontend security + BFF

**Prompt:**

```
Security audit of the Next.js frontend at /Users/andreas/Projects/unefy/apps/web.

The app uses a BFF pattern where Next.js forwards session cookies to the
FastAPI backend. Audit:

1. apiFetch / apiCall — does it leak the INTERNAL_API_SECRET to the client?
   Is the browser-side api-client different from server-side?
2. lib/api.ts vs lib/api-client.ts — are they properly separated
   (server vs client)?
3. Server Actions — do they check session server-side?
4. Cookie handling — is the session cookie forwarded correctly to backend?
5. XSS risks — any dangerouslySetInnerHTML? Any innerHTML manipulation?
6. CSRF — Server Actions should be safe by default, but check POST endpoints
7. Environment variables — is NEXT_PUBLIC_* used appropriately? Anything
   sensitive exposed to the browser?
8. Client-side data leakage — does localStorage/sessionStorage contain
   anything sensitive?
9. Input validation — is Zod used consistently?
10. Error messages shown to user — do they leak backend details?

Files to examine:
- apps/web/lib/api.ts
- apps/web/lib/api-client.ts
- apps/web/lib/auth.ts
- apps/web/app/api/auth/ (any route handlers)
- apps/web/components/auth/
- apps/web/next.config.js/ts (any security headers?)
- apps/web/middleware.ts (if exists)

Also check:
- Are there any hardcoded URLs, tokens, or credentials?
- Is the INTERNAL_API_SECRET only used server-side?
- Do Server Components correctly validate session before rendering?

Return findings as file:line, severity, issue, fix. Be concrete.
```

### 4. Code quality + consistency

**Prompt:**

```
Code quality + consistency audit of the unefy project at
/Users/andreas/Projects/unefy.

This is being prepared for open source release. Flag inconsistencies that
would hurt contributor experience.

Check:
1. Naming consistency — are filenames kebab-case? Are Python modules
   snake_case? Are React components PascalCase?
2. Error handling patterns — is every Server Action / API call consistent
   in error shape?
3. Translation coverage — any hardcoded German/English strings in
   components? Any missing keys between de.json and en.json?
4. Component structure — are UI components vs feature components cleanly
   separated?
5. Type safety — any `as any` casts, `// @ts-ignore`, or type assertions
   that could be cleaner?
6. Hook usage — are custom hooks in hooks/ folder? Do they follow use*
   naming?
7. API response shape — consistent `{data, meta, error}` envelope?
8. Migration hygiene — Alembic migrations reviewable? Any destructive
   migrations without warnings?
9. Test coverage — any critical paths lacking tests?
10. Documentation — are public functions documented?
11. Dead code — unused imports, unused exports?
12. Inconsistent imports — some files use absolute paths (@/), some
    relative?
13. Frontend — any components using primitive HTML elements instead of
    shadcn/ui?
14. Backend — any async functions with blocking calls? Missing type hints?

Scan:
- apps/web/components/ (focus on ui/, common/, members/)
- apps/web/app/
- apps/web/hooks/
- apps/web/lib/
- apps/web/messages/de.json + en.json
- backend/app/ (all subdirectories)

Return findings grouped by category (naming, errors, i18n, types, etc.),
each with file:line and concrete fix suggestion. Also list: missing
translations, unused imports, components violating shadcn rules.
```

## Report structure expected from each agent

Each dimension should return:

- A summary table with `file:line | severity | issue | fix`
- Positive findings (what's correct)
- Recommendations ordered by severity

## How to re-run later

1. Open this file
2. Paste the dimension prompts into separate `Explore` agents (parallel
   execution)
3. Consolidate findings back here if new baseline needed
