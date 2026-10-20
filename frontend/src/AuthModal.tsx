import { useEffect, useRef, useState } from 'react';
import { apiLogin, apiRegister } from './api';
import { saveSession } from './auth';
import { clearReferral, getReferral } from './growth';
import { t } from './i18n';
import type { Lang } from './types';

const BOARDS = ['Maharashtra SSC', 'Maharashtra HSC', 'CBSE'];
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function AuthModal({ lang, onClose, onAuthed }: {
  lang: Lang; onClose: () => void; onAuthed: () => void;
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('student');
  const [classGrade, setClassGrade] = useState(8);
  const [board, setBoard] = useState('Maharashtra SSC');
  const [prefLang, setPrefLang] = useState<Lang>(lang);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const cardRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  // A small phone (or a phone with the keyboard open) must be able to scroll
  // the longer sign-up form instead of losing the top fields off-screen.
  // Lock the page behind the dialog so its own scroll is the only one.
  // Also keep keyboard focus inside the modal: without this, Tab walked into
  // the page behind the dimmed overlay, and closing dropped focus on <body>.
  useEffect(() => {
    restoreFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement : null;
    const card = cardRef.current;
    const firstField = card?.querySelector<HTMLElement>(
      'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])');
    const frame = window.requestAnimationFrame(() => (firstField ?? card)?.focus());

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        closeRef.current();
        return;
      }
      if (e.key !== 'Tab' || !card) return;
      const nodes = Array.from(card.querySelectorAll<HTMLElement>(FOCUSABLE))
        .filter((el) => el.getClientRects().length > 0);
      if (!nodes.length) {
        e.preventDefault();
        card.focus();
        return;
      }
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      const outside = !card.contains(active);
      if (e.shiftKey && (active === first || outside)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (active === last || outside)) {
        e.preventDefault();
        first.focus();
      }
    };

    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKey);
    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previous;
      window.removeEventListener('keydown', onKey);
      const opener = restoreFocusRef.current;
      if (opener?.isConnected) opener.focus();
    };
  }, []);

  const submit = async () => {
    setBusy(true); setErr('');
    try {
      if (mode === 'login') {
        saveSession(await apiLogin(email, password));
      } else {
        await apiRegister({
          email, name, password, role, lang_pref: prefLang,
          class_grade: role === 'student' ? classGrade : null, board: role === 'student' ? board : null,
          ref: getReferral(),
        });
        // The captured invite is spent — a second signup on this device must
        // not credit the same referrer again.
        clearReferral();
        saveSession(await apiLogin(email, password));
      }
      onAuthed();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="auth-title">
      <div className="card auth-card" ref={cardRef} tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <h3 id="auth-title">{mode === 'login' ? t('login', lang) : t('register', lang)}</h3>
        {mode === 'register' && (
          <>
            <label>{t('name', lang)}</label>
            <input value={name} onChange={(e) => setName(e.target.value)} />
            <label>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="student">{t('student', lang)}</option>
              <option value="teacher">{t('teacher', lang)}</option>
              <option value="parent">{t('parent', lang)}</option>
            </select>
            {role === 'student' && (
              <>
                <label>{t('classes', lang)}</label>
                <select value={classGrade} onChange={(e) => setClassGrade(Number(e.target.value))}>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((g) => (
                    <option key={g} value={g}>Class {g} / कक्षा {g} / इयत्ता {g}</option>
                  ))}
                </select>
                <label>Board</label>
                <select value={board} onChange={(e) => setBoard(e.target.value)}>
                  {BOARDS.map((b) => <option key={b} value={b}>{b}</option>)}
                </select>
                <label>Language / भाषा / भाषा</label>
                <select value={prefLang} onChange={(e) => setPrefLang(e.target.value as Lang)}>
                  <option value="en">English</option>
                  <option value="hi">हिंदी</option>
                  <option value="mr">मराठी</option>
                </select>
              </>
            )}
          </>
        )}
        <label>{t('email', lang)}</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
        <label>{t('password', lang)}</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
        {err && <p className="error">{err}</p>}
        <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
          <button className="btn" disabled={busy || !email || !password} onClick={submit}>
            {mode === 'login' ? t('login', lang) : t('register', lang)}
          </button>
          <button className="btn ghost" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
            {mode === 'login' ? t('register', lang) : t('login', lang)}
          </button>
          <span style={{ flex: 1 }} />
          <button className="btn ghost small" onClick={onClose} aria-label="Close">✕</button>
        </div>
      </div>
    </div>
  );
}
