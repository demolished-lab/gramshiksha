export type Route = { page: string; sub?: string; id?: number };

/**
 * Parse both the canonical path (`/course/42`) and the legacy hash form
 * (`#/course/42`) so old bookmarks, QR codes and WhatsApp links keep working
 * after the move away from hash-only routing.
 */
export function parseRoute(input: string): Route {
  let raw = input || '';
  if (raw.startsWith('#')) raw = raw.slice(1);
  raw = raw.split('?')[0].split('#')[0];
  const path = raw.replace(/^\/+/, '').replace(/\/+$/, '');
  const [page, second, ...extra] = path.split('/');
  if (page === 'login') return { page, sub: second };
  const routePage = page || 'home';

  if (routePage === 'course' || routePage === 'lesson') {
    if (extra.length || !second || !/^[1-9]\d*$/.test(second)) return { page: 'not-found' };
    const id = Number(second);
    return Number.isSafeInteger(id) ? { page: routePage, id } : { page: 'not-found' };
  }

  return { page: routePage, id: second ? Number(second) : undefined };
}

/** The canonical URL path for a route. Home is `/`, never `/home`. */
export function pathFor(page: string, id?: number): string {
  if (page === 'home' || page === '') return '/';
  return `/${page}${id ? `/${id}` : ''}`;
}
