import { useState } from 'react';
import { saveSession } from '../auth';
import { t } from '../i18n';
import type { Lang, LoginResponse } from '../types';

/** Shared email+password form behind both designated login pages. The only
 * thing that differs per role is which api*Login function (and backend
 * endpoint) backs it — the server, not just the UI, enforces the role. */
export default function RoleLoginForm({ lang, title, subtitle, loginFn, onDone, switchHref, switchLabel }: {
  lang: Lang;
  title: string;
  subtitle: string;
  loginFn: (email: string, password: string) => Promise<LoginResponse>;
  onDone: () => void;
  switchHref: string;
  switchLabel: string;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true); setErr('');
    try {
      saveSession(await loginFn(email, password));
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
      <label>{t('email', lang)}</label>
      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
        autoComplete="username" />
      <label>{t('password', lang)}</label>
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
        autoComplete="current-password"
        onKeyDown={(e) => { if (e.key === 'Enter' && email && password && !busy) void submit(); }} />
      {err && <p className="error">{err}</p>}
      <div style={{ display: 'flex', gap: 8, marginTop: 14, alignItems: 'center' }}>
        <button className="btn accent" disabled={busy || !email || !password} onClick={() => void submit()}>
          {t('login', lang)}
        </button>
        <a href={switchHref}>{switchLabel}</a>
      </div>
    </div>
  );
}
