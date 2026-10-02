# GramShiksha — ग्रामशिक्षा

**A free, trilingual (English · हिंदी · मराठी) school e-learning portal for Class 1–12** —
Maharashtra SSC, Maharashtra HSC and CBSE — built for rural & semi-urban students with
slow internet, shared phones and limited data.

> Learn → Practice → Test → **Find Weakness** → Revise → Improve

## What's inside

| Area | Details |
|---|---|
| **Roles** | Student, Teacher, Parent, School Admin, Platform Admin (JWT auth) |
| **Teacher approval** | Self-registered teachers start **pending**: no publish/moderate/roster powers until a platform admin approves them (admin dashboard button or `POST /admin/users/{id}/approve`); approvals can be withdrawn via **suspend** |
| **Catalog** | Boards → Class 1–12 → Subjects → Courses → Chapters → Lessons |
| **Learning** | Text/video/audio lessons, mark-complete, bookmarks, personal notes |
| **Practice** | MCQ · True/False · Multi-answer · Fill-in-the-blank, instant explanations |
| **Quizzes** | Chapter quizzes, timer, per-question grading + explanations |
| **Weak topics** | Rule-based detection (≥5 attempts, <50% accuracy) → revision + easy practice |
| **Today's Learning** | Personalized daily plan: continue → practice quiz → revision |
| **Gamification** | XP, daily streaks, 7 server-awarded badges, certificates (GS-XXXX IDs) |
| **Materials** | Uploads → **approval workflow** (pending → approved/needs_changes/rejected): students and *unapproved* teachers always land in review, approved teachers publish immediately + reporting |
| **Textbooks** | Official links only (ePathshala/NCERT, eBalbharati) — no re-hosting |
| **Doubts** | Ask → teacher replies → resolve, with notifications |
| **Dashboards** | Student, Teacher (monitor + doubts), Parent (weekly child summary), School, Admin |
| **Rural-first** | Data Saver mode, offline service worker, My Downloads, offline sync queue, <65 KB gzip JS |

## Docs

- [`docs/ANALYSIS.md`](docs/ANALYSIS.md) — research mining & decisions
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — data model & flows
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — runbook: Render + Vercel + Neon,
  secret-by-secret, first-admin bootstrap, smoke test

## Run locally

```bash
# Backend (from repo root)
cd gramshiksha
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt   # Windows
.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --port 8123

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:5174 (proxies /api → :8123)
```

**Demo accounts** (auto-seeded on first start):

| Role | Email | Password |
|---|---|---|
| Platform admin | admin@gramshiksha.in | Admin@1234 |
| School admin | school@gramshiksha.in | School@1234 |
| Teacher | teacher1@gramshiksha.in | Teach@1234 |
| Teacher | teacher2@gramshiksha.in | Teach@1234 |
| Student (Class 8, SSC, मराठी) | student1@gramshiksha.in | Learn@1234 |
| Student (Class 10, CBSE) | student2@gramshiksha.in | Learn@1234 |
| Parent (linked to student1) | parent1@gramshiksha.in | Parent@1234 |

## Tests

```bash
# Backend — 100 tests: API behaviour, password reset, authorization limits,
# every registered endpoint, migrations and the production boot gates.
# test_route_coverage_canary.py fails the build if a route is ever
# registered without a test calling it, or if the bare and /api mounts
# of a router drift apart.
.venv/Scripts/python -m pytest -q

# Frontend — 38 unit tests (request framing, session/offline storage,
# approval workflow API actions, growth helpers, explore availability
# filters and cross-page prefs)
cd frontend && npm test
npm run build                       # typecheck + production build

ruff check backend/app backend/tests   # lint (also a CI gate)
```

CI (`.github/workflows/ci.yml`) runs all of it on every push — lint, both
test suites, the frontend build — including a
**Postgres 16** job: the SQLite job alone never exercises the Postgres
dialect, and Postgres is what production actually runs on.

## Schema changes (Alembic)

The schema is owned by `backend/migrations/`. The server runs `alembic upgrade
head` during startup, so a deploy picks up new tables and columns without a
manual step. Databases created before Alembic existed (plain `create_all`) are
stamped at head first — they already match the models — instead of having
their tables replayed.

```bash
cd backend
.venv/Scripts/python -m alembic revision --autogenerate -m "describe the change"
.venv/Scripts/python -m alembic upgrade head
```

`backend/tests/test_migrations.py` fails when `models.py` and the migration
head drift apart — a model edit without a generated revision breaks the suite,
not the first production deploy.

## Deploy free (100% free-tier path)

1. **Database** — create a project at [neon.tech](https://console.neon.tech) or
   [supabase.com](https://supabase.com) (both free). Copy the Postgres URL and
   add `?sslmode=require`. Install the driver: `pip install "psycopg[binary]"` (already in `requirements.txt`).
2. **Backend** — deploy `backend/` to [Render](https://render.com) free tier (see `render.yaml`, health check: `/ready`):
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers` (see `backend/Dockerfile`)
   - Env: `DATABASE_URL`, `JWT_SECRET=<random 64 chars>`, `CORS_ORIGINS=["https://your-site.netlify.app"]`
     (must stay valid JSON), `CLOUDINARY_*` and `SMTP_*` (see below).
   - **The API refuses to start in production** (`app/main.py: check_production_safety`)
     while `JWT_SECRET` is the dev default or uploads would hit an ephemeral disk.
     Fix the reported vars rather than working around them.
   - The API answers on both `/...` and `/api/...`; the frontend uses `/api/...`.
3. **Frontend** — deploy `frontend/` to Netlify/Vercel/Cloudflare Pages:
   - Build: `npm run build`, publish `dist/`
   - Proxy: `public/_redirects` (Netlify) or `vercel.json` rewrites `/api/*` to the backend — replace the placeholder URL.
   - Env: `VITE_API_URL=https://your-backend.onrender.com` (or empty for same-origin).
## Textbooks — official links + verified deep PDFs

Textbook rows link to official portals only (never re-hosted — NCERT
explicitly prohibits redistribution). Each row may also carry a verified
`deep_url` (direct PDF) + `cover_url`, filled only by the crawler below —
never hand-written. Students open books via `GET /textbooks/{id}/open`,
which counts the click and 302s to the deep PDF when healthy, else the portal.

```bash
# Crawl the official eBalbharati library (polite, 1.5s between requests)
python backend/scripts/crawl_ebalbharati.py --mediums 301 302 303 304 \
    --output catalog.json
# Fill deep_url/cover_url on exact (board, grade, subject, lang) matches
python backend/scripts/crawl_ebalbharati.py --input catalog.json --apply --board auto
# Revert assignments if the matcher improves later
python backend/scripts/crawl_ebalbharati.py --input catalog.json --audit --board auto
```

Link health: `POST /admin/textbooks/recheck?limit=50` (platform admin)
HEAD-checks deep URLs; dead ones auto-fall-back in `/open`.
Status: eBalbharati mapped (707-entry crawl re-run 2026-10-03; 133 Textbook
rows carry cover_url + deep PDF across Maharashtra SSC/HSC in
Marathi/Hindi/English/Urdu — all HEAD-verified by the recheck pass, 0 dead).
CBSE/NCERT: use `backend/scripts/crawl_ncert.py`
the same way (crawl → `--apply`); it only stores URLs verified live as PDFs
on ncert.nic.in/epathshala.nic.in. Run it from inside India — both portals
time out from most foreign networks (verified Sep 2026).
4. **Uploads** — production writes to Cloudinary (`CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET`),
   otherwise `backend/uploads/` lives on an ephemeral disk and is wiped on every redeploy.
   Only if you mounted a real persistent disk at `backend/uploads`, set
   `ALLOW_EPHEMERAL_UPLOADS=true` to skip that check.
5. **Password reset** — codes are 6 random digits, stored **hashed** in the DB
   (works across restarts/workers) and emailed over plain SMTP: set `SMTP_HOST`,
   `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`.
   Without SMTP, `/auth/reset-request` answers `503` in production rather than
   silently swallowing the request. Local dev (SQLite) logs the code instead.
   `reset-confirm` verifies the code and allows a single use.
6. **Demo accounts** — `admin@gramshiksha.in / Admin@1234` and friends are seeded
   **only on local SQLite**. With a Postgres `DATABASE_URL` they are skipped
   unless you force `SEED_DEMO=true` (never do that on a real instance); course,
   chapter, lesson, quiz and textbook content always seeds.
7. **API reference** — `/docs` and `/openapi.json` are a map of the attack
   surface, so they're **hidden in production** (set `ENABLE_DOCS=true` to
   publish them deliberately, `false` to hide them locally too).
8. **Every response carries `X-Request-ID`**, echoed back in the body of an
   unexpected 500 (`{"detail": "Internal server error", "request_id": "…"}`).
   Quote that id when reporting a problem — it matches the log line and the
   traceback, which are never sent to the client.
9. **Teacher approval** — anyone can self-register as `teacher`, so the role
   alone grants nothing: new teachers are `pending` and every privileged route
   answers `403 Account pending approval` until a platform admin approves them
   (`POST /admin/users/{id}/approve`, or the button on the Admin dashboard).
   `POST /admin/users/{id}/suspend` withdraws an approval again (`403 Account
   suspended`); both refuse to target your own account, so the last admin
   cannot lock everybody out.

## Copyright & safety

- **License — proprietary, commercial rights reserved.** View, study and
  reference this code freely (resume/portfolio use is fine), but *any*
  money-making use — ads, paid tiers, selling or licensing the code —
  is reserved **exclusively to Pravesh Kumar**. See [LICENSE](LICENSE).
- Textbooks section links to **official sources only** (ePathshala, eBalbharati).
- Student uploads require teacher/admin approval before becoming public.
- Uploads restricted to PDF/images/audio, 10 MB max, random filenames.
- Every material carries a mandatory "source of content" field.
