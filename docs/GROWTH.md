# Growth & monetization — autonomous earning on free tiers only

Rule: money flows **in**, never out. Every tool below has a free tier and no
step here asks for a card. Each revenue slot is config-gated: the site hides
any slot whose key is empty, so enabling a stream = finishing its one-time
setup + pasting one value into Render's dashboard env (never into the repo).

## Already live (zero action needed)

| System | How it earns / grows | Code |
|---|---|---|
| Referral loop | Every user gets an invite code (`GS000123`); shared links carry `?ref=`; signups credit the inviter on a public leaderboard | `routers/growth.py`, `growth.ts`, `AuthModal` |
| Share row | Native sheet + WhatsApp/Telegram/X/Facebook on the landing footer | `components/ShareButtons.tsx` |
| SEO base | OG/Twitter cards, canonical, JSON-LD, `robots.txt`, `sitemap.xml` | `index.html`, `public/` |
| RSS feed | `GET /api/feed.xml` — newest public materials + courses | `routers/growth.py` |
| Money slots | AdSense, donate, affiliates, sponsor, premium — all hidden until configured | `components/AdSlot.tsx`, `components/SupportBar.tsx` |

## One-time setups (each unlocks a stream forever)

1. **Google AdSense** (ads): apply at google.com/adsense with the live URL.
   After approval, set `ADSENSE_CLIENT` (`ca-pub-…`) + `ADSENSE_SLOT`. The
   slot appears automatically; before approval the layout is ad-free.
2. **Donations**: note your UPI id → `DONATE_UPI`; optionally a free
   Ko-fi page → `DONATE_URL`. The support card appears automatically.
3. **Affiliates**: join free programs (bookstores, stationery, ed-tech —
   Amazon Associates and most Indian bookshops accept free sites). Set
   `AFFILIATE_LINKS` to JSON `[{"name":"…","url":"https://…"}]` — only
   https URLs are ever rendered.
4. **Premium**: create a free Razorpay payment page (no website needed) →
   `PREMIUM_URL`. Free learning never changes; this is a support tier.
5. **Sponsor**: sell the one-line slot manually to a local business →
   `SPONSOR_TEXT` + `SPONSOR_URL`.

## Traffic automation (free)

- **Search Console + Bing Webmaster**: submit the URL + `sitemap.xml` once
  each. This is the only manual SEO step; everything else is in the code.
- **Social autopilot**: create free accounts (X, Facebook, Telegram channel,
  WhatsApp channel), then connect a free cross-poster (IFTTT, Buffer, or
  Make free tier) to `https://gramshiksha-backend.onrender.com/api/feed.xml`
  → every new lesson/material auto-posts with zero maintenance.
- **Directories (submit once, free)**: Google Business (if applicable),
  Product Hunt, AlternativeTo, SaaSHub, education directories, NCERT/resource
  link lists, relevant subreddits' resource wikis.
- **Virality**: the referral leaderboard + invite links are the loop — every
  new user is a potential inviter at no cost.

## After changing any key

Render dashboard → service → Environment → set the key → Save (auto-redeploys
on free tier). No code change, no Vercel redeploy — the SPA reads
`/api/growth/config` live (cached 1 hour).
