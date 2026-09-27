# GramShiksha — Research Analysis & Mining Report

Date: 2026-09-27 · Sources: official portals, open-source LMS platforms, low-bandwidth design guides, free-tier vendor docs, community discussions.

## 1. What we researched

| Area | Key sources |
|---|---|
| Official textbooks | ePathshala (NCERT joint initiative), ncert.nic.in eBooks, **eBalbharati `books.ebalbharati.in`** (free official Maharashtra PDFs), DIKSHA QR-linked textbook PDFs |
| Proven platforms | **DIKSHA/Sunbird-Ed** (MIT-licensed Digital Public Good; powers India's national platform), **Kolibri** (Learning Equality; offline-first for low-resource contexts), Khan Academy (mastery learning + gamification case studies) |
| Low-bandwidth design | Digital Frontiers Institute, Android offline-first architecture guide, OpenReplay low-bandwidth design, eLearning Industry adaptive-streaming guidance |
| Free-tier infra | 2026 comparisons of Supabase vs Neon vs Firebase; Render/Railway/Fly free tiers; Netlify/Vercel/Cloudflare Pages |
| Engagement | Khan Academy gamification analyses (XP/streaks/mastery → retention) |

## 2. Findings that shape our architecture

**F1 — Textbooks: link, don't host.** NCERT (ePathshala/ncert.nic.in) and Balbharati
(`books.ebalbharati.in`) publish free official PDFs. Copyright rule: store *metadata +
official source links* in our DB, never redistribute files. → `textbooks` table with
`source_url` pointing at the official portal.

**F2 — Proven data model.** Sunbird/Kolibri converge on the same hierarchy:
Board → Grade/Class → Subject → Course → Chapter → Lesson/Unit → Practice/Quiz.
We adopt this exactly, plus a `contentnode`-style flat search across it.

**F3 — Offline-first is a must, not a feature.** Kolibri's whole thesis: offline is the
primary mode in low-resource contexts. For a web portal: service worker (app shell
cache-first, API network-first), localStorage lesson cache, explicit "My Downloads"
section, progress sync queue when back online.

**F4 — Data Saver must be a real mode.** Converging advice: text-first lessons, low-res
media by default, no autoplay, no heavy animations, lazy images, paginated lists,
"estimated data usage" hints. We implement a Data Saver toggle persisted per device.

**F5 — Gamification works when it's mastery-shaped.** Khan Academy pattern: XP + streaks
+ badges tied to *learning milestones* (first lesson, first quiz, 7-day streak, perfect
score, course completion) — motivating without being childish. Server-awarded.

**F6 — Weak-topic detection is just math.** Per-topic accuracy from practice/quiz
attempts; accuracy < 50% with ≥ 5 attempts ⇒ weak ⇒ recommend revision + easy practice.
No ML needed at this scale; rule-based, explainable, cheap.

**F7 — Free-tier stack (2026):** Supabase/Neon (Postgres free tiers) for DB; Render
free tier or Railway trial for FastAPI; Netlify/Vercel/Cloudflare Pages for the SPA.
JWT auth we own (no service lock-in). SQLite locally, Postgres in prod — same code.

**F8 — Shared-device reality.** Multiple siblings per phone: profiles are per-account,
logout is prominent, nothing user-specific persisted outside the authenticated session
except device-level prefs (lang, data saver).

**F9 — Marathi is a first-class need** (Maharashtra SSC/HSC), not an afterthought.
All UI strings + seed content carry en/hi/mr variants.

**F10 — Moderation workflow for student uploads** (safety + copyright):
`pending → approved | needs_changes | rejected` with reviewer + reason; only approved
material appears publicly. Reporting flow with reasons on any material.

## 3. Decisions (mined → analyzed → chosen)

| Decision | Choice | Why (from findings) |
|---|---|---|
| Content hierarchy | Board→Class→Subject→Course→Chapter→Lesson | F2 |
| Textbooks | Metadata + official links only | F1, copyright |
| Offline | SW + cache + downloads + sync queue | F3 |
| Data saver | Text-first mode, media gating, lazy load | F4 |
| Weak topics | Rule-based accuracy per topic | F6 |
| Gamification | Server-side XP/streaks/badges on milestones | F5 |
| DB | SQLModel; SQLite dev / Neon Supabase Postgres prod | F7 |
| Auth | JWT, roles: student/teacher/parent/school_admin/platform_admin | spec §43 |
| Languages | en/hi/mr everywhere | spec §37, F9 |
| Uploads | PDF/images/audio ≤ 10 MB, whitelist types, approval workflow | spec §46+§19 |

## 4. Risks & mitigations

- **Postgres free tier sleep** (Render/Neon): keep pings light; DB is lazy-loaded.
- **Upload abuse**: type+size validation server-side; private until approved.
- **Copyright**: uploads carry `source_of_content` field; policy text on upload form;
  links to official books only.
- **Low-end phones**: no SPA framework beyond React, code-split by route later,
  gzip ~50 KB initial JS budget maintained.
