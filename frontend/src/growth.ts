/**
 * Growth layer: money slots, referral capture, share links.
 *
 * Every money slot renders ONLY when the backend says it is configured
 * (GET /api/growth/config) — an unconfigured slot is invisible, never a
 * broken box. Config is cached for an hour so this costs one request.
 */
export interface GrowthConfig {
  site_url: string;
  referral_enabled: boolean;
  ads: { client: string; slot: string } | null;
  donate: { upi: string | null; url: string | null } | null;
  affiliates: { name: string; url: string }[];
  sponsor: { text: string; url: string } | null;
  premium_url: string | null;
}

const UPI_RE = /^[A-Za-z0-9._-]{2,256}@[A-Za-z][A-Za-z0-9]{1,64}$/;

/** Optional build-time donation fallback for deployments where the Render
 *  environment cannot be edited. The UPI id is public by design (it is shown
 *  on the support card); the backend value still wins when both exist. */
function buildDonateUpi(): string {
  const env = (import.meta as unknown as { env?: Record<string, string> }).env;
  const value = env?.VITE_DONATE_UPI?.trim() ?? '';
  return UPI_RE.test(value) ? value : '';
}

const BUILD_DONATE_UPI = buildDonateUpi();

export const OFF_CONFIG: GrowthConfig = {
  site_url: 'https://gramshiksha-academy.vercel.app',
  referral_enabled: true,
  ads: null,
  donate: BUILD_DONATE_UPI ? { upi: BUILD_DONATE_UPI, url: null } : null,
  affiliates: [],
  sponsor: null,
  premium_url: null,
};

const CACHE_KEY = 'gs_growth';
const CACHE_TTL_MS = 60 * 60 * 1000;
const REF_KEY = 'gs_ref';
const REF_RE = /^GS\d{1,10}$/i;

function withBuildDonation(cfg: GrowthConfig): GrowthConfig {
  const upi = cfg.donate?.upi || BUILD_DONATE_UPI;
  if (!upi) return cfg;
  return { ...cfg, donate: { upi, url: cfg.donate?.url ?? null } };
}

export async function fetchGrowthConfig(): Promise<GrowthConfig> {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (raw) {
      const cached = JSON.parse(raw) as { at: number; cfg: GrowthConfig };
      if (cached?.cfg && Date.now() - cached.at < CACHE_TTL_MS) return cached.cfg;
    }
  } catch { /* corrupt cache → refetch */ }
  try {
    const res = await fetch('/api/growth/config');
    if (!res.ok) throw new Error(String(res.status));
    const cfg = withBuildDonation((await res.json()) as GrowthConfig);
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), cfg }));
    } catch { /* private mode → memory only */ }
    return cfg;
  } catch {
    return OFF_CONFIG;
  }
}

/** Capture ?ref=GS000123 on arrival so registration can credit the inviter.
 *  Runs once per page load; garbage codes are dropped, never stored. */
export function captureReferral(search = location.search): string | null {
  const code = new URLSearchParams(search).get('ref')?.trim().toUpperCase() ?? '';
  if (!REF_RE.test(code)) return null;
  try {
    localStorage.setItem(REF_KEY, code);
  } catch { /* ignore */ }
  return code;
}

/** Invite code stored from an earlier ?ref= visit (sent with registration). */
export function getReferral(): string {
  try {
    const code = (localStorage.getItem(REF_KEY) ?? '').toUpperCase();
    return REF_RE.test(code) ? code : '';
  } catch {
    return '';
  }
}

/** One signup per captured invite: the code must not credit every account
 *  created later on the same device. */
export function clearReferral(): void {
  try {
    localStorage.removeItem(REF_KEY);
  } catch { /* ignore */ }
}

/** Canonical invite link for a user's own code. */
export function inviteLink(code: string, siteUrl = OFF_CONFIG.site_url): string {
  return `${siteUrl.replace(/\/$/, '')}/?ref=${code}`;
}

/** Mobile UPI deep link. The payment goes straight to the configured UPI
 *  account; GramShiksha never handles the PIN or the money. */
export function upiPayUrl(upi: string, payee = 'GramShiksha Academy'): string {
  return `upi://pay?pa=${encodeURIComponent(upi.trim())}&pn=${encodeURIComponent(payee)}&cu=INR`;
}

export interface ShareTargets {
  whatsapp: string;
  telegram: string;
  x: string;
  facebook: string;
  nativeAvailable: boolean;
}

/** Share URLs for a page. All are plain links — no SDK, no tracker, no cost. */
export function shareLinks(pageUrl: string, text: string): ShareTargets {
  const u = encodeURIComponent(pageUrl);
  const t = encodeURIComponent(text);
  return {
    whatsapp: `https://wa.me/?text=${t}%20${u}`,
    telegram: `https://t.me/share/url?url=${u}&text=${t}`,
    x: `https://x.com/intent/tweet?text=${t}&url=${u}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${u}`,
    nativeAvailable:
      typeof navigator !== 'undefined' &&
      typeof (navigator as unknown as { share?: unknown }).share === 'function',
  };
}
