import { useEffect, useRef, useState } from 'react';
import { apiLogin, apiRegister, apiResetConfirm, apiResetRequest } from './api';
import { saveSession } from './auth';
import { clearReferral, getReferral } from './growth';
import { t } from './i18n';
import type { Lang } from './types';

const BOARDS = ['Maharashtra SSC', 'Maharashtra HSC', 'CBSE'];
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
type AuthMode = 'login' | 'register' | 'reset-request' | 'reset-confirm';

export default function AuthModal({ lang, onClose, onAuthed }: {
  lang: Lang; onClose: () => void; onAuthed: () => void;
}) {
  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('student');
  const [classGrade, setClassGrade] = useState(8);
  const [board, setBoard] = useState('Maharashtra SSC');
  const [prefLang, setPrefLang] = useState<Lang>(lang);
  const [resetCode, setResetCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [err, setErr] = useState('');
  const [notice, setNotice] = useState('');
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

  // After "Send code", move straight to the code field instead of leaving
  // focus on a button that has just changed its meaning.
  useEffect(() => {
    if (mode === 'reset-confirm') {
      cardRef.current?.querySelector<HTMLInputElement>('input[autocomplete="one-time-code"]')?.focus();
    }
  }, [mode]);

  const changeMode = (next: AuthMode) => {
    setMode(next);
    setErr('');
    setNotice('');
  };

  const submit = async () => {
    setBusy(true); setErr(''); setNotice('');
    try {
      if (mode === 'login') {
        saveSession(await apiLogin(email, password));
        onAuthed();
      } else if (mode === 'register') {
        await apiRegister({
          email, name, password, role, lang_pref: prefLang,
          class_grade: role === 'student' ? classGrade : null, board: role === 'student' ? board : null,
          ref: getReferral(),
        });
        // The captured invite is spent — a second signup on this device must
        // not credit the same referrer again.
        clearReferral();
        saveSession(await apiLogin(email, password));
        onAuthed();
      } else if (mode === 'reset-request') {
        await apiResetRequest(email.trim());
        setMode('reset-confirm');
        setNotice(t('resetSent', lang));
      } else {
        await apiResetConfirm(email.trim(), resetCode.trim(), newPassword);
        setMode('login');
        setPassword('');
        setResetCode('');
        setNewPassword('');
        setNotice(t('resetDone', lang));
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="auth-title">
      <div className="card auth-card" ref={cardRef} tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <h3 id="auth-title">{mode === 'login' ? t('login', lang)
          : mode === 'register' ? t('register', lang) : t('resetPassword', lang)}</h3>
        {notice && <p className="success" role="status">{notice}</p>}
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
        {(mode === 'login' || mode === 'register') && (
          <>
            <label>{t('password', lang)}</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
          </>
        )}
        {mode === 'reset-confirm' && (
          <>
            <label htmlFor="reset-code">{t('resetCode', lang)}</label>
            <input id="reset-code" type="text" inputMode="numeric" pattern="[0-9]*" maxLength={6}
              value={resetCode} onChange={(e) => setResetCode(e.target.value.replace(/\D/g, ''))}
              autoComplete="one-time-code" />
            <label htmlFor="reset-new-password">{t('newPassword', lang)}</label>
            <input id="reset-new-password" type="password" value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)} minLength={8}
              autoComplete="new-password" />
          </>
        )}
        {mode === 'login' && (
          <button type="button" className="auth-forgot" onClick={() => changeMode('reset-request')}>
            {t('forgotPassword', lang)}
          </button>
        )}
        {err && <p className="error" role="alert">{err}</p>}
        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          <button className="btn" disabled={busy || !email
            || ((mode === 'login' || mode === 'register') && !password)
            || (mode === 'reset-confirm' && (resetCode.length !== 6 || newPassword.length < 8))}
            onClick={submit}>
            {mode === 'login' ? t('login', lang)
              : mode === 'register' ? t('register', lang)
                : mode === 'reset-request' ? t('sendCode', lang) : t('updatePassword', lang)}
          </button>
          {mode === 'login' && (
            <button className="btn ghost" onClick={() => changeMode('register')}>
              {t('register', lang)}
            </button>
          )}
          {mode !== 'login' && (
            <button className="btn ghost" onClick={() => changeMode('login')}>
              {t('backToLogin', lang)}
            </button>
          )}
          <span style={{ flex: 1 }} />
          <button className="btn ghost small" onClick={onClose} aria-label="Close">✕</button>
        </div>
      </div>
    </div>
  );
}
