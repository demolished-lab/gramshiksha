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
  rewrites: { source: string; destination: string }[];
  headers: Rule[];
};

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

  it('proxies /api/* to the Render backend', () => {
    expect(config.rewrites).toEqual([
      {
        source: '/api/:path*',
        destination: 'https://gramshiksha-backend.onrender.com/api/:path*',
      },
    ]);
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
    const csp = headerValue('/', 'Content-Security-Policy') ?? '';
    expect(csp, 'document has no CSP').toBeTruthy();
    expect(csp).toContain("frame-ancestors 'none'"); // clickjacking
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("frame-src 'self'"); // same-origin textbook reader
    expect(csp).toContain('googlesyndication.com'); // AdSense, once enabled
    expect(csp).toContain('gramshiksha-backend.onrender.com'); // direct API base
    // No inline script execution: the build has no inline <script>, and the
    // JSON-LD block is a data block, not executable script.
    expect(csp).not.toMatch(/script-src[^;]*'unsafe-inline'/);
    expect(headerValue('/', 'X-Frame-Options')).toBe('DENY');
  });

  it('serves one identical CSP on every document route', () => {
    const csps = config.headers
      .flatMap((r) => r.headers)
      .filter((h) => h.key === 'Content-Security-Policy')
      .map((h) => h.value);
    expect(csps.length).toBeGreaterThan(1);
    expect(new Set(csps).size).toBe(1);
  });
});
