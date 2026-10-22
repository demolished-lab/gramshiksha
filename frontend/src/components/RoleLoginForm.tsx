import { useState } from 'react';
import { saveSession } from '../auth';
import { t } from '../i18n';
import type { Lang, LoginResponse } from '../types';

/** Shared email+password form behind both designated login pages. The only
 * thing that differs per role is which api*Login function (and backend
 * endpoint) backs it — the server, not just the UI, enforces the role. */
export default function RoleLoginForm({ lang, title, subtitle, loginFn, onDone, switchHref, switchLabel, onSignup }: {
  lang: Lang;
  title: string;
  subtitle: string;
  loginFn: (email: string, password: string) => Promise<LoginResponse>;
  onDone: () => void;
  switchHref: string;
  switchLabel: string;
  onSignup?: () => void;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true); setErr('');
    try {
      saveSession(await loginFn(email.trim().toLowerCase(), password));
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: 420, margin: '32px auto' }}>
      <h2>{title}</h2>
      <p className="muted">{subtitle}</p>
      <form noValidate onSubmit={(e) => { e.preventDefault(); if (email.trim() && password && !busy) void submit(); }}>
        <label htmlFor="role-login-email">{t('email', lang)}</label>
        <input id="role-login-email" type="email" inputMode="email" value={email}
          onChange={(e) => setEmail(e.target.value)} autoComplete="username"
          autoCapitalize="none" autoCorrect="off" spellCheck={false} required />
        <label htmlFor="role-login-password">{t('password', lang)}</label>
        <input id="role-login-password" type="password" value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password" required />
        {err && <p className="error" role="alert">{err}</p>}
        <div style={{ display: 'flex', gap: 8, marginTop: 14, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn accent" type="submit" disabled={busy || !email.trim() || !password}>
            {t('login', lang)}
          </button>
          <a href={switchHref}>{switchLabel}</a>
          {onSignup && (
            <button type="button" className="auth-forgot" onClick={onSignup}>
              {t('createAccount', lang)}
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
