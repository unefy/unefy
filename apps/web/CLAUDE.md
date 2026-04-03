# Frontend: Next.js Web App

Web frontend for unefy club management. Acts as BFF (Backend for Frontend) — all backend communication goes through Server Actions, never directly from the browser.

## Core Principle: Streaming-First

**Top rule: The page MUST load immediately. Data arrives asynchronously.**

```
User clicks → Immediately: Shell + Skeletons (< 100ms) → Streaming: Data fills in
```

Never wait until all data is available. Each component fetches its own data and streams in independently.

### Page Architecture: Static Shell + Async Islands

```typescript
// ❌ WRONG: Page waits for data
export default async function MembersPage() {
  const members = await getMembers()  // Blocks!
  return <MemberList members={members} />
}

// ✅ CORRECT: Page loads immediately, data streams in parallel
import { Suspense } from "react"

export default function MembersPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Members" />

      <div className="grid grid-cols-4 gap-4">
        <Suspense fallback={<StatCardSkeleton />}>
          <TotalMembersCount />
        </Suspense>
        <Suspense fallback={<StatCardSkeleton />}>
          <NewMembersThisMonth />
        </Suspense>
        <Suspense fallback={<StatCardSkeleton />}>
          <OpenDuesCount />
        </Suspense>
        <Suspense fallback={<StatCardSkeleton />}>
          <ActiveEventsCount />
        </Suspense>
      </div>

      <Suspense fallback={<TableSkeleton rows={10} />}>
        <MembersTable />
      </Suspense>
    </div>
  )
}
```

Each "Island" is its own async Server Component that fetches independently.

## Tech Stack

- **Next.js 16** with App Router and Turbopack
- **React 19** with Server Components where appropriate
- **Tailwind CSS v4** with @theme tokens
- **shadcn/ui v4** (base-ui based) for UI components
- **Hugeicons** for iconography
- **next-themes** for dark/light mode
- **Zod** for schema validation
- **React Hook Form** for complex forms
- **Server Actions** as primary data layer (BFF to FastAPI)

## Architecture

### Data Fetching
- Server Components fetch data via Server Actions that proxy to the backend API
- Every Server Action returns `{ success: boolean; error?: string; data?: T }`
- No direct API calls from browser to backend — Next.js acts as BFF
- Parallel data loading via separate Suspense boundaries (never sequential awaits)

### Backend Connection (BFF Pattern)

```typescript
// lib/api.ts — BFF client that forwards authenticated requests to backend
const API_BASE = process.env.API_URL // http://backend:8000
const INTERNAL_SECRET = process.env.INTERNAL_API_SECRET

export async function apiCall<T>(
  path: string,
  options?: RequestInit & { userId?: string; tenantId?: string }
): Promise<T> {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) throw new Error("Unauthorized")

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": session.user.id,
      "X-Tenant-Id": session.user.tenantId,
      "X-Internal-Secret": INTERNAL_SECRET,
      ...options?.headers,
    },
  })

  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

**Note:** The BFF forwards the session cookie to the backend on every request. The backend validates the session and resolves the user — no auth logic in the frontend.

### Authentication (Backend-Managed)

**All auth logic lives in the backend. The frontend is a thin cookie-forwarding layer.**

- Backend issues httpOnly session cookies after successful auth (Google OAuth, Magic Link, Passkeys)
- Next.js forwards the session cookie to the backend on every server-side request
- `getSession()` helper calls `GET /api/v1/auth/me` with the forwarded cookie
- Auth guard in `(app)/layout.tsx` redirects to `/login` if no session
- Login page redirects to backend OAuth/magic-link endpoints
- No auth libraries in the frontend — just cookie forwarding

```typescript
// lib/auth.ts — server-side session helper
export async function getSession(): Promise<Session | null> {
  const cookieStore = await cookies()
  const sessionCookie = cookieStore.get("session")?.value
  if (!sessionCookie) return null

  const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: { Cookie: `session=${sessionCookie}` },
  })
  if (!res.ok) return null
  return (await res.json()).data
}
```

### State Management
- Server state: Server Components + Server Actions (no client-side cache layer initially)
- Client state: React `useState`/`useReducer` for local UI state only
- URL state: `useSearchParams` for filters, pagination, tabs
- No global state library unless complexity demands it later

## Server Actions (Primary Data Layer)

```typescript
// actions/members.ts
"use server"

import { revalidatePath } from "next/cache"
import { getSession } from "@/lib/auth"

type ActionResult<T> =
  | { success: true; data: T }
  | { success: false; error: string; fieldErrors?: Record<string, string[]> }

export async function createMember(
  formData: FormData
): Promise<ActionResult<Member>> {
  const session = await getSession()
  if (!session) return { success: false, error: "Not authenticated" }

  const parsed = memberSchema.safeParse(Object.fromEntries(formData))
  if (!parsed.success) {
    return {
      success: false,
      error: "Validation error",
      fieldErrors: parsed.error.flatten().fieldErrors
    }
  }

  try {
    const member = await apiCall<Member>("/api/v1/members", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
    revalidatePath("/members")
    return { success: true, data: member }
  } catch (e) {
    return { success: false, error: "Could not create member" }
  }
}
```

## React 19 Hooks

- **`useActionState`**: Primary hook for form state with Server Actions
- **`useFormStatus`**: Submit button loading states (must be child of `<form>`)
- **`useOptimistic`**: Instant UI feedback during Server Action execution
- **`useTransition`**: Non-blocking navigation and filter updates
- **`use`**: Read promises in Client Components (never create inline promises)

## Code Conventions

### TypeScript
- Strict mode, no `any`
- Prefer `interface` over `type` for object shapes
- Use Zod for form validation
- Shared API types in `lib/types/`

### Styling
- Tailwind CSS v4 with design tokens via `@theme`
- shadcn/ui components installed via CLI — do NOT create manually
- Dark mode support from day one via `next-themes`
- Responsive design: mobile-first approach
- Clean, modern, minimalist aesthetic (SaaS/Admin-Dashboard)
- Subtle animations (150-200ms), `transition-colors`, `transition-opacity`

### shadcn/ui Rules (CRITICAL)

**Only import from `@/components/ui/*` — NEVER import primitives directly in feature code.**

- ✅ `import { Button } from "@/components/ui/button"`
- ❌ `import { Button } from "@base-ui/react/button"` in pages/features
- ❌ Raw HTML for interactive UI (`<button>`, `<input>`) — always use shadcn
- Primitive imports are ONLY allowed inside `components/ui/*`
- Install via CLI: `npx shadcn@latest add [component-name]`

### File Structure (no src/ directory)
```
app/
├── (auth)/              # Login, register, password reset
├── (dashboard)/         # Authenticated app shell
│   ├── members/         # Member management
│   ├── events/          # Event management
│   ├── dues/            # Dues & payments
│   ├── communications/  # Emails, newsletters
│   ├── documents/       # Document management
│   └── settings/        # Club & user settings
├── globals.css
├── layout.tsx
└── page.tsx             # Landing / redirect

actions/                 # Server Actions (primary data layer)
├── members.ts
├── events.ts
├── dues.ts
├── auth.ts
└── ...

components/
├── ui/                  # shadcn components (CLI-managed)
├── layout/              # Shell, sidebar, navigation
├── skeletons/           # All skeleton components
│   ├── primitives.tsx   # TextSkeleton, CardSkeleton, etc.
│   ├── composed.tsx     # StatCardSkeleton, TableSkeleton, etc.
│   └── index.ts
├── members/             # Member-specific components
├── events/              # Event-specific components
├── dues/                # Dues-specific components
└── common/              # Shared components (data tables, forms, etc.)

lib/
├── api.ts               # Backend API client (internal, for Server Actions)
├── auth.ts              # getSession() helper (calls backend /auth/me)
├── types/               # Shared TypeScript interfaces
├── validations/         # Zod schemas
└── utils.ts             # cn() helper and utilities

hooks/                   # Custom React hooks (UI-only)

messages/                # i18n translation files (de, en)
```

### Component Guidelines
- One component per file, named export matching filename
- Props interfaces named `{ComponentName}Props`
- Use `cn()` for conditional class merging
- Components max 150 lines — split if larger
- Default exports for pages, named exports for components

### Loading States & Skeletons (MANDATORY)

Every async component needs a matching skeleton:

```typescript
// components/skeletons/composed.tsx
export function StatCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="h-4 w-24 bg-muted animate-pulse rounded" />
      </CardHeader>
      <CardContent>
        <div className="h-8 w-16 bg-muted animate-pulse rounded" />
      </CardContent>
    </Card>
  )
}

export function TableSkeleton({ rows = 5, columns = 4 }: Props) {
  return (
    <div className="border rounded-lg divide-y">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="p-4 flex gap-4">
          {Array.from({ length: columns }).map((_, j) => (
            <div key={j} className="h-4 bg-muted animate-pulse rounded flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}
```

Rules:
1. Every async component needs a skeleton — no exceptions
2. Skeleton layout must match real component dimensions
3. Granular Suspense boundaries — prefer 5 small over 1 large
4. `animate-pulse` consistently everywhere
5. Every route group needs a `loading.tsx`

## Reusable UI Patterns

These patterns MUST be consistent across all modules:

### DataTable
- Sorting, filtering, pagination
- Row actions (Edit, Delete, etc.)
- Bulk actions where useful
- Empty state with call-to-action

### DetailPage
- Header with title, breadcrumb, actions
- Tabs for sub-sections (each with own Suspense)
- Sidebar for metadata (optional)
- Activity log

### FormDialog / FormPage
- Consistent field layout
- Cancel/Save actions
- Validation feedback (inline + toast)
- Loading state via `useFormStatus`

## Testing

### Stack
- **Vitest** for unit + integration tests
- **React Testing Library** for component tests
- **Playwright** for E2E tests (shared with backend, runs full stack)
- **MSW (Mock Service Worker)** for mocking backend API in component/integration tests

### What to Test

| Layer | Test Type | What to Verify |
|-------|-----------|---------------|
| **Server Actions** | Integration | Correct API calls, error handling, revalidation, auth checks |
| **Components** | Component | User interactions, form validation, conditional rendering |
| **Auth flows** | E2E | Magic link, Google OAuth, passkey registration, session persistence |
| **Critical paths** | E2E | Member CRUD, event registration, dues management |

### Test Structure
```
__tests__/
├── actions/           # Server Action tests
│   ├── members.test.ts
│   └── auth.test.ts
├── components/        # Component tests
│   ├── members/
│   └── common/
└── e2e/               # Playwright E2E tests (or in root /e2e/)
    ├── auth.spec.ts
    ├── members.spec.ts
    └── events.spec.ts
```

### Test Conventions
- Test file next to source or in `__tests__/` mirroring structure
- Name: `{source}.test.ts` (unit/integration), `{flow}.spec.ts` (E2E)
- Use `describe` blocks grouped by function/component
- Test the user-visible behavior, not implementation details
- Mock the backend API (via MSW), never mock React internals
- Every Server Action test must verify: auth check, validation, API call, revalidation, error case

### Review Checklist (Frontend-specific)
Before marking frontend work as done:
- [ ] `npm run typecheck` passes
- [ ] `npm run lint` passes
- [ ] `vitest run` passes
- [ ] `npm run build` succeeds (catches SSR/build issues)
- [ ] New async components have skeletons
- [ ] New pages have `loading.tsx`
- [ ] All new UI text uses i18n
- [ ] Tested in dark mode
- [ ] Tested on mobile viewport

## Commands
- `npm run dev` — Start dev server with Turbopack
- `npm run build` — Production build
- `npm run lint` — ESLint
- `npm run typecheck` — TypeScript type checking
- `npm run format` — Prettier formatting
- `npm run test` — Run Vitest
- `npm run test:coverage` — Vitest with coverage
- `npm run e2e` — Playwright E2E tests

## Forbidden

### TypeScript & Code Style
- `any` type (including `as any` casts)
- Inline styles
- `!important` in Tailwind
- Direct DOM manipulation
- `console.log` in commits
- Hardcoded colors/spacing outside Tailwind
- German variable names

### UI Anti-Patterns
- Primitive imports outside `components/ui/`
- Raw HTML for interactive UI
- Mixed UI libraries (no Material UI, Chakra, etc.)
- Pages without `loading.tsx`
- Spinners instead of skeletons
- `useState` + `useEffect` for server data (use Server Actions)
- `useFormStatus` outside of `<form>` children

### Server Actions Anti-Patterns
- Server Actions in `lib/` instead of `actions/`
- Missing `"use server"` directive
- Sensitive data in action returns
- Client-side fetch for CRUD
- Mutations without `revalidatePath`/`revalidateTag`
- Actions that don't check session
