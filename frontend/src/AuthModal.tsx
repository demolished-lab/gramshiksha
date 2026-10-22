import { useEffect, useRef, useState } from 'react';
import { apiLogin, apiRegister, apiResetConfirm, apiResetRequest } from './api';
import { saveSession } from './auth';
import { clearReferral, getReferral } from './growth';
import { t } from './i18n';
import type { Lang } from './types';

const BOARDS = ['Maharashtra SSC', 'Maharashtra HSC', 'CBSE'];
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
type AuthMode = 'login' | 'register' | 'reset-request' | 'reset-confirm';

export default function AuthModal({ lang, initialMode = 'login', onClose, onAuthed }: {
  lang: Lang; initialMode?: 'login' | 'register'; onClose: () => void; onAuthed: () => void;
}) {
  const [mode, setMode] = useState<AuthMode>(initialMode);
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

  // Parent may open the same mounted dialog in a different mode (for example
  // "Create account" from a designated login page). Keep the form in sync.
  useEffect(() => {
    setMode(initialMode);
    setErr('');
    setNotice('');
  }, [initialMode]);

  // After "Send code", move straight to the code field instead of leaving
  // focus on a button that has just changed its meaning.
  useEffect(() => {
    if (mode === 'reset-confirm') {
      cardRef.current?.querySelector<HTMLInputElement>('input[autocomplete="one-time-code"]')?.focus();
    } else {
      cardRef.current?.querySelector<HTMLElement>('input:not([disabled]), select:not([disabled])')?.focus();
    }
  }, [mode]);

  // On a phone the error can be just below the keyboard. Bring it back into
  // view instead of leaving the learner staring at a disabled button.
  useEffect(() => {
    if (err) cardRef.current?.querySelector('[role="alert"]')?.scrollIntoView({ block: 'nearest' });
  }, [err]);

  const changeMode = (next: AuthMode) => {
    setMode(next);
    setErr('');
    setNotice('');
  };

  const cleanEmail = email.trim().toLowerCase();
  const cleanName = name.trim();
  const emailLooksValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail);
  const showEmailError = Boolean(email.trim()) && !emailLooksValid;
  const canSubmit = !busy && emailLooksValid && (
    mode === 'login' ? password.length > 0
      : mode === 'register' ? cleanName.length > 0 && password.length >= 8
        : mode === 'reset-request' ? true
          : resetCode.length === 6 && newPassword.length >= 8
  );

  const submit = async () => {
    if (!emailLooksValid) {
      setErr(t('emailInvalid', lang));
      return;
    }
    if (mode === 'register' && !cleanName) {
      setErr(t('nameRequired', lang));
      return;
    }
    if (mode === 'register' && password.length < 8) {
      setErr(t('passwordTooShort', lang));
      return;
    }
    setBusy(true); setErr(''); setNotice('');
    try {
      if (mode === 'login') {
        saveSession(await apiLogin(cleanEmail, password));
        onAuthed();
      } else if (mode === 'register') {
        // Register now returns the same session shape as login, so a mobile
        // user enters the app even if the network drops between the two old
        // requests. The backend also lowercases the address: a keyboard that
        // auto-capitalises it can no longer strand the new account.
        saveSession(await apiRegister({
          email: cleanEmail, name: cleanName, password, role, lang_pref: prefLang,
          class_grade: role === 'student' ? classGrade : null,
          board: role === 'student' ? board : null,
          ref: getReferral(),
        }));
        // The captured invite is spent — a second signup on this device must
        // not credit the same referrer again.
        clearReferral();
        onAuthed();
      } else if (mode === 'reset-request') {
        await apiResetRequest(cleanEmail);
        setMode('reset-confirm');
        setNotice(t('resetSent', lang));
      } else {
        await apiResetConfirm(cleanEmail, resetCode.trim(), newPassword);
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
        <form noValidate onSubmit={(e) => { e.preventDefault(); if (canSubmit) void submit(); }}>
          {notice && <p className="success" role="status">{notice}</p>}
          {mode === 'register' && (
            <>
              <label htmlFor="auth-name">{t('name', lang)}</label>
              <input id="auth-name" value={name} onChange={(e) => setName(e.target.value)}
                autoComplete="name" required />
              <label htmlFor="auth-role">Role</label>
              <select id="auth-role" value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="student">{t('student', lang)}</option>
                <option value="teacher">{t('teacher', lang)}</option>
                <option value="parent">{t('parent', lang)}</option>
              </select>
              {role === 'student' && (
                <>
                  <label htmlFor="auth-class">{t('classes', lang)}</label>
                  <select id="auth-class" value={classGrade} onChange={(e) => setClassGrade(Number(e.target.value))}>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((g) => (
                      <option key={g} value={g}>Class {g} / कक्षा {g} / इयत्ता {g}</option>
                    ))}
                  </select>
                  <label htmlFor="auth-board">Board</label>
                  <select id="auth-board" value={board} onChange={(e) => setBoard(e.target.value)}>
                    {BOARDS.map((b) => <option key={b} value={b}>{b}</option>)}
                  </select>
                  <label htmlFor="auth-lang">Language / भाषा / भाषा</label>
                  <select id="auth-lang" value={prefLang} onChange={(e) => setPrefLang(e.target.value as Lang)}>
                    <option value="en">English</option>
                    <option value="hi">हिंदी</option>
                    <option value="mr">मराठी</option>
                  </select>
                </>
              )}
            </>
          )}
          <label htmlFor="auth-email">{t('email', lang)}</label>
          <input id="auth-email" type="email" inputMode="email" value={email}
            onChange={(e) => setEmail(e.target.value)} autoComplete="username"
            autoCapitalize="none" autoCorrect="off" spellCheck={false}
            aria-invalid={showEmailError} aria-describedby={showEmailError ? 'auth-email-error' : undefined}
            required />
          {showEmailError && (
            <p id="auth-email-error" className="error" role="alert">{t('emailInvalid', lang)}</p>
          )}
          {(mode === 'login' || mode === 'register') && (
            <>
              <label htmlFor="auth-password">{t('password', lang)}</label>
              <input id="auth-password" type="password" value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                minLength={mode === 'register' ? 8 : undefined}
                aria-describedby={mode === 'register' ? 'auth-password-hint auth-error' : 'auth-error'}
                required />
              {mode === 'register' && (
                <p id="auth-password-hint" className="muted" style={{ margin: '4px 0 0', fontSize: '.78rem' }}>
                  {t('passwordHint', lang)}
                </p>
              )}
            </>
          )}
          {mode === 'reset-confirm' && (
            <>
              <label htmlFor="reset-code">{t('resetCode', lang)}</label>
              <input id="reset-code" type="text" inputMode="numeric" pattern="[0-9]*" maxLength={6}
                value={resetCode} onChange={(e) => setResetCode(e.target.value.replace(/\D/g, ''))}
                autoComplete="one-time-code" required />
              <label htmlFor="reset-new-password">{t('newPassword', lang)}</label>
              <input id="reset-new-password" type="password" value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)} minLength={8}
                autoComplete="new-password" required />
            </>
          )}
          {mode === 'login' && (
            <button type="button" className="auth-forgot" onClick={() => changeMode('reset-request')}>
              {t('forgotPassword', lang)}
            </button>
          )}
          {err && <p id="auth-error" className="error" role="alert">{err}</p>}
          <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
            <button className="btn" type="submit" disabled={!canSubmit} aria-busy={busy}>
              {mode === 'login' ? t('login', lang)
                : mode === 'register' ? t('register', lang)
                  : mode === 'reset-request' ? t('sendCode', lang) : t('updatePassword', lang)}
            </button>
            {mode === 'login' && (
              <button type="button" className="btn ghost" onClick={() => changeMode('register')}>
                {t('register', lang)}
              </button>
            )}
            {mode !== 'login' && (
              <button type="button" className="btn ghost" onClick={() => changeMode('login')}>
                {t('backToLogin', lang)}
              </button>
            )}
            <span style={{ flex: 1 }} />
            <button type="button" className="btn ghost small" onClick={onClose} aria-label="Close">✕</button>
          </div>
        </form>
      </div>
    </div>
  );
}
