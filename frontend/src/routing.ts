export type Route = { page: string; sub?: string; id?: number };

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#\/?/, '');
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
