# Backend: FastAPI

Python backend for unefy club management. Serves Web (via Next.js BFF), native mobile apps (iOS/Android), and public API consumers. Fully async.

## Core Principles

1. **Async-First**: No request may block other requests
2. **Multi-Client API**: One API for Web, iOS, Android, and public consumers
3. **Tenant Isolation**: Every query is tenant-scoped — no exceptions
4. **Code Reuse**: DRY through generic base classes and mixins
5. **Type Safety**: Type hints everywhere, Pydantic for runtime validation
6. **Self-Host + SaaS**: Same codebase, behavior controlled by config

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.115+ |
| Python | 3.12+ |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Database | PostgreSQL 17 |
| Cache/Sessions | Redis (async) |
| Auth (Mobile) | JWT Access + Refresh Tokens (OAuth 2.0 + PKCE) |
| Auth (Web) | Backend-issued session cookie (httpOnly, validated server-side) |
| Auth (Public API) | API Keys with scoped permissions |
| Password Hashing | Argon2 (via pwdlib) — for future password support |
| HTTP Client | httpx (async) |
| Background Tasks | FastAPI BackgroundTasks (light) / ARQ (heavy) |
| Server | Uvicorn + Gunicorn (Production) |

## Async-First Architecture (CRITICAL)

**NEVER run blocking code in async functions — it blocks the entire event loop and ALL requests.**

| Code Type | Use | Performance |
|-----------|-----|-------------|
| `async def` with `await` | Non-blocking I/O (DB, APIs, Redis) | Excellent |
| `def` (sync) | Blocking I/O, CPU-intensive | Good (threadpool) |
| `async def` with blocking code | **NEVER!** | Catastrophic |

### Forbidden Libraries in async Functions

| Blocking | Async Alternative |
|----------|------------------|
| `requests` | `httpx` |
| `time.sleep()` | `asyncio.sleep()` |
| `psycopg2` | `asyncpg` |
| `SQLAlchemy Session` | `AsyncSession` |
| `redis` | `redis.asyncio` |
| `open().read()` | `aiofiles` |

Use `run_in_threadpool()` for legacy sync libraries.

## Architecture Layers

```
Routes → Services → Repositories → Models
            ↓
       Integrations (external APIs, email, etc.)
```

| Layer | Responsibility | Rules |
|-------|---------------|-------|
| **Routes** | Request/Response, Validation | No business logic |
| **Services** | Business logic, orchestration | No direct DB queries |
| **Repositories** | Data access, queries | No business logic, always tenant-scoped |
| **Models** | SQLAlchemy ORM | Only data structure |
| **Schemas** | Pydantic I/O | Validation + serialization |
| **Integrations** | External APIs | Async, with retry/timeout |

## Multi-Tenancy

- Every database model with tenant data includes a `tenant_id` foreign key
- Tenant scoping enforced at repository level via a base mixin — never rely on endpoint code to filter
- Self-hosted mode: single tenant auto-created at startup, scoping still active (consistent code path)
- SaaS mode: tenant resolved from JWT claims

## Multi-Client Authentication

Authentication differs by client type. The backend supports multiple auth mechanisms simultaneously.

### Auth Flow per Client

| Client | Auth Flow | How Backend Identifies User |
|--------|-----------|---------------------------|
| **Web (Next.js)** | Backend-issued session cookie | Next.js forwards session cookie → backend validates and resolves user |
| **Mobile (iOS/Android)** | OAuth 2.0 Authorization Code + PKCE | JWT access token in `Authorization: Bearer` header |
| **Public API** | API key | `X-API-Key` header → resolve tenant + permissions |

### MVP Auth Methods (all clients)
1. **Magic Link / Email OTP** — passwordless, primary method
2. **Google OAuth** — social login
3. **Passkeys / WebAuthn** — modern passwordless

### Auth Roadmap (post-MVP)
- Apple OAuth (iOS app launch)
- Email + Password (traditional fallback)
- MFA / TOTP
- OIDC / external IdP (self-hosted enterprise: Keycloak, Authentik, Azure AD)
- Biometric unlock (mobile)
- Device management & trusted devices
- Impersonation (admin feature for SaaS support)

### Web Auth: Session Cookie

The backend owns all auth logic. For web clients:

- Backend issues an httpOnly session cookie after successful authentication
- Next.js forwards the session cookie to the backend on every server-side request
- The backend validates the cookie, resolves the user from Redis/DB session store
- The `get_current_user` dependency resolves the user from session cookie (web), JWT (mobile), or API key (public)
- **One user table in the backend** — no duplicate auth state

### Mobile Auth: JWT with PKCE

```
POST /api/v1/auth/mobile/magic-link/request   # Send magic link / OTP
POST /api/v1/auth/mobile/magic-link/verify     # Verify → return JWT pair
POST /api/v1/auth/mobile/oauth/google          # Google OAuth → return JWT pair
POST /api/v1/auth/mobile/passkey/register      # Register passkey
POST /api/v1/auth/mobile/passkey/authenticate  # Authenticate → return JWT pair
POST /api/v1/auth/mobile/refresh               # Refresh access token
POST /api/v1/auth/mobile/logout                # Revoke tokens
GET  /api/v1/auth/me                           # Current user (works for all clients)
```

### Token Strategy (Mobile only)

| Token | Lifetime | Purpose |
|-------|----------|---------|
| Access Token | 15 minutes | API requests |
| Refresh Token | 30 days | Token renewal |

- RS256 algorithm (asymmetric keys) for production
- Refresh token rotation on every refresh
- Token revocation via Redis (blacklist with TTL)
- Tokens stored in iOS Keychain / Android Keystore

### Token Payload (Mobile JWT)
- `sub`: User ID (UUID)
- `tenant_id`: Tenant ID
- `type`: "access" | "refresh"
- `role`: User role within tenant
- `device_id`: Registered device identifier
- `exp`, `iat`, `jti`

### Security Requirements
- Rate limiting on all auth endpoints
- Brute force protection on OTP verification
- Magic link tokens: 32 bytes, URL-safe, single-use, 15 min TTL, stored in Redis
- Passkey: WebAuthn RP ID scoped to domain, attestation optional
- CORS: strict origin allowlist (web domain + mobile deep link schemes)

### RBAC (Role-Based Access Control)

| Role | Description |
|------|-------------|
| `owner` | Full access, can delete club, manage billing |
| `admin` | User management, all settings |
| `board` | Can manage members, events, dues |
| `member` | View access, self-service (profile, event registration) |

Permissions checked via FastAPI dependencies:
```python
@router.get("/members", dependencies=[Depends(require_role(Role.BOARD))])
async def list_members(...):
```

## Public API (`/api/public/v1/`)

A separate, documented REST API for third-party integrations and user-built tools.

### Design Principles
- API key authentication (scoped per tenant, with granular permissions)
- Stricter rate limiting than internal API (configurable per plan in SaaS mode)
- Read-heavy by default — write endpoints require explicit key permissions
- Full OpenAPI/Swagger documentation auto-generated
- Stable, versioned — breaking changes only in new versions
- Subset of internal API — not every internal endpoint is exposed publicly

### Public API Endpoints (examples)
```
GET  /api/public/v1/members
GET  /api/public/v1/members/{id}
GET  /api/public/v1/events
GET  /api/public/v1/events/{id}
GET  /api/public/v1/dues/summary
POST /api/public/v1/webhooks/subscribe
```

### API Key Management
- Keys created per tenant via admin settings
- Scoped permissions: `members:read`, `events:read`, `events:write`, etc.
- Keys can be rotated and revoked
- Usage tracking and rate limit headers in responses

## Code Reuse

### Generic Base Repository

`BaseRepository[ModelType, CreateSchema, UpdateSchema]` with:
- `get_by_id(id)` — always filtered by `tenant_id`
- `get_all(skip, limit, filters)` — paginated, tenant-scoped
- `create(data, user_id)`
- `update(id, data, user_id)`
- `soft_delete(id)`
- `count(filters)`

Concrete repositories inherit and add only specific methods.

### Generic Base Service

`BaseService[RepositoryType]` with standard CRUD operations.
Concrete services inherit and add business logic.

### Model Mixins

| Mixin | Fields |
|-------|--------|
| `TimestampMixin` | `created_at`, `updated_at` |
| `AuditMixin` | `created_by`, `updated_by` + timestamps |
| `SoftDeleteMixin` | `deleted_at` |
| `TenantMixin` | `tenant_id` (FK) |

Standard base: `BaseModel` = UUID PK + Timestamp + Tenant

## API Design

### Response Format

**Success (Single)**
```json
{ "data": { ... } }
```

**Success (List)**
```json
{
  "data": [ ... ],
  "meta": {
    "total": 100,
    "page": 1,
    "per_page": 20,
    "total_pages": 5
  }
}
```

**Error**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human readable message"
  },
  "details": [
    { "field": "email", "message": "Invalid email format" }
  ]
}
```

### Pagination
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20, max: 100)
- `sort_by`: Sort field
- `sort_order`: `asc` | `desc`

### Filtering
- Simple: query params (`?status=active&role=member`)
- Complex: `POST /search` with filter body

## Pydantic Schemas

| Schema | Purpose |
|--------|---------|
| `{Entity}Create` | POST body |
| `{Entity}Update` | PATCH body (all fields optional) |
| `{Entity}Response` | API response |
| `{Entity}ListResponse` | Paginated list |
| `{Entity}Filter` | Query filter |

Rules:
- `model_config = ConfigDict(from_attributes=True)`
- Strict validation with field constraints
- No sensitive data in responses

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Settings via pydantic-settings
│   ├── database.py          # Async engine, session factory
│   ├── dependencies.py      # Shared deps (current_user, current_tenant, db session)
│   ├── api/
│   │   ├── v1/
│   │   │   ├── router.py    # Aggregated v1 router
│   │   │   ├── auth.py
│   │   │   ├── members.py
│   │   │   ├── events.py
│   │   │   ├── dues.py
│   │   │   ├── communications.py
│   │   │   └── settings.py
│   │   ├── public/
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       ├── members.py
│   │   │       └── events.py
│   │   └── middleware/
│   │       ├── logging.py
│   │       └── rate_limit.py
│   ├── models/
│   │   ├── base.py          # Base model with UUID, timestamps, tenant
│   │   ├── tenant.py
│   │   ├── user.py
│   │   ├── member.py
│   │   ├── event.py
│   │   ├── due.py
│   │   └── api_key.py
│   ├── schemas/
│   │   ├── base.py
│   │   ├── auth.py
│   │   ├── member.py
│   │   ├── event.py
│   │   └── due.py
│   ├── repositories/
│   │   ├── base.py          # Generic BaseRepository[T]
│   │   ├── member.py
│   │   ├── event.py
│   │   └── due.py
│   ├── services/
│   │   ├── base.py          # Generic BaseService[T]
│   │   ├── auth.py
│   │   ├── member.py
│   │   ├── event.py
│   │   ├── due.py
│   │   └── notification.py
│   ├── core/
│   │   ├── security.py      # JWT (mobile), API key validation, BFF trust verification
│   │   ├── passkey.py       # WebAuthn/passkey registration & verification
│   │   └── exceptions.py    # Custom exceptions + handlers
│   ├── integrations/        # External APIs (email, payment, etc.)
│   │   ├── base.py          # BaseIntegration (async httpx, retry, timeout)
│   │   ├── email.py
│   │   └── payment.py
│   ├── events/              # Event logging / audit trail
│   │   ├── publisher.py
│   │   └── models.py
│   └── tasks/               # Background tasks
├── alembic/
├── alembic.ini
├── pyproject.toml
├── Dockerfile
└── tests/
    ├── conftest.py          # Fixtures (async client, test DB, test tenant)
    ├── test_auth.py
    ├── test_members.py
    └── test_public_api.py
```

## Event Logging / Audit Trail

- `user_id`: Triggering user
- `tenant_id`: Tenant scope
- `entity_type`: e.g. "member", "event", "due"
- `entity_id`: UUID of affected entity
- `action`: "created", "updated", "deleted"
- `payload`: Changed fields (old/new values)
- `timestamp`, `ip_address`

Log all create/update/delete operations, login/logout, permission changes, sensitive data access.

## Background Tasks

### Light tasks: FastAPI BackgroundTasks
- Sending emails / notifications
- Audit logging
- Webhook delivery

### Heavy tasks: ARQ + Redis
- Report generation (e.g. annual member report)
- Bulk operations (e.g. mass email, dues calculation)
- Scheduled jobs (e.g. payment reminders, membership expiry checks)

## Database

### Connection Pooling
- `pool_size`: 10, `max_overflow`: 20
- `pool_pre_ping`: True
- `pool_recycle`: 3600

### Conventions
- UUIDs as primary keys
- Soft deletes where audit trail matters (members, financial records)
- `created_at`, `updated_at` on every model
- All foreign keys indexed
- Composite index for frequent query combinations
- `deleted_at` index for soft-delete queries

### Migrations
- Alembic for all schema changes
- No manual DB changes
- Down-migrations for rollbacks
- Always review auto-generated migrations before applying

## Testing

### Stack
- **pytest** + **pytest-asyncio** for all tests
- **httpx.AsyncClient** for API endpoint tests
- **Testcontainers** for PostgreSQL (real DB in tests)
- **Factory Boy** for test data factories
- **respx** or **pytest-httpx** for mocking external HTTP calls

### What to Test

| Layer | Test Type | What to Verify |
|-------|-----------|---------------|
| **Services** | Unit | Business logic, validation, edge cases |
| **Repositories** | Integration | Queries return correct data, tenant isolation, soft deletes |
| **API Endpoints** | Integration | Status codes, response format, auth/permission checks, pagination |
| **Auth (mobile)** | Integration | Token issuance, refresh, revocation, PKCE flow, passkey flow |
| **Auth (BFF trust)** | Integration | Internal header validation, shared secret verification |
| **Public API** | Integration | API key auth, rate limiting, scoped permissions, response format |
| **Background Tasks** | Unit | Task logic executes correctly (mock I/O) |

### Test Structure
```
tests/
├── conftest.py              # Shared fixtures: async client, test DB, test tenant, test user
├── factories/               # Factory Boy factories
│   ├── member.py
│   ├── event.py
│   └── user.py
├── api/
│   ├── v1/
│   │   ├── test_auth_mobile.py
│   │   ├── test_auth_bff.py
│   │   ├── test_members.py
│   │   ├── test_events.py
│   │   └── test_dues.py
│   └── public/
│       └── v1/
│           ├── test_members.py
│           └── test_api_keys.py
├── services/
│   ├── test_member_service.py
│   └── test_due_service.py
└── repositories/
    └── test_member_repository.py
```

### Test Conventions
- Each test in its own transaction (rollback after test)
- Separate test database via Testcontainers (no shared state)
- Never mock the database — use real PostgreSQL
- Mock external services (email, payment, etc.)
- Test tenant isolation: verify that Tenant A cannot access Tenant B's data
- Every new endpoint needs at minimum: happy path, auth failure, validation error, not found
- Auth tests need 100% coverage — test every edge case

### Key Fixtures
```python
@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]: ...

@pytest.fixture
async def test_tenant(db_session) -> Tenant: ...

@pytest.fixture
async def test_user(db_session, test_tenant) -> User: ...

@pytest.fixture
async def auth_client(test_user) -> AsyncClient:
    """Pre-authenticated client (mobile JWT)."""

@pytest.fixture
async def bff_client(test_user) -> AsyncClient:
    """Pre-authenticated client (BFF internal headers)."""

@pytest.fixture
async def public_api_client(test_tenant) -> AsyncClient:
    """Client with valid API key."""

@pytest.fixture
async def anon_client() -> AsyncClient:
    """Unauthenticated client."""
```

### Review Checklist (Backend-specific)
Before marking backend work as done:
- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] `mypy --strict` passes
- [ ] `pytest` passes with no failures
- [ ] Coverage meets thresholds (80% services, 100% auth)
- [ ] New endpoints have tests (happy path + error cases)
- [ ] Tenant isolation verified in new queries
- [ ] No N+1 queries (check with `echo` or `log` SQL in tests)
- [ ] Alembic migration reviewed (if DB changes)
- [ ] No sensitive data in responses or logs

## Code Style

- **Formatter/Linter**: Ruff
- **Type Checker**: mypy (strict mode)
- **Line Length**: 100 characters
- **Docstrings**: Google style for public APIs

## Deployment

### Docker
- Multi-stage build for small images
- Non-root user
- Health check endpoint

### Production Server
```
Gunicorn + Uvicorn Workers
- Workers: 2-4 × CPU Cores
- Worker Class: uvicorn.workers.UvicornWorker
```

### Health Checks
- `/health`: Basic (200 OK)
- `/health/ready`: DB + Redis connection check
- `/health/live`: Kubernetes liveness

### Environment Variables
All secrets via environment:
- `DATABASE_URL`, `REDIS_URL`
- `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` (RS256, for mobile auth)
- `INTERNAL_API_SECRET` (shared secret for Next.js BFF → backend trust)
- `DEPLOYMENT_MODE` (`self-hosted` | `saas`)
- `DEFAULT_TENANT_ID` (for self-hosted)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `WEBAUTHN_RP_ID`, `WEBAUTHN_RP_NAME`, `WEBAUTHN_ORIGIN`
- Email/SMTP credentials
- Payment provider credentials

## Commands
- `uv run fastapi dev` — Start dev server with hot reload
- `uv run pytest` — Run tests
- `uv run alembic upgrade head` — Apply migrations
- `uv run alembic revision --autogenerate -m "description"` — Create migration
- `uv run ruff check .` — Lint
- `uv run ruff format .` — Format

## Forbidden

### Architecture
- Business logic in routes
- Direct DB queries outside repositories
- Sync DB operations in async functions
- Tenant-unscoped queries on tenant data

### Code Style
- `print()` statements (use `logging` / `structlog`)
- Hardcoded secrets (environment variables only)
- `*` imports
- Bare `except:` clauses
- `Any` type without good reason

### Security
- Passwords in logs or responses
- Tokens in URLs
- Sensitive data without encryption
- CORS `*` in production
- Public API endpoints without rate limiting

### Performance
- N+1 queries (always use `joinedload`/`selectinload`)
- Unbounded list responses (always paginate)
- Blocking I/O in async functions
- Large payloads without streaming
