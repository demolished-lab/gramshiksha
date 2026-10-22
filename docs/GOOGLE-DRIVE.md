# Google Drive import for Study Studio

The code is shipped. The Drive card stays hidden until a **public OAuth client
ID** is present at build time. This is the only external step; it needs a signed-in
Google Cloud Console, and the browser session here is currently signed out.

No client secret is needed. The browser gets a short-lived access token from
Google Identity Services, reads only the Google Doc the learner picks, and keeps
the token in memory for that tab. GramShiksha does not store refresh tokens,
passwords or Google cookies.

## One-time Google Cloud setup

1. Open <https://console.cloud.google.com/> with the owner account
   (`praveshedu29@gmail.com`).
2. Create or select a project. Name it `GramShiksha`.
3. Go to **APIs & Services → Library**, search **Google Drive API**, and click
   **Enable**. (The Drive API, not the Drive UI.)
4. Go to **APIs & Services → OAuth consent screen**:
   - User type: **External**
   - App name: `GramShiksha Academy`
   - Support email and developer email: the owner account
   - Add scope: `https://www.googleapis.com/auth/drive.readonly`
   - Test users: add `praveshedu29@gmail.com` while the app is in **Testing**
5. Go to **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Web application**
   - Name: `GramShiksha Study Studio`
   - Authorized JavaScript origins:
     - `https://gramshiksha-academy.vercel.app`
     - `http://localhost:5174` (local dev only)
   - No redirect URI is needed for the browser token flow.
6. Copy the **Client ID** (it ends in `.apps.googleusercontent.com`).

## Add it to Vercel

The value is public and is compiled into the frontend; never put a client secret
in a `VITE_*` variable.

```powershell
$line = Get-Content "$env:USERPROFILE\.gramshiksha\secrets.env" | Where-Object { $_ -match '^VERCEL_TOKEN=' } | Select-Object -First 1
$env:VERCEL_TOKEN = ($line -split '=', 2)[1].Trim().Trim('"').Trim("'")
"<client-id>.apps.googleusercontent.com" | npx vercel env add VITE_GOOGLE_CLIENT_ID production --token $env:VERCEL_TOKEN
npx vercel --prod --yes --token $env:VERCEL_TOKEN
```

Or add `VITE_GOOGLE_CLIENT_ID` in **Vercel → Project → Settings → Environment
Variables → Production**, then redeploy. The value must be present at build time,
so changing it requires a new deployment.

## What the learner sees

1. Open `/studio` and sign in to GramShiksha.
2. In their own NotebookLM, export the notebook to **Google Docs**.
3. Tap **Connect Google Drive**. Google asks for read-only Drive access.
4. Pick the exported Doc from the list and tap **Import selected doc**.
5. Review the text, then build the native study pack.
6. **Disconnect** clears the token from memory. It is never saved.

The card is hidden when `VITE_GOOGLE_CLIENT_ID` is empty, so there is no dead
button on the current deployment.

## Consent-screen status

- **Testing**: up to 100 test users; each must be added manually. Fine for a
  pilot and for the owner’s account.
- **In production**: Google requires OAuth verification for the sensitive
  `drive.readonly` scope. That is free but can take days. Until then, users see
  an “unverified app” warning; this is expected, not a bug.
- A narrower `drive.file` scope would avoid broad Drive access, but NotebookLM
  exports are not created by GramShiksha, so it cannot see them. `drive.readonly`
  plus a user-selected Doc is the honest trade-off.

## Privacy wording

The privacy policy should state:

> If you choose Google Drive import, GramShiksha asks Google for read-only access
> to your Drive so you can select a document. The access token is kept in your
> browser tab and is not stored on our servers. We do not read files you do not
> select, and we do not use Google user data for advertising.

## Verify

- With the env var set, `/studio` shows the Google Drive card.
- Without it, the card is absent and paste/file import still work.
- Connect → pick a Doc → import → build a pack.
- Disconnect → token gone from memory.
- CSP allows `https://accounts.google.com` (script) and
  `https://www.googleapis.com` (Drive API). See `frontend/vercel.json`.
