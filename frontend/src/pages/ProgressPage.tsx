import { useEffect, useState } from 'react';
import { apiProgressSummary } from '../api';
import { getToken } from '../auth';
import { t } from '../i18n';
import type { Lang, ProgressSummary } from '../types';

export default function ProgressPage({ lang }: { lang: Lang }) {
  const [s, setS] = useState<ProgressSummary | null>(null);
  const [weekly, setWeekly] = useState<{ date: string; minutes: number }[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) return;
    apiProgressSummary().then(setS).catch((e) => setError(String(e)));
    fetch('/api/progress/weekly', { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((r) => r.json()).then(setWeekly).catch(() => {});
  }, []);

  if (!getToken()) return <div className="empty-state"><p>Log in to see your progress.</p></div>;
  if (error) return <p className="error">{t('errorLoad', lang)}</p>;
  if (!s) return <div><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>;

  const maxMin = Math.max(30, ...weekly.map((w) => w.minutes));

  return (
    <div>
      <div className="page-head"><div><span className="eyebrow eyebrow-muted">Your journey</span><h1>📈 {t('progress', lang)}</h1></div></div>
      <div className="stat-cards">
        <div className="stat-card"><div className="ic" aria-hidden="true">📖</div><div className="num">{s.lessons_completed}</div><div className="lbl">{t('lessonsDone', lang)}</div></div>
        <div className="stat-card"><div className="ic" aria-hidden="true">✏️</div><div className="num">{s.quizzes_taken}</div><div className="lbl">Quizzes</div></div>
        <div className="stat-card"><div className="ic" aria-hidden="true">🎯</div><div className="num">{s.quiz_avg_pct === null ? '—' : `${s.quiz_avg_pct}%`}</div><div className="lbl">{t('quizAvg', lang)}</div></div>
        <div className="stat-card"><div className="ic" aria-hidden="true">🔥</div><div className="num">{s.streak_days}</div><div className="lbl">{t('streak', lang)}</div></div>
      </div>

      <div className="card">
        <h3>Last 14 days (minutes)</h3>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 100 }}>
          {weekly.map((w) => (
            <div key={w.date} title={`${w.date}: ${w.minutes} min`}
              style={{ flex: 1, background: 'var(--primary)', opacity: 0.85, borderRadius: 4,
                       height: `${Math.max(4, (w.minutes / maxMin) * 100)}%` }} />
          ))}
          {!weekly.length && <div className="muted">No activity recorded yet.</div>}
        </div>
      </div>

      <div className="card">
        <h3>🏅 {t('badges', lang)}</h3>
        {s.badges.length === 0 && <p className="muted">{t('empty', lang)}</p>}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {s.badges.map((b) => <span key={b.code} className="badge orange">{b.title_en}</span>)}
        </div>
      </div>

      <div className="card">
        <h3>📜 {t('certificates', lang)}</h3>
        {s.certificates.length === 0 && <p className="muted">Complete a course to earn your first certificate.</p>}
        {!!s.certificates.length && (
          <div className="cert-grid">
            {s.certificates.map((c) => (
              <div className="cert-card" key={c.cert_id}>
                <div className="cert-ic" aria-hidden="true">🏆</div>
                <strong>GS Certificate</strong>
                <div className="muted">{c.cert_id}</div>
                <div className="muted">issued {new Date(c.issued_at).toLocaleDateString()}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
