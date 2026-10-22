# GramShiksha Study Studio

A native study workspace at `/studio`. A learner generates a study guide, notes
or quiz in **their own** NotebookLM / Gemini Notebook account, copies the result,
and imports it into GramShiksha. GramShiksha turns that text into a native pack:
overview, key points, flashcards, quiz questions and a revision checklist.

The learner never leaves GramShiksha to *study*. NotebookLM is only the
authoring tool they already chose to use with their own Google account.

## The rule that keeps this safe

> The user's Gmail session stays in the user's browser. GramShiksha only receives
> the text the user deliberately pastes.

We do **not**:

- ask for a Google password,
- store Google cookies or session tokens,
- run an invisible browser on the server as the user,
- call undocumented NotebookLM APIs,
- create accounts or accept Google's terms on the user's behalf.

Those shortcuts would put every learner's Google account at risk, break when
Google changes its login flow, and are not something a school platform should
do. The import design gives the learner the same result without holding their
credentials.

## What shipped

- **`/studio`** — signed-in, mobile-first page with an import form, an example,
  clipboard paste, a local library, and four study tabs.
- **Deterministic parser** (`frontend/src/studio.ts`) — turns plain text into:
  - overview,
  - up to 8 key points,
  - up to 12 flashcards,
  - up to 8 quiz questions,
  - up to 12 checklist items.
- **Study tools** — flip cards, mark cards known, reveal quiz answers, tick the
  revision checklist, reset progress.
- **Device-local library** — packs are saved in `localStorage`, scoped to the
  signed-in name and role, so they survive a reload and work offline.
- **Export** — print / Save as PDF, or download a self-contained HTML file.
- **File import** — upload a NotebookLM export as PDF, DOCX, HTML, Markdown or
  TXT (up to 10 MB). The backend extracts text in memory and never stores the
  upload; `/api/studio/extract` requires a signed-in GramShiksha account.
- **Google Drive import (opt-in)** — a learner can connect their own Google
  account with read-only Drive access, pick the Google Doc they exported from
  NotebookLM, and import its text. The token stays in the browser tab. The card
  is hidden until `VITE_GOOGLE_CLIENT_ID` is configured; see
  [GOOGLE-DRIVE.md](GOOGLE-DRIVE.md).
- **PWA install prompt** — when the browser says the app is installable, Studio
  shows a one-tap **Install app** card. Once installed, the learner can tap
  **Share → GramShiksha** from their own NotebookLM app; the shared title, text
  and link prefill the import form. This is a user-initiated handoff, not a
  background Google login.
- **Privacy badge** — the page states that packs are saved on the device and that
  the Google session is never connected.
- **Routing and SEO** — `/studio` is a private, `noindex` SPA route; it is not in
  the sitemap and is not statically generated.
- **Tests** — parser unit tests plus Playwright coverage on desktop, mobile and
  compact mobile: import, tabs, flip, reveal, checklist, reload persistence,
  HTML download, and the signed-out gate.

## How a learner uses it

1. Open `/studio` and sign in to GramShiksha.
2. In their own NotebookLM account, generate a study guide, notes or quiz.
3. Copy the text, or export the notebook as PDF/DOCX and upload it.
4. Paste/import it into `/studio`, optionally add a title and source URL.
5. Build the pack and study it in GramShiksha.
6. Keep it on the device, print it, or download the HTML copy.

If the owner configures a Google OAuth client ID, step 3 can also be
**Export to Google Docs → Connect Google Drive → pick the Doc** inside Studio.

On a phone, the copy/paste flow works in every browser. It does not depend on a
Chrome extension, a desktop-only connector, or a paid API. On Android, installing
GramShiksha as a PWA adds it to the system share sheet, so the learner can tap
**Share → GramShiksha** instead of copying and pasting manually.

## Why not fully automatic per-user NotebookLM?

| Route | Result | Verdict |
|---|---|---|
| User copies from their own NotebookLM and imports | Native pack, no credentials held | **Shipped** |
| Official Gemini Notebook Enterprise API | Fully automatic | Paid Google Cloud; conflicts with the free-tier rule |
| Server-side Gmail automation with stored cookies | Fully automatic | Rejected: credential custody, ToS and account-security risk |
| Browser extension running in the user's own session | More automatic | Possible later; must be installed by the user and still respects Google's terms |
| PWA share target | One-tap "Share to GramShiksha" on mobile | **Shipped for text and links** |
| Upload a PDF/DOCX/HTML file | Import an exported notebook directly | **Shipped** |
| Google Drive import | Pick an exported Google Doc | **Shipped, opt-in via OAuth client ID** |

The share target still runs in the learner's session and sends only the content
the learner chooses to share. It does not need Google credentials.

## Architecture as implemented

```
frontend /studio
        │
        ├── paste / clipboard / example
        ├── file upload ── POST /studio/extract ── PDF/DOCX/HTML/MD/TXT
        ├── Google Drive ── Google Identity Services (read-only, opt-in)
        ├── local deterministic parser  (no network, no API key)
        ├── native flashcards, quiz, checklist
        └── localStorage library
                ├── print / Save as PDF
                └── download self-contained HTML
```

The parser itself has no backend call, so it works on a low-end phone and while
offline. File extraction is the only network step, and the upload is parsed in
memory and discarded. The parser is deterministic: the same text produces the
same pack, which makes the feature testable and cheap to run.

### Storage

- Key: `gs_studio_packs_v1:<name>:<role>`.
- Limit: 20 packs per browser profile.
- The raw pasted text is **not** stored; only the generated pack is.
- Clearing browser data removes the packs. Downloading HTML is the durable copy.
- No pack is published to other users from this screen.

## Guardrails

- Free tier only. No paid model, domain or hosting is required.
- No student PII is sent anywhere; parsing happens in the browser.
- Imported text is escaped before it is placed in downloadable HTML.
- AI output is labelled "AI-assisted" and the page tells learners to check facts
  against the official textbook.
- No scraped copyrighted textbook content is republished.
- The page never presents generated notes as an official government textbook.
- Clipboard access is optional; the manual paste path always works.
- The pack is device-local, so a shared phone does not publish one learner's notes
  to another account.

## Files

| File | Purpose |
|---|---|
| `frontend/src/studio.ts` | Parser, pack type, safe HTML export |
| `frontend/src/pages/Studio.tsx` | `/studio` UI and local library |
| `frontend/src/googleDrive.ts` | Opt-in Google Drive listing/export helpers |
| `frontend/src/components/InstallPrompt.tsx` | PWA install suggestion |
| `backend/app/routers/studio.py` | In-memory PDF/DOCX/HTML/text extraction |
| `frontend/src/__tests__/studio.test.ts` | Parser and escaping tests |
| `frontend/src/__tests__/googleDrive.test.ts` | Drive request/token/Error tests |
| `frontend/e2e/studio.spec.ts` | Desktop/mobile import, share, install and export tests |
| `docs/GOOGLE-DRIVE.md` | OAuth client setup and consent-screen limits |
| `frontend/src/App.tsx` | Route, navigation and signed-out gate |
| `frontend/public/manifest.webmanifest` | PWA share-target registration |
| `frontend/seo-routes.json` | Private `noindex` SEO entry |
| `frontend/vercel.json` | SPA rewrite and noindex header |
| `frontend/src/styles.css` | Studio and print styles |

## Later, only with explicit approval

- Share-target support for PDF/file shares (text and links already work).
- Optional owner-only batch authoring for teacher-published packs.
- Google OAuth verification and a production consent screen for Drive import.
- Provider adapter for a free model, with the native parser as fallback.
- Backend persistence and cross-device sync, with per-user quotas and moderation.
- Official Gemini Notebook Enterprise API only if the no-spend rule changes.
