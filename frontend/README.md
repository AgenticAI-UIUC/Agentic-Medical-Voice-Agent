# Frontend (Next.js)

The client application for the full-stack project. Built with Next.js App Router, React 19, and TypeScript.

## Architecture

```text
src/
├── app/                        # Next.js App Router
│   ├── (auth)/login/           # Login page
│   ├── (dashboard)/            # Protected layout
│   │   ├── users/              # Admin user management
│   │   └── settings/           # Profile & password
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # Home / dashboard
│   ├── error.tsx               # Global error boundary
│   └── not-found.tsx           # 404 page
├── components/
│   ├── ui/                     # shadcn/ui primitives
│   ├── common/                 # Shared components (forms, dialogs, pagination)
│   └── forms/                  # Profile & password forms
├── hooks/                      # React Query hooks
│   ├── use-auth.ts             # Login, current user, password
│   └── use-users.ts            # User CRUD mutations/queries
└── lib/
    ├── api/                    # Typed API client
    │   ├── client.ts           # Core fetch wrapper + ApiError
    │   ├── login.ts            # Auth endpoints
    │   ├── users.ts            # User endpoints + types
    │   ├── health.ts           # Health check
    │   ├── auth.ts             # Token storage (localStorage)
    │   └── errors.ts           # Error formatting utilities
    ├── config.ts               # Environment variable access
    └── query-client.ts         # TanStack Query configuration
```

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **Language**: TypeScript (strict mode)
- **UI**: Tailwind CSS v4, shadcn/ui, Radix UI, Lucide icons
- **Data fetching**: TanStack Query v5
- **Forms**: React Hook Form + Zod validation
- **Toasts**: Sonner
- **Theming**: next-themes (light/dark mode)

## Requirements

- Node.js 18+ (LTS recommended)
- [pnpm](https://pnpm.io/)

## Setup

```bash
cd frontend
pnpm install
cp .env.local.example .env.local
```

## Environment Variables

| Variable                   | Required | Default | Description                       |
| -------------------------- | -------- | ------- | --------------------------------- |
| `NEXT_PUBLIC_API_BASE_URL` | Yes      | —       | Backend API URL (e.g. `http://localhost:8000`) |
| `NEXT_PUBLIC_APP_NAME`     | No       | `App`   | Display name used in the UI       |

## Running

```bash
# Development
pnpm dev
# → http://localhost:3000

# Production build
pnpm build
pnpm start
```

## Scripts

| Script       | Command           | Description                |
| ------------ | ----------------- | -------------------------- |
| `dev`        | `next dev`        | Start dev server           |
| `build`      | `next build`      | Production build           |
| `start`      | `next start`      | Serve production build     |
| `lint`       | `eslint`          | Run ESLint                 |
| `typecheck`  | `tsc --noEmit`    | TypeScript type checking   |

## Pages

| Route       | Description                                        |
| ----------- | -------------------------------------------------- |
| `/`         | Dashboard home with health check                   |
| `/login`    | OAuth2 login form                                  |
| `/users`    | Admin user management (superuser only)             |
| `/settings` | Profile editing and password change                |

## API Client

The API client layer is split by domain:

- `lib/api/client.ts` — core `apiFetch<T>()` wrapper with automatic JSON handling, token injection, and `ApiError` class
- `lib/api/login.ts` — `loginAccessToken()`
- `lib/api/users.ts` — user CRUD + profile endpoints with TypeScript types
- `lib/api/health.ts` — health check

Each domain module is consumed by a corresponding React Query hook in `hooks/`.
