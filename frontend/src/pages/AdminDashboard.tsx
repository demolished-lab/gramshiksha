import { useEffect, useState } from 'react';
import {
  AdminUser, apiAdminUsers, apiApproveUser, apiSchoolStats, apiSearch, apiSuspendUser,
} from '../api';
import { getToken } from '../auth';
import { t } from '../i18n';
import type { Lang, RoleStatus } from '../types';

const statusKey = (s: RoleStatus) =>
  s === 'pending' ? 'statusPending' : s === 'suspended' ? 'statusSuspended' : 'statusActive';
const statusBadge = (s: RoleStatus) =>
  s === 'active' ? 'green' : s === 'pending' ? 'orange' : 'gray';
const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** Only staff ever hold a non-active status; students and parents always are
 * `active`, so action buttons on their rows would just invite an accidental
 * suspension of somebody who has nothing to approve. */
const isStaff = (role: string) =>
  role === 'teacher' || role === 'school_admin' || role === 'platform_admin';

export default function AdminDashboard({ lang }: { lang: Lang }) {
  const [stats, setStats] = useState<{ students: number; teachers: number; lessons_completed_total: number } | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () => {
    // Real server detail, not a hardcoded "Admin access required": when the
    // API refuses (403/400), that message is the only explanation available.
    apiAdminUsers(100).then(setUsers).catch((e) => setError(errText(e)));
  };

  useEffect(() => {
    apiSchoolStats().then(setStats).catch(() => {});
    load();
    void apiSearch;
  }, []);

  const setStatus = async (id: number, action: 'approve' | 'suspend') => {
    setBusy(true);
    setError('');
    try {
      await (action === 'approve' ? apiApproveUser(id) : apiSuspendUser(id));
      load(); // refetch so the badge reflects the server, not our assumption
    } catch (e) {
      setError(errText(e)); // e.g. "Cannot change your own approval status"
    } finally {
      setBusy(false);
    }
  };

  const announce = async () => {
    const title = prompt('Announcement title:');
    if (!title) return;
    await fetch(`/api/school/announce?title=${encodeURIComponent(title)}`, {
      method: 'POST', headers: { Authorization: `Bearer ${getToken() ?? ''}` },
    });
    alert('Announcement sent to all students ✓');
  };

  return (
    <div>
      <div className="page-head"><div><span className="eyebrow eyebrow-muted">Administration</span><h1>🛠 Admin</h1></div></div>
      {stats && (
        <div className="stat-cards">
          <div className="stat-card"><div className="ic" aria-hidden="true">👥</div><div className="num">{stats.students}</div><div className="lbl">{t('students', lang)}</div></div>
          <div className="stat-card"><div className="ic" aria-hidden="true">👩‍🏫</div><div className="num">{stats.teachers}</div><div className="lbl">{t('teacher', lang)}</div></div>
          <div className="stat-card"><div className="ic" aria-hidden="true">📖</div><div className="num">{stats.lessons_completed_total}</div><div className="lbl">{t('lessonsDone', lang)}</div></div>
        </div>
      )}

      <button className="btn accent" style={{ margin: '12px 0' }} onClick={announce}>📣 School announcement</button>

      {error && <p className="error">{error}</p>}
      <div className="card">
        <h3>{t('students', lang)} & staff</h3>
        <table>
          <thead>
            <tr>
              <th>{t('name', lang)}</th><th>Role</th><th>{t('status', lang)}</th>
              <th>Class</th><th>{t('xp', lang)}</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.name}<div className="muted">{u.email}</div></td>
                <td><span className="badge gray">{u.role}</span></td>
                <td><span className={`badge ${statusBadge(u.role_status)}`}>{t(statusKey(u.role_status), lang)}</span></td>
                <td>{u.class_grade ?? '—'}</td>
                <td>{u.xp}</td>
                <td>
                  {isStaff(u.role) && (u.role_status === 'active'
                    ? (
                      <button className="btn small ghost" disabled={busy}
                        onClick={() => setStatus(u.id, 'suspend')}>
                        ⛔ {t('suspend', lang)}
                      </button>
                    )
                    : (
                      <button className="btn small" disabled={busy}
                        onClick={() => setStatus(u.id, 'approve')}>
                        ✓ {t('approve', lang)}
                      </button>
                    ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!users.length && !error && <p className="muted">{t('loading', lang)}</p>}
      </div>
    </div>
  );
}
