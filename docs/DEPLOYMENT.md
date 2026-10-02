# Deploying GramShiksha

> **Status: LIVE.** Backend on Render (`https://gramshiksha-backend.onrender.com`),
> SPA on Vercel (`https://gramshiksha-academy.vercel.app`), Postgres on Neon,
> uploads on Cloudinary. This runbook is both the record of how it was built
> and the path to rebuild it. SMTP is the one piece still gated on account
> verification (see step 1).

## Topology

```
Browser ──▶ Vercel (React SPA, static)
              │  /api/* rewritten (frontend/vercel.json)
              ▼
            Render (Docker · FastAPI · render.yaml blueprint)
              │
              ├── Neon/Supabase Postgres   (DATABASE_URL)
              ├── Cloudinary               (uploads — Render's disk is ephemeral)
              └── SMTP provider            (password-reset emails)
```

Same-origin by design: the SPA calls `/api` on its own host, Vercel proxies to
Render, so CORS is only a factor if you point `VITE_API_URL` straight at the API.

## 0. Accounts needed (all have free tiers)

| Account | Provides | Lands in |
|---|---|---|
| [Render](https://render.com) | backend host | service env (render.yaml) |
| [Vercel](https://vercel.com) | frontend host | project settings |
| [Neon](https://neon.tech) or Supabase | managed Postgres | `DATABASE_URL` |
| [Cloudinary](https://cloudinary.com) | upload storage | `CLOUDINARY_*` |
| SMTP: [Brevo](https://brevo.com), Mailgun, or a Gmail **app password** | reset emails | `SMTP_*` |
| Sentry (optional) | error tracking | `SENTRY_DSN` |

## 1. Secrets — Render service environment (names match `render.yaml` exactly)

| Variable | How it's set | If missing |
|---|---|---|
| `APP_ENV` | preset `production` | — (this is what makes the guards fire at all) |
| `JWT_SECRET` | preset, auto-generated | boot refused (known dev key = forged admin tokens) |
| `DATABASE_URL` | **you fill it** (`sync: false`) | boot refused: would run on ephemeral SQLite |
| `CLOUDINARY_CLOUD_NAME` / `_API_KEY` / `_API_SECRET` | **you fill them** | boot refused: uploads would die on redeploy |
| `SMTP_HOST` / `_PORT` / `_USER` / `_PASSWORD` / `_FROM` | **you fill them** | boots, but `/auth/reset-request` answers `503` (never silently swallows a request) |
| `CORS_ORIGINS` | preset `["https://gramshiksha-academy.vercel.app"]` | adjust if your frontend URL differs |
| `ADSENSE_CLIENT` / `ADSENSE_SLOT`, `DONATE_UPI` / `DONATE_URL`, `AFFILIATE_LINKS`, `SPONSOR_TEXT` / `SPONSOR_URL`, `PREMIUM_URL` | **you fill them** as each stream unlocks (`sync: false`) | empty = that money slot is hidden, site runs identically |
| `SENTRY_DSN` | optional | error tracking disabled |
| `SEED_DEMO` | leave unset | `auto` = off on Postgres → demo logins are **never** created |
| `ENABLE_DOCS` | leave unset | off in production (`/docs` hidden) |

**Connection-string shape:** Neon/Supabase give `postgres://user:pass@host/db?sslmode=require`.
The driver needs the prefix `postgresql+psycopg://` — same string, different scheme.
`backend/.env.example` has both forms commented side by side.

## 2. Backend on Render

1. Render → **New → Blueprint** → connect `github.com/demolished-lab/gramshiksha`.
   Render reads `render.yaml` at the repo root: service `gramshiksha-backend`,
   Docker runtime (builds `backend/Dockerfile`), health check `GET /ready`.
2. Fill the four `sync: false` secret groups from step 1 (`DATABASE_URL`,
   Cloudinary ×3, SMTP ×5). `JWT_SECRET` generates itself.
3. **Deploy.** Boot order: `check_production_safety()` → `alembic upgrade head`
   (3 revisions) → content seed. A misconfiguration fails the deploy with the
   offending variable named in the log — by design, fix and redeploy.

Verify: `GET https://<service>.onrender.com/ready` → `{"status":"ready"}`,
`/health` → ok, `/docs` → hidden.

## 3. Create the first platform admin

Demo accounts don't seed on Postgres, so a fresh instance has **nobody** who
can approve teachers until you mint one. Render's Shell is **paid-only on the
Free plan**, so run the bootstrap locally against the production database:

```sh
cd backend && python -m app.bootstrap_admin admin@your-school.ac.in 'a-strong-password'
```

(uses the production `DATABASE_URL` from the secrets store; idempotent —
re-running resets that account's password and re-promotes it).
Never set `SEED_DEMO=true` on a public instance — it would create the demo
logins with the passwords printed in the README.

## 4. Frontend on Vercel (CLI-only, deliberately **not** connected to GitHub)

The project is linked to the repo owner's account by token, never by the GitHub
integration — pushes to `main` deploy Render only, and that is intentional
(the ownership split is documented in `LICENSE`).

1. Project `gramshiksha` exists under the deploy account; the deploy token and
   IDs live in the operator's secrets store (`VERCEL_TOKEN`, `VERCEL_ORG_ID`,
   `VERCEL_PROJECT_ID`) — never in the repo.
2. `VITE_API_URL` stays empty: `frontend/vercel.json` rewrites `/api/*` to
   `https://gramshiksha-backend.onrender.com/api/*`.
3. Ship a frontend change:

   ```sh
   cd frontend
   npx vercel deploy --prod --yes --token "$VERCEL_TOKEN"   # with VERCEL_ORG_ID/PROJECT_ID set
   ```

4. Production URL: `https://gramshiksha-academy.vercel.app` (the apex
   `gramshiksha.vercel.app` belongs to another team, so the project carries
   this alias instead). Deployment Protection is **Standard** (public).
   If the origin ever changes, update `CORS_ORIGINS` in `render.yaml` and let
   the backend redeploy.

## 5. Smoke test (the first real test of the environment)

- [ ] `GET /ready` → `ready`; migrations ran (log shows `Running upgrade … c4d81a6b90ef`)
- [ ] `/docs` returns nothing (attack surface hidden)
- [ ] Register a **teacher** → `#/teacher` shows *Awaiting approval*, and the
      *Check approval status* button reports pending
- [ ] Log in as the admin from step 3 → approve the teacher → teacher's
      re-check flips the screen → they can publish a lesson
- [ ] Suspend them → teacher routes answer `403 Account suspended` → approve restores
- [ ] Upload a material (as an approved teacher) → lands `approved`, survives a
      **redeploy** (proves Cloudinary, not the ephemeral disk)
- [ ] Password reset: real address receives mail (SMTP); unknown address gets
      the same `200` (no account enumeration); code is single-use
- [ ] Student login works; `/api/admin/users` answers `403` for a student

## 6. Day-2 notes

- **Push to `main` = deploy for Render only**: the blueprint auto-deploys and
  migrations run at boot, so schema changes ship with the push. CI must be
  green first (SQLite + Postgres + frontend jobs). **Vercel does not
  auto-deploy** — no Git integration by design (see step 4); ship frontend
  changes with the CLI command above.
- **Rotating `JWT_SECRET`** logs every user out (all tokens are signed with it).
- **Rate limits are in-process**: they reset on restart and are per-instance —
  fine for a single free instance; move to a shared store before scaling out.
- **Backups**: Neon keeps its own; this app has no export tool — use the
  provider's PITR/snapshots.
- **Logs ↔ errors**: every response carries `X-Request-ID`; quote it when a 500
  returns `{"detail": "Internal server error", "request_id": "…"}`.
- **Free-tier realities**: Render's free instance sleeps on inactivity (a cold
  start costs the first visitor 50+ s) and the disk is ephemeral — both are
  accounted for. `.github/workflows/keep-warm.yml` pings `/ready`,
  `/api/growth/config` and `/api/feed.xml` every 10 minutes (under Render's
  ~15 min idle cutoff), so the container never sleeps and no visitor eats a
  cold start. It costs $0 — the repo is public, so Actions minutes are
  unlimited — and it keeps the whole path hot (proxy → app → Postgres), not
  just the socket. `workflow_dispatch` is on it for a manual kick; the
  Actions tab's `keep-warm` badge is the health signal (if it ever goes red
  the backend is truly unreachable, since the job fails on connection error).
  Caveats: GitHub runs schedules only from `main` and pauses them after ~60
  days without repo activity, so keep committing (the loop already does).
