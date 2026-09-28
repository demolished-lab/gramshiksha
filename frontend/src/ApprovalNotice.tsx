import { useState } from 'react';
import { apiMe } from './api';
import { refreshUser } from './auth';
import { t } from './i18n';
import type { Lang, RoleStatus } from './types';

/**
 * What a `pending` or `suspended` account sees instead of the teacher/admin
 * dashboard. Without it the dashboard only 403s, and the user is left with a
 * generic load error and no idea why their account does nothing.
 *
 * A pending teacher sits on this screen while an admin approves them, so the
 * re-check button re-reads `/auth/me` — approval must become visible without
 * logging out. A suspended account gets no button: only an admin can change
 * that state, so re-checking could never succeed.
 */
export default function ApprovalNotice({ lang, status, onRecheck }: {
  lang: Lang;
  status: RoleStatus;
  onRecheck: () => void;
}) {
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState('');

  const recheck = async () => {
    setChecking(true);
    setError('');
    try {
      refreshUser(await apiMe());
      onRecheck();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  };

  const suspended = status === 'suspended';
  return (
    <div className="card" role="status" aria-live="polite">
      <h2>{t(suspended ? 'suspendedTitle' : 'pendingTitle', lang)}</h2>
      <p>{t(suspended ? 'suspendedBody' : 'pendingBody', lang)}</p>
      {!suspended && (
        <button className="btn accent" onClick={recheck} disabled={checking}>
          {checking ? t('checking', lang) : t('checkStatus', lang)}
        </button>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
