import { Component, StrictMode, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { clearCachedApi } from './auth';
import './styles.css';

class ErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(e: unknown) {
    return { error: e instanceof Error ? e.message : 'Something went wrong' };
  }
  componentDidCatch() {
    // v1: report to console; production APM (e.g. Sentry) plugs in here.
    // eslint-disable-next-line no-console
    console.error('GramShiksha UI crashed');
  }
  render() {
    if (this.state.error) {
      return (
        <main className="container">
          <div className="empty-state">
            <div className="icon">⚠️</div>
            <p>Something went wrong loading this page.</p>
            <button className="btn small" onClick={() => { localStorage.clear(); void clearCachedApi(); location.hash = '#/home'; location.reload(); }}>
              Reset & reload
            </button>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>
);

// A deploy replaces the hashed chunk files, so a tab that stayed open across
// one can ask for a chunk that no longer exists and land on the error
// boundary (seen live: Textbooks-*.js 404 right after a release). Vite fires
// this event for exactly that case — reload once to pick up the new index.
// The guard stops a genuine CDN outage from becoming a reload loop.
window.addEventListener('vite:preloadError', (event) => {
  event.preventDefault();
  try {
    const last = Number(sessionStorage.getItem('gs-preload-reload') ?? 0);
    if (Date.now() - last < 60_000) return;   // already retried: let the boundary speak
    sessionStorage.setItem('gs-preload-reload', String(Date.now()));
  } catch {
    return;                                    // storage unavailable: don't risk a loop
  }
  window.location.reload();
});

// PWA: register service worker (offline + low-bandwidth cache)
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    // updateViaCache: 'none' — never trust a cached copy of sw.js itself.
    navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).catch(() => {
      /* offline support unavailable — app still works */
    });
    // The cache name only changes when sw.js bumps CACHE, so without an
    // explicit check a user on a slow connection can keep running yesterday's
    // worker for days. Re-check once an hour (cheap: conditional request).
    window.setInterval(() => {
      navigator.serviceWorker
        .getRegistration()
        .then((reg) => reg?.update())
        .catch(() => { /* offline */ });
    }, 60 * 60 * 1000);
  });
}
