"""Delta sync: how a client mirrors a tenant's data and keeps it current.

The contract has two halves, and only one of them is load-bearing.

**The pull is where correctness lives.** A client holds an opaque cursor, asks
for everything that changed after it, and gets back changed rows, tombstones for
deleted ones, and a new cursor. That alone is enough to be offline-capable and to
converge — no stream required, no message ever has to arrive.

**A push channel is only latency.** It says "something changed, come and get it"
and nothing more, so a dropped notification costs a few seconds of freshness
rather than data. That is why the payload carries no rows.

Two things this module deliberately does not reuse:

- **`TenantAuditLog` is not the change feed**, tempting as it looks. Its coverage
  is attendance-only, it stores field diffs rather than rows (on purpose, for
  GDPR), and its read API needs the target ids up front. See `app/models/audit.py`.
- **Offset pagination is not used here.** `page`/`per_page` re-evaluates the
  ordered set per page, so a concurrent write shifts rows across page boundaries
  and one slips through un-synced. Fine for a human browsing a table, wrong for
  a mirror. See `cursor.py` for what replaces it.
"""
