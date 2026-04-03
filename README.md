<p align="center">
  <h1 align="center">unefy</h1>
  <p align="center">
    <strong>Open-source club & association management platform</strong>
  </p>
  <p align="center">
    Self-hostable &middot; SaaS-ready &middot; AI-powered
  </p>
  <p align="center">
    <a href="#features">Features</a> &middot;
    <a href="#architecture">Architecture</a> &middot;
    <a href="#getting-started">Getting Started</a> &middot;
    <a href="#contributing">Contributing</a>
  </p>
</p>

<!-- TODO: Add CI badge when pipeline is set up -->
<!-- [![CI](https://github.com/org/unefy/actions/workflows/ci.yml/badge.svg)](https://github.com/org/unefy/actions) -->
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

---

> [!NOTE]
> **Early development** — we're building the architecture and core features. Not yet functional. Expect breaking changes.

---

## Why unefy?

Club management in the DACH region is stuck in the past — spreadsheets, paper forms, and legacy software from the 2000s. unefy brings club administration into 2026 with a modern stack, mobile-first design, and AI features that actually help.

## Features

| | Feature | Description |
|---|---------|-------------|
| :busts_in_silhouette: | **Members** | Profiles, roles, membership lifecycle, self-service portal |
| :calendar: | **Events** | Create, register, track attendance |
| :credit_card: | **Dues & Payments** | Fee management, reminders, financial overview |
| :envelope: | **Communications** | Email, newsletters, push notifications |
| :brain: | **AI Features** | On-device intelligence — camera-based analysis, smart insights, natural language interaction. All processing on-device, no data leaves the phone. |
| :globe_with_meridians: | **Public API** | REST API for integrations and custom tooling |
| :package: | **Self-Hosted** | `docker compose up` — done |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    unefy platform                   │
├──────────┬──────────┬───────────┬───────────────────┤
│  Web     │  iOS     │  Android  │  Public API       │
│  Next.js │  Swift   │  Kotlin   │  REST + API Keys  │
│  BFF     │  Native  │  Native   │                   │
├──────────┴──────────┴───────────┴───────────────────┤
│                  FastAPI Backend                    │
│          PostgreSQL  ·  Redis  ·  JWT               |
└─────────────────────────────────────────────────────┘
```

| Component | Stack |
|-----------|-------|
| **Backend** | FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, Alembic |
| **Web** | Next.js 16, React 19, Tailwind v4, shadcn/ui |
| **iOS** | Swift 6.2, SwiftUI, Liquid Glass, Core ML, Foundation Models |
| **Android** | Kotlin, Jetpack Compose, Material 3, CameraX, MediaPipe |

**Key decisions:**
- Multi-tenant from day one (self-hosted = single tenant, SaaS = multi)
- Passwordless-first: Magic Link, Passkeys, Google OAuth
- On-device AI — privacy-first, no user data leaves the device
- Backend is the single source of truth for all clients

## Built with AI

This project is developed using **agentic coding** with [Claude Code](https://claude.ai/claude-code). Every component has a detailed `CLAUDE.md` that serves as an engineering playbook — defining architecture, patterns, conventions, and constraints.

AI writes the code. Quality gates keep it honest:

- **100%** test coverage on auth logic
- **80%+** coverage on services and API endpoints
- Automated linting, type checking, and formatting
- PR-based review with mandatory CI checks
- Architectural constraints enforced via CLAUDE.md files

The goal: prove that AI-assisted development produces **production-grade software**, not prototypes.

## Getting Started

> Coming soon. The project is in the scaffolding phase.

```bash
# Self-hosted (planned)
git clone https://github.com/your-org/unefy.git
cd unefy
docker compose up
```

**Prerequisites:** Docker, Node.js 22+, Python 3.12+, Xcode 26+ (iOS), Android Studio (Android)

## Project Structure

```
unefy/
├── apps/web/           → Next.js frontend
├── apps/mobile/ios/    → Swift / SwiftUI
├── apps/mobile/android → Kotlin / Compose
├── backend/            → FastAPI
├── docker/             → Deployment
├── docs/               → Specs & architecture
└── CLAUDE.md           → Architecture playbook
```

## Contributing

The project is in early development. Read the `CLAUDE.md` files to understand the architecture before diving in. Issues and discussions welcome.

## License

**AGPL v3** — [GNU Affero General Public License v3.0](LICENSE)

You can **self-host, modify, and use unefy freely** — including for clubs and associations that collect membership fees. The AGPL ensures that if anyone offers a modified version as a network service (e.g., a competing SaaS), they must publish their complete source code under the same license.

Commercial licensing is available for organizations that need different terms. [Contact us](mailto:hallo@unefy.app) for details.
