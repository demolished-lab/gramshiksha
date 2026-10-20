/* Gramshiksha service worker — tiny, dependency-free.

   app shell  = cache-first (fast reloads on a 2G connection).
   /api GET   = network-first with cache fallback, so lessons stay readable
                offline.

   Rules that keep a shared phone honest:
   - /api/auth/* is never touched: it carries tokens and password-reset
     traffic, and caching it would let a second account replay it offline.
   - only 2xx bodies are stored. A cached 401/500 would poison offline mode
     (the app would see "logged out" the moment connectivity dropped).
   - an *authenticated* response is stored in a per-account cache
     (`gramshiksha-api:<opaque-id>`), never in the shared shell cache. The id
     is pushed by auth.ts on login/boot; without it private responses are not
     cached at all. Logout deletes every per-account cache. This is what stops
     the next person on the same phone from reading the previous user's
     offline dashboard.
   - responses marked `no-store` or `private` are the server saying "don't
     keep this" — we only keep the private ones in the per-account cache,
     which is exactly the scope the header allows. */
const CACHE = 'gramshiksha-v3';
const API_PREFIX = 'gramshiksha-api:';
const OFFLINE_MATERIALS = 'gramshiksha-offline-materials';
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/favicon.svg'];

const OFFLINE = new Response('Offline', { status: 503, statusText: 'Offline' });

let apiScope = null;

self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type !== 'gs-session') return;
  const raw = typeof data.userId === 'string' ? data.userId : '';
  apiScope = raw ? raw.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 64) || null : null;
  if (!apiScope) {
    event.waitUntil(caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k.startsWith(API_PREFIX)).map((k) => caches.delete(k))
    )));
  }
});

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys
        // Keep the shell and the user's explicitly downloaded study
        // materials (offlineMaterials.ts owns that cache); drop per-account
        // API caches so a shell update also clears private data.
        .filter((k) => k !== CACHE && !k.startsWith(OFFLINE_MATERIALS))
        .map((k) => caches.delete(k))
    ))
  );
});

const putIfOk = (request, res, cacheName = CACHE) => {
  // A textbook PDF can be 15 MB — caching it would eat the storage quota of
  // the shared, low-end phones this app targets. `no-store` is an explicit
  // instruction from the server; `redirected` bodies are not the response the
  // request asked for.
  const type = res.headers.get('content-type') || '';
  const cacheControl = (res.headers.get('cache-control') || '').toLowerCase();
  if (res.ok && !res.redirected && !type.includes('pdf') && !cacheControl.includes('no-store')) {
    const copy = res.clone();
    caches.open(cacheName).then((c) => c.put(request, copy));
  }
  return res;
};

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;

  // Auth: pass straight through, never cached, never replayed offline.
  if (url.pathname.startsWith('/api/auth/')) return;

  if (url.pathname.startsWith('/api/')) {
    const isPrivate = e.request.headers.has('authorization');
    const cacheName = isPrivate ? (apiScope ? API_PREFIX + apiScope : null) : CACHE;
    // Private response before the session handshake (SW just woke up): let it
    // go straight to the network rather than risk storing it in the shell.
    if (!cacheName) return;
    e.respondWith(
      fetch(e.request)
        .then((res) => putIfOk(e.request, res, cacheName))
        .catch(() => caches.open(cacheName)
          .then((c) => c.match(e.request))
          .then((hit) => hit || OFFLINE))
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
