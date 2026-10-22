# Growth & monetization — autonomous earning on free tiers only

Rule: money flows **in**, never out. Every tool below has a free tier and no
step here asks for a card. Each revenue slot is config-gated: the site hides
any slot whose key is empty, so enabling a stream = finishing its one-time
setup + pasting one value into Render (never into the repo).

## Already implemented

| System | How it grows / earns | Code |
|---|---|---|
| Referral loop | Every user gets an invite code (`GS000123`); shared links carry `?ref=`; signups credit the inviter on a public leaderboard | `backend/app/routers/growth.py`, `frontend/src/growth.ts`, `AuthModal` |
| Share row | Native sheet + WhatsApp/Telegram/X/Facebook in the site footer and on the landing page | `frontend/src/components/ShareButtons.tsx` |
| SEO base | Per-route HTML titles/descriptions, canonicals, Open Graph, Twitter cards, JSON-LD, `robots.txt`, `sitemap.xml`, real path URLs | `frontend/seo-routes.json`, `frontend/scripts/generate-seo-pages.mjs` |
| RSS feed | `GET /api/feed.xml` — newest public materials + courses | `backend/app/routers/growth.py` |
| AdSense slot | Renders only after both `ADSENSE_CLIENT` and `ADSENSE_SLOT` are set; one labelled slot on public study pages, never on login/private/404 screens | `frontend/src/components/AdSlot.tsx` |
| `ads.txt` | Vercel proxies `/ads.txt` to the backend; a valid publisher ID publishes the official `google.com, pub-…, DIRECT, …` line, otherwise the route is a clean 404 | `backend/app/routers/growth.py`, `frontend/vercel.json` |
| Trust pages | Public About, Contact, Privacy Policy and Terms of Use, linked from every footer | `frontend/src/pages/Legal.tsx` |
| Money slots | Donate, affiliates, sponsor and premium links — all hidden until configured | `frontend/src/components/SupportBar.tsx` |

## One-time setups

### 1. Google AdSense (ads)

1. Apply at <https://www.google.com/adsense/> using the live URL
   `https://gramshiksha-academy.vercel.app/`. Use the same Google account that
   owns Search Console so verification is shared.
2. Add the site in AdSense. If it asks for verification, use the Search Console
   method or the meta-tag method below.
3. In AdSense, create one responsive display unit. Keep the generated
   publisher ID (`ca-pub-` + 16 digits) and numeric slot ID.
4. In Render → the backend service → Environment, set:
   - `ADSENSE_CLIENT=ca-pub-…`
   - `ADSENSE_SLOT=…`
   Save; Render redeploys automatically on the free tier.
5. Check the public endpoints:
   - `https://gramshiksha-academy.vercel.app/api/growth/config` returns
     `"ads": {"client": "ca-pub-…", "slot": "…"}`.
   - `https://gramshiksha-academy.vercel.app/ads.txt` returns the
     `google.com, pub-…, DIRECT, f08c47fec0942fa0` line.
   - A public page shows one `Advertisement`-labelled slot. Login, dashboard,
     course/lesson detail and 404 pages stay ad-free.
6. In AdSense, request review. Approval is a Google decision and is not
   guaranteed. Keep publishing original lessons and materials while waiting.
7. For visitors in the EEA, UK or Switzerland, configure a Google-certified
   consent message in AdSense → Privacy & messaging. The privacy policy already
   explains cookies, Google advertising and opt-out links.

Never click your own ads, ask others to click them, or place ads on empty,
private or misleading pages. Those actions can permanently close the account.
Do not paste the publisher ID into a public issue; it is public on the page, but
account access is not.

### 2. Search Console and Bing Webmaster (discovery)

1. Add `https://gramshiksha-academy.vercel.app/` as a URL-prefix property in
   <https://search.google.com/search-console>.
2. Choose the HTML meta-tag verification method. Put the token (only the
   `content` value) in Vercel → Project → Settings → Environment Variables as
   `GOOGLE_SITE_VERIFICATION`, then redeploy the frontend. The build writes the
   meta tag into every generated public page.
3. Submit `https://gramshiksha-academy.vercel.app/sitemap.xml`.
4. Use URL Inspection on `/`, `/courses`, `/materials`, `/textbooks`,
   `/practice` and `/explore/8`; request indexing once. Do not repeatedly
   request the same URL.
5. Repeat the sitemap submission at <https://www.bing.com/webmasters> (it can
   import from Search Console for free).

Status (2026-10-21): URL-prefix property verified with the HTML tag; the
sitemap was accepted with 22 discovered pages; indexing was requested once for
`/`, `/courses`, `/materials`, `/textbooks`, `/practice`, `/explore` and
`/explore/8`. Recheck the Pages report after Google has had time to crawl.

Status (2026-10-21): `/materials` is no longer empty. Twenty-one original
**Course Revision Checklist** PDFs were published - one for every seeded
course (Classes 1–12, SSC/HSC/CBSE) - with chapter/lesson checklists, a
25-minute study routine and an exam-day plan. They are public, approved and
available without login. This gives AdSense reviewers a real content shelf
alongside the courses, practice and textbook links. See
`docs/DEPLOYMENT.md` for the Cloudinary free-plan PDF-delivery setting.

A new `vercel.app` subdomain can take days or weeks to appear for a competitive
brand. The code removes the technical blockers; authority still comes from
useful content, a custom domain later, and genuine links.

### 3. Donations

Set one or both in Render:

- `DONATE_UPI=name@upi` — a valid UPI id. The card shows **Donate with UPI**
  (opens the learner's UPI app) and a **Copy UPI** button. The payment goes
  straight to that account; GramShiksha never sees the PIN.
- `DONATE_URL=https://ko-fi.com/yourpage` (or another free page). Only an
  absolute `https://` link is accepted.

The support card appears automatically. Never put a bank password, card number
or UPI PIN in the repo or an env value. A malformed UPI id or non-HTTPS link is
hidden rather than rendered as a broken button.

If the Render environment cannot be edited, the same public UPI id can be
baked in at frontend build time with `VITE_DONATE_UPI=name@upi` (Vercel →
Production env, then redeploy). `DONATE_UPI` in Render still wins when both are
set; use one source of truth once Render is available.

### 4. Affiliates

Join free programs (bookstores, stationery, ed-tech; Amazon Associates and most
Indian bookshops accept free sites). Set `AFFILIATE_LINKS` to JSON:

```json
[{"name":"Example bookstore","url":"https://example.com/?aff=you"}]
```

Only `https` URLs with a host are served back. Affiliate links render with
`rel="noopener sponsored nofollow"`.

### 5. Premium support tier

Create a free Razorpay payment page (or another no-code payment link) and set
`PREMIUM_URL`. Free learning never changes; this is an optional support tier.

### 6. Sponsor slot

Sell one line manually to a local business, then set `SPONSOR_TEXT` and
`SPONSOR_URL`. It renders after the other support cards.

## Traffic automation (free)

- **Social autopilot**: create free accounts (X, Facebook, Telegram channel,
  WhatsApp channel), then connect a free cross-poster (IFTTT, Buffer or Make
  free tier) to `https://gramshiksha-backend.onrender.com/api/feed.xml`.
  New public lessons/materials auto-post with no maintenance.
- **Directories (submit once, free)**: Google Business (if applicable),
  Product Hunt, AlternativeTo, SaaSHub, education directories, NCERT/resource
  link lists, and relevant community resource wikis. Follow each community's
  self-promotion rules; spam links do not help SEO.
- **Virality**: the referral leaderboard + invite links are the loop. No cash
  reward is attached, so fake-account farming buys nothing.
- **Custom domain (optional, later)**: buy only if it fits the inbound-cash
  rule. Update `SITE_URL` (Render), the `site` value in
  `frontend/seo-routes.json`, `public/robots.txt`, `public/sitemap.xml`,
  `index.html`, and redeploy. Add a 301 from the old host if the host supports
  it; never run two canonical hosts at once.
- **Keep-warm (free)**: a free external pinger can call
  `https://gramshiksha-backend.onrender.com/ready` every 10 minutes. Do not add
  a cron on the user's machine.

## After changing any key

Render dashboard → service → Environment → set the key → Save (auto-redeploys
on free tier). No code change, no Vercel redeploy — the SPA reads
`/api/growth/config` live (cached 1 hour in the browser).

For a Search Console token, Vercel needs a new frontend deployment because the
meta tag is written at build time. For an AdSense publisher ID, only Render
needs the change; the ad config and `/ads.txt` update without a frontend build.

## Guardrails

- No paid tool, subscription, card, or trial that can auto-charge.
- No ad on a login, dashboard, private, empty or error page.
- No invented publisher IDs, payment links or affiliate URLs.
- Secrets live only in Render/Vercel env or `%USERPROFILE%\.gramshiksha\secrets.env`;
  never in git, docs, screenshots or chat.
- Keep the backend's `X-Frame-Options: SAMEORIGIN` on PDFs; the frontend header
  rule must never cover `/api/*` or `/ads.txt`.
