import { useEffect, useState } from 'react';
import { dataSaver, getLang, getUser, logout, setDataSaver, setLang, SessionUser } from './auth';
import { t } from './i18n';
import type { Lang } from './types';
import Landing from './pages/Landing';
import StudentDashboard from './pages/StudentDashboard';
import Courses from './pages/Courses';
import CourseDetail from './pages/CourseDetail';
import LessonPage from './pages/LessonPage';
import Practice from './pages/Practice';
import Materials from './pages/Materials';
import Textbooks from './pages/Textbooks';
import Doubts from './pages/Doubts';
import Downloads from './pages/Downloads';
import ProgressPage from './pages/ProgressPage';
import TeacherDashboard from './pages/TeacherDashboard';
import ParentDashboard from './pages/ParentDashboard';
import AdminDashboard from './pages/AdminDashboard';
import AuthModal from './AuthModal';
import ApprovalNotice from './ApprovalNotice';

type Route = { page: string; id?: number };

function parseHash(): Route {
  const h = location.hash.replace(/^#\/?/, '');
  const [page, idStr] = h.split('/');
  return { page: page || 'home', id: idStr ? Number(idStr) : undefined };
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(getLang());
  const [user, setUser] = useState<SessionUser | null>(getUser());
  const [route, setRoute] = useState<Route>(parseHash());
  const [online, setOnline] = useState(navigator.onLine);
  const [saver, setSaver] = useState(dataSaver());
  const [showAuth, setShowAuth] = useState(false);
  const [notifCount] = useState(0);

  useEffect(() => {
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
    document.body.classList.toggle('data-saver', saver);
  }, [saver]);

  const go = (page: string, id?: number) => {
    location.hash = `/${page}${id ? `/${id}` : ''}`;
  };

  const switchLang = (l: Lang) => { setLang(l); setLangState(l); };
  const onAuthed = () => { setUser(getUser()); setShowAuth(false); };
  const refreshSession = () => setUser(getUser());
  const nav = (page: string) => () => go(page);

  const isStudent = user?.role === 'student';
  const isTeacher = user?.role === 'teacher' || user?.role === 'school_admin' || user?.role === 'platform_admin';
  const isParent = user?.role === 'parent';
  const isAdmin = user?.role === 'platform_admin' || user?.role === 'school_admin';

  const navItems: [string, string][] = [
    ['home', t('home', lang)],
    ['courses', t('courses', lang)],
    ['materials', t('materials', lang)],
    ['textbooks', t('textbooks', lang)],
    ['practice', t('practice', lang)],
    ['doubts', t('doubts', lang)],
    ['downloads', t('downloads', lang)],
  ];
  const tabs: [string, string, string][] = [
    ['home', '🏠', t('home', lang)],
    ['courses', '📚', t('courses', lang)],
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
    case 'dashboard': page = <StudentDashboard lang={lang} go={go} />; break;
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

  return (
    <>
      {!online && <div className="banner-offline">📴 {t('offlineNote', lang)}</div>}
      <header className="appbar">
        <span className="brand" style={{ cursor: 'pointer' }} onClick={nav('home')}>
          {t('appName', lang)}
        </span>
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
            <button className="btn small ghost" onClick={nav(user.role === 'student' ? 'dashboard' : user.role === 'parent' ? 'parent' : isTeacher ? 'teacher' : 'admin')}>
              {user.name}
            </button>
            <button className="btn small ghost" onClick={() => { logout(); setUser(null); go('home'); }}>
              {t('logout', lang)}
            </button>
          </>
        ) : (
          <button className="btn small" onClick={() => setShowAuth(true)}>{t('login', lang)}</button>
        )}
      </header>

      <nav className="navbar" aria-label="Main">
        {navItems.map(([p, label]) => (
          <a key={p} href={`#/${p}`} className={route.page === p ? 'active' : ''}>{label}</a>
        ))}
        {isStudent && <a href="#/dashboard" className={route.page === 'dashboard' ? 'active' : ''}>{t('todaysLearning', lang)}</a>}
        {isStudent && <a href="#/progress" className={route.page === 'progress' ? 'active' : ''}>{t('progress', lang)}</a>}
        {isTeacher && <a href="#/teacher" className={route.page === 'teacher' ? 'active' : ''}>{t('teacher', lang)} ✦</a>}
        {isParent && <a href="#/parent" className={route.page === 'parent' ? 'active' : ''}>{t('parent', lang)} ✦</a>}
        {isAdmin && <a href="#/admin" className={route.page === 'admin' ? 'active' : ''}>Admin ✦</a>}
      </nav>

      <main className="container">{page}</main>

      <nav className="tabbar" aria-label="Quick">
        {tabs.map(([p, ic, label]) => (
          <a key={p} href={`#/${p}`} className={route.page === p ? 'active' : ''}>
            <span className="ic">{ic}</span>{label}
          </a>
        ))}
      </nav>

      {showAuth && <AuthModal lang={lang} onClose={() => setShowAuth(false)} onAuthed={onAuthed} />}
      {notifCount > 0 && <span aria-hidden style={{ display: 'none' }}>{notifCount}</span>}
    </>
  );
}
