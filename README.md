# GramShiksha — ग्रामशिक्षा

**A free, trilingual (English · हिंदी · मराठी) school e-learning portal for Class 1–12** —
Maharashtra SSC, Maharashtra HSC and CBSE — built for rural & semi-urban students with
slow internet, shared phones and limited data.

> Learn → Practice → Test → **Find Weakness** → Revise → Improve

## What's inside

| Area | Details |
|---|---|
| **Roles** | Student, Teacher, Parent, School Admin, Platform Admin (JWT auth) |
| **Catalog** | Boards → Class 1–12 → Subjects → Courses → Chapters → Lessons |
| **Learning** | Text/video/audio lessons, mark-complete, bookmarks, personal notes |
| **Practice** | MCQ · True/False · Multi-answer · Fill-in-the-blank, instant explanations |
| **Quizzes** | Chapter quizzes, timer, per-question grading + explanations |
| **Weak topics** | Rule-based detection (≥5 attempts, <50% accuracy) → revision + easy practice |
| **Today's Learning** | Personalized daily plan: continue → practice quiz → revision |
| **Gamification** | XP, daily streaks, 7 server-awarded badges, certificates (GS-XXXX IDs) |
| **Materials** | Teacher uploads (auto-approved) + student uploads → **approval workflow** (pending → approved/needs_changes/rejected) + reporting |
| **Textbooks** | Official links only (ePathshala/NCERT, eBalbharati) — no re-hosting |
| **Doubts** | Ask → teacher replies → resolve, with notifications |
| **Dashboards** | Student, Teacher (monitor + doubts), Parent (weekly child summary), School, Admin |
| **Rural-first** | Data Saver mode, offline service worker, My Downloads, offline sync queue, <65 KB gzip JS |

## Docs

- [`docs/ANALYSIS.md`](docs/ANALYSIS.md) — research mining & decisions
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — data model & flows

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
.venv/Scripts/python -m pytest -q        # 13 API tests, all green
cd frontend && npm run build             # typecheck + production build
```

## Deploy free (100% free-tier path)

1. **Database** — create a project at [neon.tech](https://console.neon.tech) or
   [supabase.com](https://supabase.com) (both free). Copy the Postgres URL and
   add `?ssl=require`. Install the driver: `pip install "psycopg[binary]"`.
2. **Backend** — deploy `backend/` to [Render](https://render.com) free tier:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Env: `DATABASE_URL`, `JWT_SECRET=<random 64 chars>`,
     `CORS_ORIGINS=["https://your-site.netlify.app"]`
3. **Frontend** — deploy `frontend/` to Netlify/Vercel/Cloudflare Pages:
   - Build: `npm run build`, publish `dist/`
   - Proxy: Netlify `_redirects` → `/api/* https://your-backend.onrender.com/api/:splat 200`
   - Vercel: `vercel.json` rewrites with the same pattern.
4. **Uploads** — the free-tier volume works for pilots; for durability move
   `/uploads` to Supabase Storage or Cloudflare R2 (both free tiers).

## Copyright & safety

- Textbooks section links to **official sources only** (ePathshala, eBalbharati).
- Student uploads require teacher/admin approval before becoming public.
- Uploads restricted to PDF/images/audio, 10 MB max, random filenames.
- Every material carries a mandatory "source of content" field.
