/* Gramshiksha service worker — tiny, dependency-free.

   app shell  = cache-first (fast reloads on a 2G connection).
   /api GET   = network-first with cache fallback, so lessons stay readable
                offline.

   Two rules that keep a shared phone honest:
   - /api/auth/* is never touched: it carries tokens and password-reset
     traffic, and caching it would let a second account replay it offline.
   - only 2xx bodies are stored. A cached 401/500 would poison offline mode
     (the app would see "logged out" the moment connectivity dropped), and it
     would keep one user's responses around for the next. Logout additionally
     calls clearCachedApi() in auth.ts. */
const CACHE = 'gramshiksha-v3';
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/favicon.svg'];

const OFFLINE = new Response('Offline', { status: 503, statusText: 'Offline' });

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
});

const putIfOk = (request, res) => {
  if (res.ok) {
    const copy = res.clone();
    caches.open(CACHE).then((c) => c.put(request, copy));
  }
  return res;
};

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;

  // Auth: pass straight through, never cached, never replayed offline.
  if (url.pathname.startsWith('/api/auth/')) return;

  if (url.pathname.startsWith('/api/')) {
    // network-first, fall back to cache (offline lesson reading)
    e.respondWith(
      fetch(e.request)
        .then((res) => putIfOk(e.request, res))
        .catch(() => caches.match(e.request).then((hit) => hit || OFFLINE))
    );
    return;
  }

  if (e.request.mode === 'navigate') {
    // Deep SPA routes (/learn/3) have no cached entry of their own — serve
    // the shell so a reload still renders offline instead of erroring.
    e.respondWith(
      fetch(e.request)
        .then((res) => putIfOk(e.request, res))
        .catch(() => caches.match('/index.html').then((hit) => hit || caches.match('/')))
    );
    return;
  }

  // app shell assets: cache-first
  e.respondWith(
    caches.match(e.request).then(
      (hit) => hit || fetch(e.request).then((res) => putIfOk(e.request, res))
    )
  );
});
