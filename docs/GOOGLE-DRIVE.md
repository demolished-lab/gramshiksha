# Google Drive import for Study Studio

Study Studio can open Google's own file picker and import **one Google Doc**
that the learner chooses. It uses Google Identity Services plus the Google
Picker API, and requests only the non-sensitive
`https://www.googleapis.com/auth/drive.file` scope. GramShiksha cannot list or
read any other Drive file.

The access token stays in memory for the current tab. GramShiksha never
receives a Google password, cookie, refresh token or client secret.

## Current production configuration

The Cloud project is already set up:

- Project ID: `gramshiksha-studio`
- Project number / Picker app ID: `592295986653`
- APIs enabled: **Google Drive API** and **Google Picker API**
- OAuth client: **Web application**, named `GramShiksha Study Studio`
- Authorized JavaScript origins:
  - `https://gramshiksha-academy.vercel.app`
  - `http://localhost:5174`
- OAuth consent screen: **External**, publishing status **In production**
- Data access: **`.../auth/drive.file`** — listed by Google as non-sensitive
- API key: restricted to **Google Picker API** and HTTP referrers
  - `https://gramshiksha-academy.vercel.app/*`
  - `https://docs.google.com/*` (the Picker iframe)

Because only `drive.file` is requested, the app does **not** need Google OAuth
verification or a paid security assessment. Users do not see the "unverified
app" warning for this scope.

## Build-time values

The Drive card is hidden unless all three public values are present when the
frontend is built:

```text
VITE_GOOGLE_CLIENT_ID=592295986653-j805khs8u4jcqsrijg6gcibai7r1as0i.apps.googleusercontent.com
VITE_GOOGLE_PICKER_KEY=AIza...
VITE_GOOGLE_APP_ID=592295986653
```

They live in `frontend/.env.production.local` on this machine. That file is
ignored by Git. The values are public (they ship in the browser bundle); the
OAuth **client secret is not used and must never be added**.

If the repository is built somewhere else, add the same three values to
**Vercel → Project → Settings → Environment Variables → Production**, or export
them before running `npm run build`:

```powershell
$env:VITE_GOOGLE_CLIENT_ID = '...apps.googleusercontent.com'
$env:VITE_GOOGLE_PICKER_KEY = 'AIza...'
$env:VITE_GOOGLE_APP_ID = '592295986653'
npm run build
```

The Vercel REST fallback uploads the already-built `dist/`, so the values must
be present during that local build. Changing them requires a new build and
deployment.

## What the learner sees

1. Open `/studio` and sign in to GramShiksha.
2. In their own NotebookLM, export the notebook to **Google Docs**.
3. Tap **Choose from Google Drive**.
4. Google asks for access to the file they pick. The Picker lists their Docs;
   GramShiksha receives access only to the selected document.
5. The text is imported into the Studio draft. Review it, then build the native
   study pack.
6. **Disconnect** clears the token from memory. It is never saved.

If the learner would rather not use Google sign-in, the existing
**Import a file** path accepts a DOCX downloaded from Google Docs, plus PDF,
HTML, Markdown and TXT. That path needs no Google authorization at all.

## Why not list Docs directly?

Listing a learner's Drive requires `drive.readonly`, which Google classifies as
restricted. A public app using it needs OAuth verification plus a security
assessment, and can be capped or blocked until that finishes. The Picker with
`drive.file` is the free, least-privilege route: the learner explicitly selects
one file, and only that file is shared with GramShiksha.

## Privacy wording

> If you choose Google Drive import, Google lets you pick one document.
> GramShiksha receives access only to that document and keeps the short-lived
> access token in your browser tab. We do not store the token on our servers, do
> not read files you do not select, and do not use Google user data for
> advertising.

## Verify

- With all three values set, `/studio` shows the Google Drive card.
- Without any of them, the card is absent and paste/file import still work.
- **Choose from Google Drive** opens the Google Picker (desktop and mobile).
- Picking a Google Doc imports its text and source link.
- **Disconnect** removes the token from React state.
- The browser console has no CSP errors for `apis.google.com` or
  `docs.google.com`.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Google Picker is not configured yet.` | Rebuild with `VITE_GOOGLE_PICKER_KEY` and `VITE_GOOGLE_APP_ID`. |
| `The API developer key is invalid` | Add `https://docs.google.com/*` to the API key's website restrictions and wait up to 5 minutes. |
| `Access blocked` / `origin_mismatch` | Add the exact site origin to the OAuth client's authorized JavaScript origins. |
| Picker opens but is empty | Confirm the learner has a Google Doc and that the Picker key is restricted to the Picker API. |
| `Google access expired` | Tap **Disconnect**, then choose the Doc again. |
| Picker does not load | Check CSP and an extension/ad-blocker; the loader needs `https://apis.google.com` and the frame needs `https://docs.google.com`. |

See `frontend/vercel.json` for the CSP and COOP settings. `same-origin-allow-popups`
is deliberate: the Google Identity Services consent popup needs its opener.
