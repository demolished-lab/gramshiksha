/**
 * Post-build SEO pass.
 *
 * Vite emits one index.html for the SPA. Public sections still need their own
 * title, description, canonical and structured data before JavaScript runs,
 * otherwise Google sees the same page at every URL. This script writes a small
 * HTML file per public route; Vercel's `cleanUrls` serves `/courses` from
 * `courses.html` while the app boots normally from the same hashed bundle.
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dist = join(root, 'dist');
const data = JSON.parse(await readFile(join(root, 'seo-routes.json'), 'utf8'));
const base = await readFile(join(dist, 'index.html'), 'utf8');
const site = data.site.replace(/\/$/, '');
const image = data.image.startsWith('http') ? data.image : `${site}${data.image}`;
const today = new Date().toISOString().slice(0, 10);
const verification = (process.env.GOOGLE_SITE_VERIFICATION || '').trim();

const escapeHtml = (value) => String(value)
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;');

const fill = (value, grade) => {
  if (typeof value === 'string') return value.replaceAll('{grade}', String(grade));
  if (Array.isArray(value)) return value.map((item) => fill(item, grade));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, fill(item, grade)]));
  }
  return value;
};

const expand = (entry) => {
  if (!entry.path.includes('{grade}')) return [entry];
  return (entry.grades || []).map((grade) => ({
    ...fill(entry, grade),
    path: entry.path.replace('{grade}', String(grade)),
  }));
};

const entries = data.routes.flatMap(expand);
const staticEntries = entries.filter((entry) => entry.static);

const meta = (attribute, key, content) =>
  `<meta ${attribute}="${escapeHtml(key)}" content="${escapeHtml(content)}">`;

const replaceMeta = (html, attribute, key, content) => {
  const pattern = new RegExp(
    `<meta\\s+[^>]*${attribute}="${key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"[^>]*>`,
    'i',
  );
  const tag = meta(attribute, key, content);
  return pattern.test(html) ? html.replace(pattern, tag) : html.replace('</head>', `  ${tag}\n</head>`);
};

const fallback = (entry) => {
  const title = entry.h1 || entry.title;
  const summary = entry.summary || entry.description;
  return [
    '<noscript>',
    '  <main style="max-width:760px;margin:48px auto;padding:0 20px;font-family:system-ui,sans-serif;line-height:1.6">',
    `    <h1>${escapeHtml(title)}</h1>`,
    `    <p>${escapeHtml(summary)}</p>`,
    '    <nav aria-label="Public pages">',
    '      <a href="/">Home</a> · <a href="/courses">Courses</a> · <a href="/materials">Study materials</a> · ',
    '      <a href="/textbooks">Textbooks</a> · <a href="/practice">Practice</a> · <a href="/explore">Explore</a>',
    '    </nav>',
    '    <p><a href="/about">About</a> · <a href="/contact">Contact</a> · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></p>',
    '  </main>',
    '</noscript>',
  ].join('\n');
};

const withHead = (entry) => {
  const path = entry.path === '/' ? '/' : entry.path;
  const canonical = `${site}${path}`;
  let html = base;

  html = html.replace(/<title>[\s\S]*?<\/title>/i, `<title>${escapeHtml(entry.title)}</title>`);
  html = replaceMeta(html, 'name', 'description', entry.description);
  html = replaceMeta(html, 'name', 'robots', entry.robots);
  html = replaceMeta(html, 'property', 'og:title', entry.title);
  html = replaceMeta(html, 'property', 'og:description', entry.description);
  html = replaceMeta(html, 'property', 'og:url', canonical);
  html = replaceMeta(html, 'property', 'og:image', image);
  html = replaceMeta(html, 'name', 'twitter:title', entry.title);
  html = replaceMeta(html, 'name', 'twitter:description', entry.description);
  html = replaceMeta(html, 'name', 'twitter:image', image);
  html = html.replace(
    /<link\s+rel="canonical"[^>]*>/i,
    `<link rel="canonical" href="${escapeHtml(canonical)}">`,
  );

  if (verification) {
    html = replaceMeta(html, 'name', 'google-site-verification', verification);
  }

  const schema = entry.schema
    ? `<script type="application/ld+json" data-seo-jsonld="true">${JSON.stringify(entry.schema)}</script>`
    : '';
  html = html.replace(
    /<script\s+type="application\/ld\+json"[^>]*>[\s\S]*?<\/script>/i,
    schema,
  );
  if (schema && !html.includes('data-seo-jsonld')) {
    html = html.replace('</head>', `  ${schema}\n</head>`);
  }

  // A crawler that does not execute the SPA still gets the route's real H1,
  // summary and a small set of internal links instead of one generic shell.
  html = html.replace(/<noscript>[\s\S]*?<\/noscript>/i, fallback(entry));

  return html;
};

for (const entry of staticEntries) {
  const path = entry.path === '/' ? '/index.html' : `${entry.path}.html`;
  const file = join(dist, path);
  await mkdir(dirname(file), { recursive: true });
  await writeFile(file, withHead(entry), 'utf8');
}

const sitemapEntries = entries
  .filter((entry) => entry.sitemap)
  .map((entry) => {
    const loc = `${site}${entry.path === '/' ? '/' : entry.path}`;
    return [
      '  <url>',
      `    <loc>${escapeHtml(loc)}</loc>`,
      `    <lastmod>${today}</lastmod>`,
      `    <changefreq>${entry.changefreq || 'monthly'}</changefreq>`,
      `    <priority>${(entry.priority ?? 0.5).toFixed(1)}</priority>`,
      '  </url>',
    ].join('\n');
  })
  .join('\n');

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sitemapEntries}
</urlset>
`;
await writeFile(join(dist, 'sitemap.xml'), sitemap, 'utf8');

console.log(`SEO: wrote ${staticEntries.length} static pages and ${sitemapEntries ? sitemapEntries.split('<url>').length - 1 : 0} sitemap URLs.`);
