import { lazy, Suspense, useEffect, useState } from 'react';
import { dataSaver, getLang, getUser, landingAfterAuth, logout, setDataSaver, setLang, SessionUser } from './auth';
import { t } from './i18n';
import type { Lang } from './types';
import Landing from './pages/Landing';
import { captureReferral } from './growth';
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
const Explore = lazy(() => import('./pages/Explore'));
const TeacherLogin = lazy(() => import('./pages/TeacherLogin'));
const StudentLogin = lazy(() => import('./pages/StudentLogin'));
import AuthModal from './AuthModal';
import ApprovalNotice from './ApprovalNotice';

type Route = { page: string; sub?: string; id?: number };

function parseHash(): Route {
  const h = location.hash.replace(/^#\/?/, '');
  const [page, second] = h.split('/');
  // #/login/teacher and #/login/student carry the role in the second slot,
  // where course/lesson carry a numeric id — never mix the two.
  if (page === 'login') return { page, sub: second };
  return { page: page || 'home', id: second ? Number(second) : undefined };
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(getLang());
  const [user, setUser] = useState<SessionUser | null>(getUser());
  const [route, setRoute] = useState<Route>(parseHash());
  const [online, setOnline] = useState(navigator.onLine);
  const [saver, setSaver] = useState(dataSaver());
  const [showAuth, setShowAuth] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [notifCount] = useState(0);

  useEffect(() => {
    captureReferral();
    const onHash = () => setRoute(parseHash());
    window.addEventListener('hashchange', onHash);
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('hashchange', onHash);
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);

  useEffect(() => {
    const pageTitles: Record<string, string> = {
      home: 'Learn without limits', explore: 'Explore courses', courses: 'Courses',
      course: 'Course details', lesson: 'Lesson', practice: 'Practice', materials: 'Study materials',
      textbooks: 'Textbooks', doubts: 'Ask a doubt', downloads: 'My downloads', progress: 'My progress',
      dashboard: 'Today’s learning', teacher: 'Teacher dashboard', parent: 'Parent dashboard', admin: 'Admin dashboard',
      // #/login carries its audience in the sub slot (parseHash) — name it.
      'login.student': 'Student login', 'login.teacher': 'Teacher login', login: 'Log in',
    };
    const key = route.sub ? `${route.page}.${route.sub}` : route.page;
    document.title = `${pageTitles[key] ?? pageTitles[route.page] ?? 'Learn without limits'} · GramShiksha`;
  }, [route.page, route.sub]);

  useEffect(() => {
    document.body.classList.toggle('data-saver', saver);
  }, [saver]);

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
    location.hash = `/${page}${id ? `/${id}` : ''}`;
  };

  const switchLang = (l: Lang) => { setLang(l); setLangState(l); };
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

  const navItems: [string, string][] = [
    ['home', t('home', lang)],
    ['explore', t('explore', lang)],
    ['materials', t('materials', lang)],
    ['textbooks', t('textbooks', lang)],
    ['practice', t('practice', lang)],
    ['doubts', t('doubts', lang)],
    ['downloads', t('downloads', lang)],
  ];
  const navIcons: Record<string, string> = { home: '⌂', explore: '▦', materials: '▤', textbooks: '▥', practice: '✎', doubts: '?', downloads: '⇩', dashboard: '◉', progress: '↗', teacher: '▣', parent: '♧', admin: '⚙' };
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
  switch (route.page) {
    case 'login':
      page = route.sub === 'teacher'
        ? <TeacherLogin lang={lang} go={go} onAuthed={onAuthed} />
        : route.sub === 'student'
          ? <StudentLogin lang={lang} go={go} onAuthed={onAuthed} />
          : <Landing lang={lang} go={go} onLogin={() => setShowAuth(true)} />;
      break;
    case 'dashboard': page = <StudentDashboard lang={lang} go={go} />; break;
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
    case 'downloads': page = <Downloads lang={lang} go={go} />; break;
    case 'progress': page = <ProgressPage lang={lang} />; break;
    case 'teacher': page = approvalGated(<TeacherDashboard lang={lang} />); break;
    case 'parent': page = <ParentDashboard lang={lang} />; break;
    case 'admin': page = approvalGated(<AdminDashboard lang={lang} />); break;
    default: page = user && isStudent
      ? <StudentDashboard lang={lang} go={go} />
      : <Landing lang={lang} go={go} onLogin={() => setShowAuth(true)} />;
  }

  // Unknown hash routes get a real 404 (with a way home), not a silent
  // landing render — deep links stay honest about where they point.
  const knownPages = ['home', 'login', 'dashboard', 'explore', 'courses', 'course',
    'lesson', 'practice', 'materials', 'textbooks', 'doubts', 'downloads',
    'progress', 'teacher', 'parent', 'admin'];
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

  const authenticated = Boolean(user);
  const roleHome = user?.role === 'student' ? 'dashboard' : user?.role === 'parent' ? 'parent' : isTeacher ? 'teacher' : 'admin';
  const sidebarItems: [string, string][] = authenticated
    ? user?.role === 'student'
      ? [['dashboard', t('todaysLearning', lang)], ['explore', t('explore', lang)], ['textbooks', t('textbooks', lang)], ['practice', t('practice', lang)], ['doubts', t('doubts', lang)], ['progress', t('progress', lang)], ['downloads', t('downloads', lang)]]
      : [['home', t('home', lang)], ['explore', t('explore', lang)], ['materials', t('materials', lang)], ['doubts', t('doubts', lang)], [roleHome, roleHome === 'teacher' ? t('teacher', lang) : roleHome === 'parent' ? t('parent', lang) : 'Admin']]
    : [];

  return (
    <div className={authenticated ? 'app-shell is-authenticated' : 'app-shell'}>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      {!online && <div className="banner-offline" role="status">📴 {t('offlineNote', lang)} <span>Cached lessons remain available.</span></div>}
      {authenticated && mobileNavOpen && <button className="drawer-backdrop" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
      <aside className={`sidebar ${mobileNavOpen ? 'drawer-open' : ''}`} aria-label="Workspace navigation">
        <div className="sidebar-header"><a className="brand sidebar-brand" href="#/home" onClick={() => setMobileNavOpen(false)}><span className="brand-mark" aria-hidden="true">G</span><span><strong>GramShiksha</strong><small>Learn. Practice. Grow.</small></span></a><button className="drawer-close" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)}>×</button></div>
        <div className="sidebar-label">Workspace</div>
        <nav className="sidebar-nav">
          {sidebarItems.map(([p, label]) => <a key={p} href={`#/${p}`} onClick={() => setMobileNavOpen(false)} className={route.page === p ? 'active' : ''} aria-current={route.page === p ? 'page' : undefined}><span className="nav-icon">{navIcons[p] ?? '•'}</span>{label}</a>)}
        </nav>
        <div className="sidebar-bottom"><a href="#/downloads" onClick={() => setMobileNavOpen(false)}><span className="nav-icon">⇩</span>{t('downloads', lang)}</a><button className="sidebar-logout" onClick={() => { setMobileNavOpen(false); logout(); setUser(null); go('home'); }}><span className="nav-icon">↪</span>{t('logout', lang)}</button></div>
      </aside>
      <div className="app-content">
      <header className="appbar">
        {authenticated && <button className="mobile-menu-toggle" aria-label="Open navigation" aria-expanded={mobileNavOpen} onClick={() => setMobileNavOpen(true)}>☰</button>}
        <a className="brand" href="#/home">
          <span className="brand-mark" aria-hidden="true">G</span>
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
          <button className="btn small" onClick={() => setShowAuth(true)}>{t('login', lang)}</button>
        )}
      </header>

      <nav className="navbar" aria-label="Main navigation">
        {navItems.map(([p, label]) => (
          <a key={p} href={`#/${p}`} className={route.page === p ? 'active' : ''} aria-current={route.page === p ? 'page' : undefined}>{label}</a>
        ))}
        {isStudent && <a href="#/dashboard" className={route.page === 'dashboard' ? 'active' : ''} aria-current={route.page === 'dashboard' ? 'page' : undefined}>{t('todaysLearning', lang)}</a>}
        {isStudent && <a href="#/progress" className={route.page === 'progress' ? 'active' : ''} aria-current={route.page === 'progress' ? 'page' : undefined}>{t('progress', lang)}</a>}
        {isTeacher && <a href="#/teacher" className={route.page === 'teacher' ? 'active' : ''} aria-current={route.page === 'teacher' ? 'page' : undefined}>{t('teacher', lang)} <span className="nav-role">✦</span></a>}
        {isParent && <a href="#/parent" className={route.page === 'parent' ? 'active' : ''} aria-current={route.page === 'parent' ? 'page' : undefined}>{t('parent', lang)} <span className="nav-role">✦</span></a>}
        {isAdmin && <a href="#/admin" className={route.page === 'admin' ? 'active' : ''} aria-current={route.page === 'admin' ? 'page' : undefined}>Admin <span className="nav-role">✦</span></a>}
      </nav>

      <main id="main-content" className="container"><Suspense fallback={<div className="route-loading" aria-busy="true"><div className="skeleton skeleton-title" /><div className="skeleton skeleton-panel" /></div>}>{page}</Suspense></main>

      <nav className="tabbar" aria-label="Quick">
        {tabs.map(([p, ic, label]) => (
          <a key={p} href={`#/${p}`} className={route.page === p ? 'active' : ''} aria-current={route.page === p ? 'page' : undefined}>
            <span className="ic">{ic}</span>{label}
          </a>
        ))}
      </nav>

      {showAuth && <AuthModal lang={lang} onClose={() => setShowAuth(false)} onAuthed={onAuthed} />}
      {notifCount > 0 && <span aria-hidden style={{ display: 'none' }}>{notifCount}</span>}
      </div>
    </div>
  );
}
