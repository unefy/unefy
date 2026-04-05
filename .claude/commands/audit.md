---
description: Run the full code audit (4 parallel Explore agents)
---

Run the complete code audit as documented in `docs/audit.md`.

Dispatch **four Explore agents in parallel** using the exact prompts from
the audit playbook. Do NOT paraphrase or change the prompts — they are the
stable baseline.

Prompts to dispatch (each in its own agent, all in one message):

1. **Backend auth + session audit** — use section "1. Backend auth + session"
   prompt from `docs/audit.md`
2. **Tenant isolation audit** — use section "2. Tenant isolation" prompt
3. **Frontend security + BFF audit** — use section "3. Frontend security + BFF"
   prompt
4. **Code quality + consistency audit** — use section "4. Code quality +
   consistency" prompt

After all four agents return, present a consolidated summary:

- One table per dimension with `file:line | severity | issue | fix`
- A final combined "Must fix before release" list sorted by severity
- Call out any NEW findings that weren't in the previous audit (if we have
  a previous baseline)

If the user asks for a single dimension only (e.g. "just run the tenant
audit"), dispatch only that agent.
