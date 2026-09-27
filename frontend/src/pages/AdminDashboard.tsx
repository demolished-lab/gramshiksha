import { useEffect, useState } from 'react';
import { apiSchoolStats, apiSearch } from '../api';
import { getToken } from '../auth';
import { t } from '../i18n';
import type { Lang } from '../types';

interface AdminUser { id: number; email: string; name: string; role: string; class_grade: number | null; xp: number }

export default function AdminDashboard({ lang }: { lang: Lang }) {
  const [stats, setStats] = useState<{ students: number; teachers: number; lessons_completed_total: number } | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    apiSchoolStats().then(setStats).catch(() => {});
    fetch('/api/admin/users?limit=100', { headers: { Authorization: `Bearer ${getToken() ?? ''}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('Admin access required'))))
      .then(setUsers)
      .catch((e) => setError(String(e)));
    void apiSearch;
  }, []);

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
      <h1>🛠 Admin</h1>
      {stats && (
        <div className="stat-row">
          <div className="stat"><div className="num">{stats.students}</div><div className="lbl">{t('students', lang)}</div></div>
          <div className="stat"><div className="num">{stats.teachers}</div><div className="lbl">{t('teacher', lang)}</div></div>
          <div className="stat"><div className="num">{stats.lessons_completed_total}</div><div className="lbl">{t('lessonsDone', lang)}</div></div>
        </div>
      )}

      <button className="btn accent" style={{ margin: '12px 0' }} onClick={announce}>📣 School announcement</button>

      {error && <p className="error">{error}</p>}
      <div className="card">
        <h3>{t('students', lang)} & staff</h3>
        <table>
          <thead><tr><th>{t('name', lang)}</th><th>Role</th><th>Class</th><th>{t('xp', lang)}</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.name}<div className="muted">{u.email}</div></td>
                <td><span className="badge gray">{u.role}</span></td>
                <td>{u.class_grade ?? '—'}</td>
                <td>{u.xp}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!users.length && !error && <p className="muted">{t('loading', lang)}</p>}
      </div>
    </div>
  );
}
