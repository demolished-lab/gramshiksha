# GramShiksha — Security Audit

**Date:** 20 October 2026
**Target:** `https://gramshiksha-academy.vercel.app` (SPA) + `https://gramshiksha-backend.onrender.com` (API)
**Method:** live black-box probing of production **and** source review of the deployed commit.
**Scope:** authentication, authorization/tenancy, uploads, PDF proxy, rate limiting, client
storage/PWA, headers, input handling, info disclosure.

> Nothing was defaced, deleted or created. The only state changes were one login to the
> existing test student, rejected registration attempts, and ~300 deliberately failed
> logins used to measure the rate limiter. No load/DoS testing was performed.

---

## Summary

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 4 |
| Medium | 10 |
| Low | 15 |

**The core is solid** — JWT handling, SQL injection, path traversal, IDOR on student data,
admin/teacher authorization, XSS sinks and secret handling all held up under testing.
The four High findings are all *policy/architecture* gaps rather than broken crypto:
an upload-moderation bypass, a self-declared tenant boundary, an unreliable rate limiter,
and a service worker that caches private data in a shared cache.

---

## High

### H1 — Any self-registered `parent` can publish material publicly without moderation

**Where:** `backend/app/routers/materials.py:54` + `backend/app/routers/auth.py:102`

```python
# materials.py:54 — auto-approve anyone who is not a student and is "active"
status = "pending" if user.role == "student" or user.role_status != "active" else "approved"
```

```python
# auth.py:102 — parent accounts are created active, with no email verification
role_status="pending" if payload.role == "teacher" else "active",
```

**Exploit (≈30 seconds, no email needed):**

1. `POST /auth/register {"role":"parent", ...}` → active account + token immediately.
2. `POST /materials` (multipart, any allowed file, `visibility=public`) → stored with
   `status="approved"`.
3. It appears in the anonymous `GET /materials` list and is downloadable by any signed-in
   user. No teacher or admin ever sees it in the moderation queue.

**Impact:** the entire moderation model (students pending, teachers approved) is bypassed.
Arbitrary PDF/image/audio/pptx content is hosted and branded as GramShiksha — misinformation,
phishing documents, malware, or Cloudinary quota abuse (10 MB × 30/min/IP). There are
currently **zero** approved public materials, so this is a pre-launch hole, not a live incident.

**Fix:**

```python
status = "approved" if user.role in ("teacher", "platform_admin") and user.role_status == "active" else "pending"
```

and require an approved teacher/admin before honouring `visibility="public"`.

---

### H2 — Users can rewrite their own `school_id`, breaking tenant isolation

**Where:** `backend/app/routers/auth.py:190-197`, relied on by
`backend/app/authorization.py:18-21` and `backend/app/routers/materials.py:78-80`

```python
# PATCH /auth/me — no role check, no approval
if school_name:
    school = session.exec(select(School).where(School.name == school_name.strip())).first()
    ...
    user.school_id = school.id
```

```python
# authorization.py — the whole school-admin boundary is user.school_id
return list(session.exec(query.where(User.school_id == user.school_id)...))
```

**Exploit:**

- Any account: `PATCH /auth/me {"school_name":"<target school>"}` → `GET /materials`
  now returns that school's `visibility="school"` files, and downloads work.
- A **school_admin** who moves schools immediately inherits that school's
  `visible_students` → `/admin/users` (student emails), `/admin/reports`, teacher
  overviews, and draft lessons.
- `POST /auth/register {"school_name":"<target>"}` does the same at signup.

School names are not secret (seeded, printed on dashboards, chosen by users at signup).

**Impact:** horizontal privilege escalation across schools. Student PII of another school
becomes readable to a school admin; school-private material becomes readable by anyone.

**Fix:** remove `school_name` from self-service profile updates and registration (or apply it
only for `platform_admin`, with approval). Make school membership an operator/admin action.

---

### H3 — Rate limiting is per-process and not per-user: brute force works, and one client can lock everyone out

**Where:** `backend/app/ratelimit.py:17,25-33`; `backend/Dockerfile:29`

```python
HITS: dict[tuple[str, str], list[float]] = {}      # in-process memory
ip = request.client.host if request.client else "unknown"
```

The Dockerfile runs `uvicorn --proxy-headers` **without** `--forwarded-allow-ips`, so
`request.client.host` is only the real client when the proxy connects from `127.0.0.1`.
The dict is also per process/instance.

**Live evidence** (single client, single public IP, `/auth/token`):

- 33 sequential failed logins → **0 × 429**.
- 100 sequential failed logins → `401×37`, then a *scattered* mix: `429×54`, `401×46`,
  with 401s appearing between 429 runs (`429,429,401,429…`). A single bucket can only produce
  one contiguous block of 429s, so requests were divided across ≥2 independent buckets.
- 429 responses are the app's own JSON, so this is not Cloudflare doing the work.
- No `Retry-After` header is sent.

**Impact:**

- **No per-account throttle.** The only limit is per bucket, and buckets are shared. An
  attacker can keep ~30–60 password guesses/minute/IP going indefinitely; with 7-day tokens
  and no lockout/revocation, credential stuffing is practical.
- **Login denial of service.** Because the bucket is shared, 30 requests trip it for
  *everyone* on that bucket for 60 s. I locked myself (and anyone else) out repeatedly with
  ~30 rps of junk logins. An attacker can sustain that with a tiny request budget.

**Fix:** key by a verified client IP (configure `--forwarded-allow-ips` to Render's proxy
range, or read the rightmost XFF hop), add a **per-account** counter with a short lockout and
`Retry-After`, and move the limiter to a shared store (Upstash Redis free tier) or accept
per-instance limits explicitly. At minimum, return `Retry-After: 60` on 429.

---

### H4 — Service worker caches authenticated API responses in a shared, URL-keyed cache

**Where:** `frontend/public/sw.js:29-37,46-54`; `frontend/src/auth.ts:107-111`;
`frontend/src/api.ts:15-19`

```js
if (res.ok && !type.includes('pdf')) { caches.open(CACHE).then(c => c.put(request, res.clone())); }
...
if (url.pathname.startsWith('/api/')) {
  e.respondWith(fetch(e.request).then(res => putIfOk(e.request, res))
    .catch(() => caches.match(e.request).then(hit => hit || OFFLINE)));
}
```

Only `/api/auth/*` is excluded. `caches.match()` keys on the URL and ignores the
`Authorization` header (the API sets `Vary: Accept-Encoding` only).

**Exploit (shared school/family phone — the app's stated target):**

1. Teacher/parent A signs in, browses `#/teacher`, `/progress`, notifications, then closes
   the tab without pressing Logout (or their token expires — the 401 path clears
   `localStorage` but **not** Cache Storage).
2. Student B signs in on the same device. On a dropped connection (or with DevTools offline),
   the SW serves A's cached `/api/teacher/students`, `/api/progress/*`, `/api/notifications`.
3. B opens `#/teacher` — `App.tsx` renders the teacher dashboard for any signed-in user — and
   reads A's roster offline.

**Impact:** cross-account disclosure of student names, progress, doubts and notifications on
shared devices; also private non-PDF materials (`/api/materials/{id}/download`) are cached.
A redirected textbook URL that ends in HTML is cached under the app's own origin — a latent
same-origin content-injection vector.

**Fix:** in `sw.js`, do not intercept requests that carry `Authorization` (or restrict
caching to an explicit allowlist of anonymous catalog URLs), skip `res.redirected` and
`no-store/private`, and clear the API cache in `saveSession()` and in the 401 branch —
`await`ing it before navigating.

---

## Medium

### M1 — Any teacher can delete any material on the platform

`backend/app/routers/materials.py:239`:

```python
if m.uploader_id != user.id and not has_role(user, "teacher", "school_admin", "platform_admin"):
    raise HTTPException(403, "Not allowed")
```

No school scoping, unlike `_moderation_clause` (`materials.py:86-94`) which explicitly keeps
moderation inside a school. A teacher can walk sequential IDs and `DELETE /materials/{id}`
across every school; files are removed from Cloudinary/disk via `delete_ref`. 404 only for
non-existent rows, so the catalog can be enumerated and wiped.
**Fix:** scope to `platform_admin` or same-school uploader, and rate-limit the route.

### M2 — Attempting an unpublished lesson returns the answer key and completes it

`backend/app/routers/lessons.py:227-269`: `submit_attempt` never checks `lesson.published`
(and never checks the course), unlike `learn.get_lesson` (`learn.py:43`) and
`learn.submit_quiz` (`learn.py:161`). `POST /lessons/{id}/attempt` returns
`correct_answer` + `explanation` for every question and sets `Progress.completed = True`.
**Fix:** reject `not lesson.published` (and unpublished course) with 404.

### M3 — `/search` ignores material visibility and lesson publication

`backend/app/routers/dashboards.py:435-445`: the material query is
`select(Material).where(Material.status == "approved")` — no `_visible_query` — so
`private`/`school` titles, types and description matches from other schools are returned.
The question query has no `Lesson.published` join, exposing draft prompts/ids.
**Fix:** reuse `materials._visible_query(user)` and the published-lesson join used by
`learn.practice_questions`.

### M4 — Unlimited quiz attempts farm XP and inflate grades

`backend/app/routers/learn.py:185-190` + `backend/app/gamification.py:96-102`: every submit
awards `quiz_attempt` (+5) and a perfect score again (+20), with no attempt cap and no rate
limit. The first response includes the full answer key, so 25 XP/call is trivial; averages on
teacher/parent dashboards count every retake.
**Fix:** award once per `(user, quiz)` (or per day), cap attempts, and average best/first only.

### M5 — PDF proxy buffers up to 60 MB per anonymous request

`backend/app/routers/catalog.py:383,408-415,476`: `PDF_MAX_BYTES = 60 MB`, chunks are
collected in a list and `b"".join`-ed (≈2× peak), with no cache, on an anonymous
`GET /textbooks/{id}/open` limited only by 30/min/IP. ~4 concurrent 60 MB opens can exhaust a
512 MB instance; every request re-downloads from the government portal.
**Fix:** `StreamingResponse` with a running byte cap, lower the cap (~20 MB), add a global
concurrency semaphore (e.g. 3), and cache by `(textbook_id, chapter)` for a short TTL.

### M6 — Blocking 30–90 s outbound calls on public endpoints exhaust the threadpool

`library.py:125-131,230-231` (`POST /library/locate` is anonymous, 30 s timeouts,
`SCAN_BUDGET_S` checked only *between* mediums), `ncert.py:194-213` (HEAD, HEAD retry, ranged
GET), `catalog.py:365-377`. These are sync `def` endpoints on the ~40-thread AnyIO pool:
~40 concurrent calls pin it for 90 s and every other API request queues.
**Fix:** async handlers + `AsyncClient`, 5–10 s timeouts, deadline checked inside each fetch,
global semaphore, and a shared secret/cron gate for `scan-requests`.

### M7 — Account enumeration

- `POST /auth/register` returns `409 "Email already registered"` for existing addresses
  and `201` otherwise (**confirmed live**). No email verification is required, so an attacker
  can also squat a victim's address.
- `POST /parent/invite` returns `404` vs `200` to distinguish existing parents
  (`dashboards.py:171-174`), with no rate limit.
**Fix:** uniform response + email delivery for invites; for registration, either accept and
email a "you already have an account" message, or accept the enumeration trade-off explicitly.

### M8 — Authenticated responses are cacheable (`Cache-Control: public`, no `no-store`)

**Confirmed live:** every `/api/*` response through Vercel carries
`Cache-Control: public, max-age=0, must-revalidate`, and the backend adds nothing to
`/auth/me`, `/progress/me`, `/notifications`. Only `Vary: Accept-Encoding` is present.
Vercel itself currently reports `MISS`/`DYNAMIC`, so the edge is not caching, but browsers,
corporate proxies and the service worker may store PII.
**Fix:** middleware setting `Cache-Control: no-store` (plus `Pragma: no-cache`) on
authenticated routes; keep explicit public caching for catalog endpoints only.

### M9 — CSP cannot contain an XSS, and the JWT sits in `localStorage` next to planned ads

`frontend/vercel.json:39,56`: `script-src 'self' 'unsafe-inline' … https://*.google.com`,
`img-src … https:`, `connect-src … https://*.google.com`, `frame-src … https://*.google.com`.
`'unsafe-inline'` neuters script CSP; `*.google.com` and `img-src https:` give ready
exfiltration channels. The session token is in `localStorage` (`auth.ts:15,29-30`) with a
7-day, non-revocable lifetime, and `AdSlot` injects a Google script on a page that can be
rendered while signed in.
**Fix:** drop `'unsafe-inline'` (nonce + `'strict-dynamic'` for the ad loader if required),
replace `*.google.com` with the exact ad hosts, narrow `img-src`, and keep ads off
authenticated routes. Longer term, move the session to an `HttpOnly` cookie.

### M10 — Suspension is not enforced everywhere

`get_current_user` (`security.py:31-50`) and `require_any` (`security.py:138-149`)
deliberately ignore `role_status`, and several routes compare `user.role` inline instead of
using `has_role()`:

- `social.py:44-53,96-105` — a suspended school_admin still lists the school's doubts and can
  resolve any of them; a suspended platform_admin can resolve globally.
- `materials.py` upload via `require_any` — suspended accounts can still upload.
- `lessons.py:39-45` — suspended/pending admins can read draft lessons and question banks.
- `library.py:515-517` — suspended school_admin can delete reading picks, cross-school.

**Fix:** use `has_role(...)` in the inline checks and add a status check to `require_any`
(suspension should differ from "pending teacher").

---

## Low

| # | Finding | Where |
|---|---|---|
| L1 | Client `X-Request-ID` is echoed unbounded (200 chars accepted live) → log forging/header bloat | `main.py:105,115` |
| L2 | No HSTS on the API host (frontend has it); direct API users are unprotected | Render response headers |
| L3 | Preflight for the canonical origin returns **400 Disallowed CORS origin** (env list doesn't match the deployed alias). Fails closed; breaks direct-API mode | `config.py:17`, `render.yaml` |
| L4 | Tech/version disclosure: `/health` returns `{app, version:0.2.0}`; `x-render-origin-server: uvicorn` | `main.py:262-263` |
| L5 | 429 responses omit `Retry-After` | `ratelimit.py:31` |
| L6 | Client-supplied `minutes` (≤120) inflates study time shown to parents/teachers | `learn.py:67,229`, `lessons.py:279` |
| L7 | Read-then-write idempotency without unique constraints → races double XP/certs/badges; course XP re-awarded on each new lesson at 100% | `learn.py:73-84`, `gamification.py:81-87,118-120` |
| L8 | Referral leaderboard gameable (`ref=GS…` at signup); `gs_ref` persists across accounts on shared devices | `growth.py:105-122`, `auth.ts`/`growth.ts:56-63` |
| L9 | Unbounded text: `/school/announce` writes unlimited title/body to every student; `profile_pic` unbounded; library `board/lang/stream` unbounded | `dashboards.py:234-243`, `library.py:216-221` |
| L10 | Public reading list leaks teacher email local-parts when `name` is empty | `library.py:431,436,502` |
| L11 | Anonymous `clicks` counter increments before resolution → analytics poisoning | `catalog.py:462-464` |
| L12 | Vercel `"source": "/(.*)"` headers also hit `/api/*`, contradicting the documented invariant (currently harmless, duplicates backend headers) | `frontend/vercel.json:10` |
| L13 | SW `activate` deletes **all** other caches, including saved offline downloads (data loss, not a breach) | `sw.js:23-27` |
| L14 | Upload validation is extension-only (no magic-byte check). Served `attachment` + `nosniff`, so not XSS — but arbitrary content is hosted | `storage.py:29-38`, `materials.py:214` |
| L15 | No email verification: addresses can be squatted; "verified" is implied by the UI | `auth.py:102` |

**Known functional blocker (not a vuln):** password reset returns 503 in production until
SMTP is configured (`auth.py:214`); reset endpoints are unusable today.

---

## Verified secure (tested, so don't re-audit)

- **JWT:** forged HS256 with the dev default secret → 401; random secret → 401; `alg:none`
  rejected by `jose`; garbage token → 401. Production secret is not the default. Role claims
  are ignored — the user row is loaded by email, so a forged `role` claim cannot elevate.
- **Docs exposure:** `/docs`, `/openapi.json`, `/redoc` → 404. No stack traces or debug pages.
- **Sensitive paths:** `/.env`, `/.git/config`, `/server.log`, `/app/main.py`, `/uploads/*` →
  404 on both hosts. Uploads are never statically mounted.
- **SQL injection:** all queries bound; live `' OR 1=1--` and `'; DROP TABLE` payloads blocked
  (Cloudflare WAF 403) and, where they reach the app, return empty/422 — never 500 or
  all rows.
- **IDOR:** all 18 anonymous-gated routes → 401; all 8 student→admin/teacher routes → 403;
  admin approve/suspend, material review → 403. `/auth/me` returns no hash/token. Doubt #1
  belonged to the test student, so the 200 on resolve was legitimate.
- **Self-registration privileges:** `role=platform_admin` → 422; teachers start `pending`.
- **XSS:** SPA has zero `dangerouslySetInnerHTML`/`innerHTML`/`eval`; `feed.xml` escapes every
  interpolated value; no Host-header poisoning (`Host: evil.example` → 403).
- **Headers:** `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`,
  `Permissions-Policy`, COOP, HSTS + `frame-ancestors 'none'` on the SPA; PDF proxy adds
  `Accept-Ranges: none` and validates `%PDF` magic + content-type.
- **No open redirect / SSRF reachable today:** proxy and redirect targets come only from the
  DB (seeded/crawler-written, digits-only IDs); `chapter` is a bounded int.
- **Bundle:** 222 KB, contains no `JWT_SECRET`, `DATABASE_URL`, `CLOUDINARY`, backend host or
  dev secret. `vercel.json` is BOM-free; the only rewrite is `/api/:path*` → Render.
- **CORS:** evil origin preflight → 400, no `Access-Control-Allow-Origin`; credentialed
  wildcard not present.

---

## Suggested remediation order

**Batch 1 — small, high-value (≈half a day incl. tests)**
H1 (one line), H2 (drop `school_name` from self-service), M10 (`has_role` everywhere),
M1 (scope delete), M2 (published check), M7 (uniform register/invite responses),
M8 (`no-store` middleware), L1, L5, L3, L2.

**Batch 2 — client/PWA (≈half a day)**
H4 (SW allowlist + clear on login/401), M3 (`_visible_query` in search), M4 (attempt cap +
one-time XP), L7 (unique constraints), L13.

**Batch 3 — availability (≈1 day)**
H3 (trusted proxy config + per-account lockout + shared store or `Retry-After`),
M5 (streaming PDF relay + semaphore), M6 (async + timeouts), L9.

**Batch 4 — before ads ship**
M9 (CSP hardening, ads off authenticated pages, shorten/revoke tokens).

---

## Limits of this audit

- No load, flood or destructive fuzzing was run; H3 was measured with ~300 cheap auth
  requests, M5/M6 are reasoned from code + limits, not weaponized.
- Authenticated testing used the existing **student** account only. Teacher/admin paths were
  reviewed in source; no teacher/admin session was created or modified.
- Findings marked “source-verified” (H1, H2, M1–M4, M10) were not exploited end-to-end
  because doing so would create or delete production content.
- Dependency CVEs (`npm audit` / `pip-audit`) and Cloudflare/WAF rule review were out of scope.

---

## Remediation status (20 October 2026)

All code fixes below were applied after the report, on the same day. Backend: **182 tests
pass**, `ruff` clean. Frontend: **74 tests pass**, production build clean. The two external
blockers are called out explicitly.

| ID | Status | What changed |
|---|---|---|
| H1 | **Fixed** | `status` is now `approved` only for `has_role(teacher/school_admin/platform_admin)`; a parent or pending teacher is `pending`. Regression test: a parent upload never appears in `GET /materials`. |
| H2 | **Fixed** | `school_name` removed from `ProfileUpdate` (and its handler). Membership is set once at registration; a PATCH carrying the field is ignored. |
| H3 | **Fixed (single instance)** | Login now also locks **per account** (10 failures / 15 min, `Retry-After`), independent of the IP bucket; ALL 429s carry `Retry-After`; the limiter keys on the **last** `X-Forwarded-For` hop (the address Render's edge appended), so users no longer share the proxy's bucket and client-supplied leading hops are ignored. A multi-instance deployment would still need Redis, which the free tier does not have. |
| H4 | **Fixed** | Authenticated API responses go to a **per-account** SW cache (`gramshiksha-api:<opaque-id>`), never the shared shell cache; the id is pushed on login/boot, logout deletes every private cache, and 401/login also call `clearCachedApi()`. Offline lessons still work. |
| M1 | **Fixed** | Deletes are owner, or staff **inside the same school**; platform admin anywhere. Regression test added. |
| M2 | **Fixed** | `submit_attempt` and the lesson reader return 404 for an unpublished lesson **or** an unpublished course. |
| M3 | **Fixed** | `/search` uses the same `_visible_query()` as the materials library and searches only questions on published lessons. |
| M4 | **Fixed** | Quiz XP is paid only on the **first** attempt (retakes still record and update topic stats); course-completion XP is paid only when the certificate is actually created. Retake averages remain a deliberate learning feature. |
| M5 | **Mitigated** | Cap 60 MB -> 20 MB, `bytearray` (no list+join copy), max **3** concurrent PDF fetches (4th gets `503 Retry-After: 30`). Still buffered by design: the viewer has no range support. |
| M6 | **Mitigated** | Portal timeouts 30-45 s -> 8-20 s, catalogue link check 15 -> 8 s, live scan budget 45 -> 20 s, max **2** concurrent crawls (extra `locate` degrades to the queue), optional `SCAN_TOKEN` gate on `/library/scan-requests`. |
| M7 | **Partial** | Parent invites now return the **same 200** and a valid token whether or not the address has an account. Registration still answers 409 for an existing email: a non-oracle signup needs email verification (see L15). |
| M8 | **Fixed** | `/auth/*` responses get `Cache-Control: no-store`; other authenticated responses get `private, max-age=0, must-revalidate` + `Vary: Authorization`, so no proxy may store them while the user's own SW still enables offline reading. |
| M9 | **Fixed** | `script-src` no longer allows `'unsafe-inline'` and `https://*.google.com` was dropped from `script-src` (AdSense hosts are still allow-listed). The build has no inline scripts; JSON-LD is a non-executable data block. Documented caveat: if AdSense is ever enabled it may inject inline scripts and need a fresh CSP review. |
| M10 | **Fixed** | Inline `role ==` checks moved to `has_role()` in lessons, social and library; suspended accounts are now refused by `require_any` (uploads), so suspension is genuinely read-only. |
| L1 | **Fixed** | A client `X-Request-ID` is accepted only if it matches `[A-Za-z0-9._-]{1,64}`; otherwise a fresh id is generated. Test added. |
| L2 | **Fixed** | HSTS is emitted by the API in production (`max-age=63072000; includeSubDomains`). |
| L3 | **Fixed** | CORS origins are the env list **plus** `settings.site_url`, so a stale Render env can no longer break the canonical origin; `allow_credentials=False` (bearer tokens only). |
| L4 | **Fixed** | `/health` and `/api/health` no longer expose the app version. |
| L5 | **Fixed** | Every rate-limit 429 carries `Retry-After` (window in seconds). |
| L6 | **Fixed** | Client `minutes` is clamped: 30 per lesson completion, 15 per practice answer. |
| L7 | **Partial** | XP/certificate/badge awards are now idempotent in code (first attempt, first certificate). No DB unique constraints were added: production is a live Neon DB, the migration would need a dedupe + batch rebuild, and the practical farming paths are closed. |
| L8 | **Fixed** | The captured `?ref=` code is cleared after a successful registration (`clearReferral()`), so one invite cannot credit every later signup on a shared device. Leaderboard remains cosmetic by design. |
| L9 | **Fixed** | Length caps on `/school/announce` (120/2000), `profile_pic` (500), registration fields, and library `board/lang/stream`. |
| L10 | **Fixed** | Public reading picks show `"Teacher"` when a name is empty; email local-parts are never exposed. |
| L11 | **Accepted** | Anonymous click counts are analytics only and already rate-limited to 30/min/IP. Debouncing would need per-IP state for no security gain. |
| L12 | **Fixed** | The Vercel header rule is now `/((?!api/).*)`, so `/api/*` keeps the backend's own framing/cache headers. Deploy-config test updated. |
| L13 | **Fixed** | SW `activate` preserves `gramshiksha-offline-materials*` (saved downloads) and only drops the shell/per-account caches. |
| L14 | **Fixed** | `save_upload` checks magic bytes for PDF/PNG/JPEG/WebP/MP3/M4A/PPTX; a renamed HTML file is rejected with 422. Test added. |
| L15 | **Blocked** | Email verification needs SMTP + a verification-token flow. SMTP is still unconfigured in production (password reset correctly returns 503). This is the one finding that cannot be closed from code alone; see `docs/GROWTH.md`. |

### Verification

- `ruff check backend/app backend/tests` -> clean.
- `pytest backend/tests` -> **182 passed** (10 new hardening tests in
  `backend/tests/test_security_hardening.py`).
- `npm test -- --run` -> **74 passed**; `npm run build` -> clean.
- Live re-probe after deploy: see the deploy log in the session summary (CORS preflight,
  cache headers, CSP, per-account cache, rate-limit `Retry-After`).

### Residual risks (deliberate)

1. **Multi-instance rate limiting** - H3's per-account lockout lives in process memory. Render
   may run more than one instance briefly during a deploy; a shared Redis/KV would be the
   complete fix but is not on the free tier.
2. **Email verification** - L15 remains open until SMTP is configured.
3. **AdSense CSP** - M9 removed `'unsafe-inline'`. Before enabling ads, verify the ad unit in
   a real browser; re-add only the specific hosts/nonce AdSense requires.
4. **PDF buffering** - M5 is capped, not streamed. A 20 MB book still occupies 20 MB of RAM
   for the duration of the request (3 at a time). A true streaming relay is a future change.

