import data from '../seo-routes.json';

export type SeoEntry = {
  path: string;
  title: string;
  description: string;
  h1?: string;
  summary?: string;
  robots: string;
  sitemap?: boolean;
  priority?: number;
  changefreq?: string;
  static?: boolean;
  grades?: number[];
  schema: Record<string, unknown> | null;
};

type RawEntry = Omit<SeoEntry, 'schema'> & {
  schema: Record<string, unknown> | null;
};

const SITE = data.site;
const SITE_NAME = data.siteName;
const DEFAULT_IMAGE = data.image;

const fill = (value: unknown, grade: number): unknown => {
  if (typeof value === 'string') {
    const boards = grade >= 11 ? 'HSC & CBSE' : 'SSC & CBSE';
    return value.replace(/\{grade\}/g, String(grade)).replace(/\{boards\}/g, boards);
  }
  if (Array.isArray(value)) return value.map((item) => fill(item, grade));
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, fill(item, grade)]),
    );
  }
  return value;
};

export function normalizePath(pathname: string): string {
  let clean = pathname.split('?')[0].split('#')[0];
  if (!clean.startsWith('/')) clean = `/${clean}`;
  if (clean.length > 1) clean = clean.replace(/\/+$/, '');
  return clean || '/';
}

export function canonicalUrl(pathname: string): string {
  const path = normalizePath(pathname);
  return `${SITE}${path === '/' ? '/' : path}`;
}

export function imageUrl(): string {
  return DEFAULT_IMAGE.startsWith('http') ? DEFAULT_IMAGE : `${SITE}${DEFAULT_IMAGE}`;
}

const expand = (entry: RawEntry, grade: number): SeoEntry => ({
  ...(fill(entry, grade) as SeoEntry),
  path: entry.path.replace('{grade}', String(grade)),
});

export function seoForPath(pathname: string): SeoEntry | null {
  const path = normalizePath(pathname);

  const exact = (data.routes as RawEntry[]).find((entry) => !entry.path.includes('{grade}') && entry.path === path);
  if (exact) return { ...exact, schema: exact.schema };

  const graded = (data.routes as RawEntry[]).find((entry) => entry.path.includes('{grade}'));
  if (graded) {
    const match = path.match(/^\/explore\/(\d{1,2})$/);
    const grade = match ? Number(match[1]) : NaN;
    if (graded.grades?.includes(grade)) return expand(graded, grade);
  }

  for (const rule of data.dynamicRoutes) {
    try {
      if (new RegExp(rule.pattern).test(path)) {
        return {
          path,
          title: rule.title,
          description: rule.description,
          robots: rule.robots,
          schema: rule.schema,
        };
      }
    } catch {
      // A bad pattern should never blank the page head.
    }
  }

  return null;
}

function upsertMeta(attribute: 'name' | 'property', key: string, content: string): void {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attribute, key);
    document.head.appendChild(el);
  }
  el.content = content;
}

function upsertLink(rel: string, href: string): void {
  let el = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!el) {
    el = document.createElement('link');
    el.rel = rel;
    document.head.appendChild(el);
  }
  el.href = href;
}

function applySchema(schema: Record<string, unknown> | null): void {
  const old = document.head.querySelector<HTMLScriptElement>('script[data-seo-jsonld]');
  if (!schema) {
    old?.remove();
    return;
  }
  const el = old ?? document.createElement('script');
  el.type = 'application/ld+json';
  el.dataset.seoJsonld = 'true';
  el.textContent = JSON.stringify(schema);
  if (!old) document.head.appendChild(el);
}

/**
 * Keep the document head correct after every client-side navigation. Static
 * HTML already carries the same values for direct visits; this is the SPA
 * counterpart, and it also gives private routes an explicit noindex.
 */
export function applySeo(pathname: string): void {
  const path = normalizePath(pathname);
  const entry = seoForPath(path);
  const title = entry?.title ?? 'Page not found | GramShiksha Academy';
  const description = entry?.description
    ?? 'Explore free lessons, practice, study materials and textbooks on GramShiksha Academy.';
  const robots = entry?.robots ?? 'noindex, nofollow';
  const canonical = canonicalUrl(path);
  const image = imageUrl();

  document.title = title;
  upsertMeta('name', 'description', description);
  upsertMeta('name', 'robots', robots);
  upsertMeta('name', 'application-name', SITE_NAME);
  upsertMeta('property', 'og:type', path === '/' ? 'website' : 'article');
  upsertMeta('property', 'og:site_name', SITE_NAME);
  upsertMeta('property', 'og:title', title);
  upsertMeta('property', 'og:description', description);
  upsertMeta('property', 'og:url', canonical);
  upsertMeta('property', 'og:image', image);
  upsertMeta('property', 'og:image:width', '1600');
  upsertMeta('property', 'og:image:height', '900');
  upsertMeta('property', 'og:image:alt', 'Students learning together in a bright classroom');
  upsertMeta('property', 'og:locale', 'en_IN');
  upsertMeta('property', 'og:locale:alternate', 'hi_IN');
  upsertMeta('name', 'twitter:card', 'summary_large_image');
  upsertMeta('name', 'twitter:title', title);
  upsertMeta('name', 'twitter:description', description);
  upsertMeta('name', 'twitter:image', image);
  upsertLink('canonical', canonical);
  applySchema(entry?.schema ?? null);
}
