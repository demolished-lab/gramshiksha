import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { dataSaver, getLang, getUser, landingAfterAuth, logout, setDataSaver, setLang, SessionUser } from './auth';
import { t } from './i18n';
import type { Lang } from './types';
import { parseRoute, pathFor } from './routing';
import { applySeo } from './seo';
import Landing from './pages/Landing';
import { captureReferral } from './growth';
import { syncQueuedProgress } from './offlineSync';
const StudentDashboard = lazy(() => import('./pages/StudentDashboard'));
const Courses = lazy(() => import('./pages/Courses'));
const CourseDetail = lazy(() => import('./pages/CourseDetail'));
const LessonPage = lazy(() => import('./pages/LessonPage'));
const Practice = lazy(() => import('./pages/Practice'));
const Materials = lazy(() => import('./pages/Materials'));
const Textbooks = lazy(() => import('./pages/Textbooks'));
const Doubts = lazy(() => import('./pages/Doubts'));
const Downloads = lazy(() => import('./pages/Downloads'));
const ProgressPage = lazy(() => import('./pages/ProgressPage'));
const TeacherDashboard = lazy(() => import('./pages/TeacherDashboard'));
const ParentDashboard = lazy(() => import('./pages/ParentDashboard'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const Studio = lazy(() => import('./pages/Studio'));
const Explore = lazy(() => import('./pages/Explore'));
const TeacherLogin = lazy(() => import('./pages/TeacherLogin'));
const StudentLogin = lazy(() => import('./pages/StudentLogin'));
const AboutPage = lazy(() => import('./pages/Legal').then((m) => ({ default: m.AboutPage })));
const ContactPage = lazy(() => import('./pages/Legal').then((m) => ({ default: m.ContactPage })));
const PrivacyPage = lazy(() => import('./pages/Legal').then((m) => ({ default: m.PrivacyPage })));
const TermsPage = lazy(() => import('./pages/Legal').then((m) => ({ default: m.TermsPage })));
import AuthModal from './AuthModal';
import ApprovalNotice from './ApprovalNotice';
import SiteFooter from './components/SiteFooter';

function initialPath(): string {
  const hash = location.hash;
  if (hash.startsWith('#/')) {
    const path = hash.slice(1) || '/';
    history.replaceState(null, '', path);
    return path;
  }
  return location.pathname;
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(getLang());
  const [user, setUser] = useState<SessionUser | null>(getUser());
  const [route, setRoute] = useState(() => parseRoute(initialPath()));
  const [online, setOnline] = useState(navigator.onLine);
  const [saver, setSaver] = useState(dataSaver());
  const [showAuth, setShowAuth] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [notifCount] = useState(0);

  const navigate = useCallback((path: string, replace = false) => {
    const next = path.startsWith('/') ? path : `/${path}`;
    const current = `${location.pathname}${location.search}`;
    if (next !== current) {
      if (replace) history.replaceState(null, '', next);
      else history.pushState(null, '', next);
    }
    setRoute(parseRoute(next));
    if (!replace) window.scrollTo(0, 0);
  }, []);

  useEffect(() => {
    captureReferral();
    const sync = () => {
      // Old #/course/1 links land here. Replace, don't push, so the legacy
      // URL does not sit in history in front of the canonical path.
      if (location.hash.startsWith('#/')) {
        navigate(location.hash.slice(1) || '/', true);
        return;
      }
      setRoute(parseRoute(location.pathname));
    };
    window.addEventListener('popstate', sync);
    window.addEventListener('hashchange', sync);
    const on = () => { setOnline(true); void syncQueuedProgress().catch(() => {}); };
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('popstate', sync);
      window.removeEventListener('hashchange', sync);
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [navigate]);

  // Keep every same-origin, in-app link a real history navigation. External
  // links, downloads and in-page anchors keep their browser behaviour.
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0
        || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const target = event.target instanceof Element ? event.target : null;
      const anchor = target?.closest('a');
      if (!anchor || anchor.hasAttribute('target') || anchor.hasAttribute('download')) return;
      const href = anchor.getAttribute('href');
      if (!href || !href.startsWith('/') || href.startsWith('//')) return;
      if (href.startsWith('/api/') || href.startsWith('/assets/')) return;
      const url = new URL(anchor.href, location.href);
      if (url.origin !== location.origin) return;
      if (url.pathname === location.pathname && url.search === location.search && url.hash) return;
      if (/\.[a-z0-9]+$/i.test(url.pathname) && !/\.html?$/i.test(url.pathname)) return;
      event.preventDefault();
      setMobileNavOpen(false);
      navigate(`${url.pathname}${url.search}`);
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [navigate]);

  // api.ts clears a dead token on every 401; this also clears the React user
  // so a guarded page redirects to its login instead of showing a signed-in
  // shell full of failed requests.
  useEffect(() => {
    const expired = () => {
      setUser(null);
      setShowAuth(false);
      setMobileNavOpen(false);
    };
    window.addEventListener('gs:session-expired', expired);
    // Child effects run before this one, so a very fast 401 can land before
    // the listener exists. By then api.ts has already cleared storage; read it
    // once here so the shell does not keep a dead user in memory.
    if (!getUser()) setUser(null);
    return () => window.removeEventListener('gs:session-expired', expired);
  }, []);

  useEffect(() => {
    if (user?.role === 'student') void syncQueuedProgress().catch(() => {});
  }, [user?.role]);

  useEffect(() => {
    applySeo(location.pathname);
  }, [route.page, route.sub, route.id]);

  useEffect(() => {
    document.body.classList.toggle('data-saver', saver);
  }, [saver]);

  // Keep the document language in sync with the UI language: screen readers
  // and translation engines read <html lang>, which stayed "en" even when the
  // whole interface was switched to हिंदी or मराठी.
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileNavOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    document.body.classList.add('nav-drawer-open');
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.classList.remove('nav-drawer-open');
    };
  }, [mobileNavOpen]);

  const go = (page: string, id?: number) => {
    navigate(pathFor(page, id));
  };

  const switchLang = (l: Lang) => { setLang(l); setLangState(l); };
  const openAuth = (mode: 'login' | 'register' = 'login') => {
    setAuthMode(mode);
    setShowAuth(true);
  };
  const onAuthed = () => {
    const u = getUser();
    setUser(u);
    setShowAuth(false);
    // Students who just logged in from the landing/login screens open into
    // the e-book library (auth.ts landingAfterAuth); everyone else stays put.
    const landing = landingAfterAuth(u?.role, route.page);
    if (landing) go(landing);
  };
  const refreshSession = () => setUser(getUser());
  const nav = (page: string) => () => go(page);

  const isStudent = user?.role === 'student';
  const isTeacher = user?.role === 'teacher' || user?.role === 'school_admin' || user?.role === 'platform_admin';
  const isParent = user?.role === 'parent';
  const isAdmin = user?.role === 'platform_admin' || user?.role === 'school_admin';

  const authenticated = Boolean(user);
  const isPlatformAdmin = user?.role === 'platform_admin';
  const roleHome = isStudent ? 'dashboard' : isParent ? 'parent' : isPlatformAdmin ? 'admin' : isTeacher ? 'teacher' : 'home';

  // Role-scoped pages must not fire their API calls for the wrong account.
  // A deep link, bookmark, or stale history entry should land on the right
  // dashboard instead of a screen full of 403s.
  const guardedRole: 'student' | 'teacher' | 'admin' | 'parent' | null =
    route.page === 'dashboard' || route.page === 'progress' ? 'student'
      : route.page === 'teacher' ? 'teacher'
        : route.page === 'admin' ? 'admin'
          : route.page === 'parent' ? 'parent'
            : null;
  const canViewGuarded =
    guardedRole === 'student' ? isStudent
      : guardedRole === 'teacher' ? isTeacher
        : guardedRole === 'admin' ? isAdmin
          : guardedRole === 'parent' ? isParent
            : true;
  const loginTarget = guardedRole === 'student' ? 'login/student' : guardedRole === 'teacher' ? 'login/teacher' : 'login';
  const redirectTarget = guardedRole && !canViewGuarded ? (authenticated ? roleHome : loginTarget) : null;

  useEffect(() => {
    if (redirectTarget) {
      const target = pathFor(redirectTarget);
      if (location.pathname !== target) navigate(target, true);
    }
  }, [redirectTarget, navigate]);

  const navItems: [string, string][] = [
    ['home', t('home', lang)],
    ['explore', t('explore', lang)],
    ['materials', t('materials', lang)],
    ['textbooks', t('textbooks', lang)],
    ['practice', t('practice', lang)],
    ['doubts', t('doubts', lang)],
  ];
  if (authenticated) navItems.push(['studio', t('studio', lang)], ['downloads', t('downloads', lang)]);
  const navIcons: Record<string, string> = { home: '⌂', explore: '▦', materials: '▤', textbooks: '▥', practice: '✎', doubts: '?', downloads: '⇩', dashboard: '◉', progress: '↗', teacher: '▣', parent: '♧', admin: '⚙' };
  navIcons.studio = '📚';
  const tabs: [string, string, string][] = [
    ['home', '🏠', t('home', lang)],
    ['explore', '📚', t('explore', lang)],
    ['practice', '✏️', t('practice', lang)],
    ['progress', '📈', t('progress', lang)],
    ['doubts', '❓', t('doubts', lang)],
  ];

  /**
   * A pending or suspended account must never reach a privileged page: the
   * server would 403 every call and the user would see only a generic load
   * error, with no hint that approval is the reason. Show the reason instead.
   */
  const approvalGated = (node: JSX.Element) =>
    user?.role_status && user.role_status !== 'active'
      ? <ApprovalNotice lang={lang} status={user.role_status} onRecheck={refreshSession} />
      : node;

  let page: JSX.Element;
  if (redirectTarget) {
    page = (
      <div className="card empty-state" role="status">
        <div className="icon">🔒</div>
        <p>{authenticated ? 'Taking you to your dashboard…' : t('privateDownloadsLogin', lang)}</p>
      </div>
    );
  } else {
    switch (route.page) {
      case 'login':
        page = route.sub === 'teacher'
          ? <TeacherLogin lang={lang} go={go} onAuthed={onAuthed}
              onSignup={() => openAuth('register')} />
          : route.sub === 'student'
            ? <StudentLogin lang={lang} go={go} onAuthed={onAuthed}
                onSignup={() => openAuth('register')} />
            : <Landing lang={lang} go={go} onLogin={() => openAuth('login')} />;
        break;
      case 'dashboard': page = <StudentDashboard lang={lang} go={go} />; break;
      case 'studio': page = user
        ? <Studio lang={lang} user={user} />
        : <div className="card empty-state">
            <div className="icon">📚</div>
            <p>Log in to open your Study Studio. Your packs stay on this device.</p>
            <button className="btn" onClick={() => openAuth('login')}>{t('login', lang)}</button>
          </div>;
        break;
      case 'explore':
        page = <Explore lang={lang} go={go} routeGrade={route.id} user={user} />;
        break;
      case 'courses': page = <Courses lang={lang} go={go} />; break;
      case 'course': page = <CourseDetail lang={lang} go={go} courseId={route.id!} />; break;
      case 'lesson': page = <LessonPage lang={lang} go={go} lessonId={route.id!} />; break;
      case 'practice': page = <Practice lang={lang} />; break;
      case 'materials': page = <Materials lang={lang} user={user} />; break;
      case 'textbooks': page = <Textbooks lang={lang} user={user} />; break;
      case 'doubts': page = <Doubts lang={lang} user={user} />; break;
      case 'downloads': page = user
        ? <Downloads lang={lang} go={go} />
        : <div className="card empty-state"><div className="icon">🔒</div><p>{t('privateDownloadsLogin', lang)}</p><button className="btn" onClick={() => openAuth('login')}>{t('login', lang)}</button></div>;
        break;
      case 'progress': page = <ProgressPage lang={lang} />; break;
      case 'teacher': page = approvalGated(<TeacherDashboard lang={lang} />); break;
      case 'parent': page = <ParentDashboard lang={lang} />; break;
      case 'admin': page = approvalGated(<AdminDashboard lang={lang} />); break;
      case 'about': page = <AboutPage lang={lang} />; break;
      case 'contact': page = <ContactPage lang={lang} />; break;
      case 'privacy': page = <PrivacyPage lang={lang} />; break;
      case 'terms': page = <TermsPage lang={lang} />; break;
      default: page = user && isStudent
        ? <StudentDashboard lang={lang} go={go} />
        : <Landing lang={lang} go={go} onLogin={() => openAuth('login')} />;
    }
  }

  // Unknown hash routes get a real 404 (with a way home), not a silent
  // landing render — deep links stay honest about where they point.
  const knownPages = ['home', 'login', 'dashboard', 'studio', 'explore', 'courses', 'course',
    'lesson', 'practice', 'materials', 'textbooks', 'doubts', 'downloads',
    'progress', 'teacher', 'parent', 'admin', 'about', 'contact', 'privacy', 'terms'];
  if (!knownPages.includes(route.page)) {
    page = (
      <div className="card" style={{ textAlign: 'center', padding: '48px 20px' }}>
        <div style={{ fontSize: '3rem', fontWeight: 900, color: 'var(--primary)' }}>404</div>
        <h2>Page not found</h2>
        <p className="muted">This link points nowhere on GramShiksha.</p>
        <button className="btn" onClick={nav('home')}>← {t('home', lang)}</button>
      </div>
    );
  }

  const sidebarItems: [string, string][] = authenticated
    ? user?.role === 'student'
      ? [['dashboard', t('todaysLearning', lang)], ['studio', t('studio', lang)], ['explore', t('explore', lang)], ['textbooks', t('textbooks', lang)], ['practice', t('practice', lang)], ['doubts', t('doubts', lang)], ['progress', t('progress', lang)]]
      : [['home', t('home', lang)], ['studio', t('studio', lang)], ['explore', t('explore', lang)], ['materials', t('materials', lang)], ['doubts', t('doubts', lang)], [roleHome, roleHome === 'teacher' ? t('teacher', lang) : roleHome === 'parent' ? t('parent', lang) : 'Admin']]
    : [];

  return (
    <div className={authenticated ? 'app-shell is-authenticated' : 'app-shell'}>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      {!online && <div className="banner-offline" role="status">📴 {t('offlineNote', lang)} <span>Cached lessons remain available.</span></div>}
      {authenticated && mobileNavOpen && <button className="drawer-backdrop" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
      <aside className={`sidebar ${mobileNavOpen ? 'drawer-open' : ''}`} aria-label="Workspace navigation">
        <div className="sidebar-header"><a className="brand sidebar-brand" href="/" onClick={() => setMobileNavOpen(false)}><img className="brand-mark-img" src="/images/gramshiksha-logo-192.png" alt="" width="34" height="34" /><span><strong>GramShiksha</strong><small>Learn. Practice. Grow.</small></span></a><button className="drawer-close" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)}>×</button></div>
        <div className="sidebar-label">Workspace</div>
        <nav className="sidebar-nav">
          {sidebarItems.map(([p, label]) => <a key={p} href={pathFor(p)} onClick={() => setMobileNavOpen(false)} className={route.page === p ? 'active' : ''} aria-current={route.page === p ? 'page' : undefined}><span className="nav-icon">{navIcons[p] ?? '•'}</span>{label}</a>)}
        </nav>
        <div className="sidebar-bottom"><a href="/downloads" onClick={() => setMobileNavOpen(false)}><span className="nav-icon">⇩</span>{t('downloads', lang)}</a><button className="sidebar-logout" onClick={() => { setMobileNavOpen(false); logout(); setUser(null); go('home'); }}><span className="nav-icon">↪</span>{t('logout', lang)}</button></div>
      </aside>
      <div className="app-content">
      <header className="appbar">
        {authenticated && <button className="mobile-menu-toggle" aria-label="Open navigation" aria-expanded={mobileNavOpen} onClick={() => setMobileNavOpen(true)}>☰</button>}
        <a className="brand" href="/">
          <img className="brand-mark-img" src="/images/gramshiksha-logo-192.png" alt="" width="34" height="34" />
          {t('appName', lang)}
        </a>
        <span className="spacer" />
        <button className="btn small" aria-pressed={saver}
          onClick={() => { const v = !saver; setSaver(v); setDataSaver(v); }}>
          📶 {t('dataSaver', lang)}: {saver ? 'ON' : 'OFF'}
        </button>
        <button className="btn small ghost" onClick={() => switchLang(lang === 'en' ? 'hi' : lang === 'hi' ? 'mr' : 'en')}>
          {lang === 'en' ? 'EN' : lang === 'hi' ? 'हिं' : 'मराठी'}
        </button>
        {user ? (
          <>
            <button className="profile-chip" onClick={nav(roleHome)}>
              <span className="avatar">{user.name?.slice(0, 1).toUpperCase() || 'G'}</span><span><strong>{user.name}</strong><small>{user.role === 'student' ? 'Student' : user.role.replace('_', ' ')}</small></span>
            </button>
            <button className="btn small ghost" onClick={() => { logout(); setUser(null); go('home'); }}>
              {t('logout', lang)}
            </button>
          </>
        ) : (
          <button className="btn small" onClick={() => openAuth('login')}>{t('login', lang)}</button>
        )}
      </header>

      <nav className="navbar" aria-label="Main navigation">
        {navItems.map(([p, label]) => (
          <a key={p} href={pathFor(p)} className={route.page === p ? 'active' : ''} aria-current={route.page === p ? 'page' : undefined}>{label}</a>
        ))}
        {isStudent && <a href="/dashboard" className={route.page === 'dashboard' ? 'active' : ''} aria-current={route.page === 'dashboard' ? 'page' : undefined}>{t('todaysLearning', lang)}</a>}
        {isStudent && <a href="/progress" className={route.page === 'progress' ? 'active' : ''} aria-current={route.page === 'progress' ? 'page' : undefined}>{t('progress', lang)}</a>}
        {isTeacher && <a href="/teacher" className={route.page === 'teacher' ? 'active' : ''} aria-current={route.page === 'teacher' ? 'page' : undefined}>{t('teacher', lang)} <span className="nav-role">✦</span></a>}
        {isParent && <a href="/parent" className={route.page === 'parent' ? 'active' : ''} aria-current={route.page === 'parent' ? 'page' : undefined}>{t('parent', lang)} <span className="nav-role">✦</span></a>}
        {isAdmin && <a href="/admin" className={route.page === 'admin' ? 'active' : ''} aria-current={route.page === 'admin' ? 'page' : undefined}>Admin <span className="nav-role">✦</span></a>}
      </nav>

      <main id="main-content" className="container"><Suspense fallback={<div className="route-loading" aria-busy="true"><div className="skeleton skeleton-title" /><div className="skeleton skeleton-panel" /></div>}>{page}</Suspense></main>

      <SiteFooter lang={lang} />

      <nav className="tabbar" aria-label="Quick">
        {tabs.map(([p, ic, label]) => (
          <a key={p} href={pathFor(p)} className={route.page === p ? 'active' : ''} aria-current={route.page === p ? 'page' : undefined}>
            <span className="ic">{ic}</span>{label}
          </a>
        ))}
      </nav>

      {showAuth && <AuthModal lang={lang} initialMode={authMode} onClose={() => setShowAuth(false)} onAuthed={onAuthed} />}
      {notifCount > 0 && <span aria-hidden style={{ display: 'none' }}>{notifCount}</span>}
      </div>
    </div>
  );
}
