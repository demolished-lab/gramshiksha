/**
 * `frontend/vercel.json` is production delivery config: nothing in `src/`
 * imports it, so a mistake there ships silently and only surfaces in a live
 * browser. Two real failures are pinned here so they cannot come back:
 *
 *  1. Vercel's config parser rejects a UTF-8 BOM, and a Windows editor adds one
 *     invisibly — the deploy then fails with "Couldn't parse JSON file".
 *  2. A blanket framing header over `/api/*` would break the in-app textbook
 *     reader. The reader is a same-origin <iframe> whose PDF the backend
 *     deliberately marks `X-Frame-Options: SAMEORIGIN`; if the SPA's header
 *     config ever overwrote that with DENY, every book would open to a blank
 *     frame with only a console error to explain it.
 *
 * The file is pulled in as raw text (Vite's `?raw`, typed via vite/client) so
 * a leading BOM is visible — a plain JSON import would have been parsed
 * already. This also keeps the test dependency-free: the project has no
 * @types/node, so `fs` is not available here by design.
 */
import rawConfig from '../../vercel.json?raw';
import { describe, expect, it } from 'vitest';

type Header = { key: string; value: string };
type Rule = { source: string; headers: Header[] };

const config = JSON.parse(rawConfig) as {
  cleanUrls?: boolean;
  rewrites: { source: string; destination: string }[];
  headers: Rule[];
};

const DOCUMENT_SOURCE = '/((?!api/|assets/|images/|favicon\\.svg|manifest\\.webmanifest|sw\\.js|robots\\.txt|sitemap\\.xml|ads\\.txt).*)';

const headersOf = (source: string) =>
  config.headers.find((r) => r.source === source)?.headers ?? [];
const headerKeys = (source: string) => headersOf(source).map((h) => h.key);
const headerValue = (source: string, key: string) =>
  headersOf(source).find((h) => h.key === key)?.value;

describe('vercel.json delivery config', () => {
  it('is BOM-free so Vercel can parse it', () => {
    expect(rawConfig.charCodeAt(0)).not.toBe(0xfeff);
    expect(config.rewrites.length).toBeGreaterThan(0);
  });

  it('proxies /api/* to the Render backend and keeps private routes in the SPA', () => {
    expect(config.rewrites[0]).toEqual({
      source: '/api/:path*',
      destination: 'https://gramshiksha-backend.onrender.com/api/:path*',
    });
    const rewritten = new Map(config.rewrites.map((r) => [r.source, r.destination]));
    for (const path of ['/dashboard', '/studio', '/progress', '/downloads', '/teacher',
      '/parent', '/admin', '/course/:id', '/lesson/:id']) {
      expect(rewritten.get(path), `missing rewrite for ${path}`).toBe('/');
    }
    expect(rewritten.get('/ads.txt')).toBe('https://gramshiksha-backend.onrender.com/ads.txt');
    expect(config.cleanUrls, 'cleanUrls must serve /courses from courses.html').toBe(true);
  });

  it('hardens every response against sniffing and referrer leaks', () => {
    const keys = headerKeys('/((?!api/).*)');
    for (const key of [
      'X-Content-Type-Options',
      'Referrer-Policy',
      'Permissions-Policy',
      'Strict-Transport-Security',
      'Cross-Origin-Opener-Policy',
    ]) {
      expect(keys, `missing ${key} on /((?!api/).*)`).toContain(key);
    }
  });

  it('leaves framing and CSP to the backend on /api/*', () => {
    // The PDF route sets SAMEORIGIN on purpose; a blanket rule here would
    // clobber it and blank the reader. The source explicitly excludes /api/*,
    // so Vercel cannot add its own framing/Cache-Control headers there.
    const keys = headerKeys('/((?!api/).*)');
    expect(keys).not.toContain('X-Frame-Options');
    expect(keys).not.toContain('Content-Security-Policy');
  });

  it('frames the app nowhere, but still frames the reader and allows AdSense', () => {
    const csp = headerValue(DOCUMENT_SOURCE, 'Content-Security-Policy') ?? '';
    expect(csp, 'document has no CSP').toBeTruthy();
    expect(csp).toContain("frame-ancestors 'none'"); // clickjacking
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("frame-src 'self'"); // same-origin textbook reader
    expect(csp).toContain('googlesyndication.com'); // AdSense, once enabled
    expect(csp).toContain('fundingchoicesmessages.google.com'); // Google-certified CMP
    expect(csp).toContain('gramshiksha-backend.onrender.com'); // direct API base
    expect(csp).toContain('https://www.googleapis.com'); // opt-in Drive import
    expect(csp).toContain('https://accounts.google.com'); // Google Identity Services
    // AdSense injects inline bootstrap code; its publisher script cannot run
    // under a nonce-only policy. Keep the rest of the policy tight instead of
    // shipping an ad slot that is silently blocked.
    expect(csp).toMatch(/script-src[^;]*'unsafe-inline'/);
    expect(csp).toContain("script-src 'self'");
    expect(headerValue(DOCUMENT_SOURCE, 'X-Frame-Options')).toBe('DENY');
  });

  it('serves one identical CSP on every document route', () => {
    const csps = config.headers
      .flatMap((r) => r.headers)
      .filter((h) => h.key === 'Content-Security-Policy')
      .map((h) => h.value);
    expect(csps).toHaveLength(1);
    expect(new Set(csps).size).toBe(1);
  });

  it('keeps login, learner workspaces and dynamic pages out of search', () => {
    const noindex = config.headers
      .find((r) => r.source.includes('dashboard') && r.source.includes('studio'));
    expect(noindex?.headers).toContainEqual({
      key: 'X-Robots-Tag',
      value: 'noindex, nofollow',
    });
  });
});
