import { useEffect, useState, type FormEvent } from 'react';
import { apiAcceptParentInvite, apiParentChildren } from '../api';
import { t } from '../i18n';
import type { Lang, ParentChild } from '../types';

export default function ParentDashboard({ lang }: { lang: Lang }) {
  const [children, setChildren] = useState<ParentChild[]>([]);
  const [error, setError] = useState('');
  const [invite, setInvite] = useState('');
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState('');

  const load = () => apiParentChildren().then(setChildren).catch((e) => setError(String(e)));
  useEffect(() => { void load(); }, []);

  const acceptInvite = async (event: FormEvent) => {
    event.preventDefault();
    if (!invite.trim()) return;
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const result = await apiAcceptParentInvite(invite.trim());
      setInvite('');
      setSuccess(`${t('parentLinked', lang)} ${result.child}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div>
      <h1>👪 {t('parent', lang)}</h1>
      {error && <p className="error" role="alert">{t('errorLoad', lang)} {error}</p>}
      {success && <p className="success" role="status">{success}</p>}
      {!children.length && !error && <div className="empty-state"><div className="icon">👪</div><p>{t('parentNoChild', lang)}</p></div>}

      <div className="card">
        <h2>{t('linkStudentTitle', lang)}</h2>
        <p className="muted">{t('linkStudentHint', lang)}</p>
        <form onSubmit={acceptInvite}>
          <label htmlFor="parent-invite">{t('parentInviteLabel', lang)}</label>
          <textarea id="parent-invite" value={invite} onChange={(e) => setInvite(e.target.value)} rows={3} required autoComplete="off" />
          <button className="btn" type="submit" disabled={busy || !invite.trim()}>{busy ? t('checking', lang) : t('acceptParentInvite', lang)}</button>
        </form>
      </div>

      {children.map((c) => (
        <div className="card" key={c.id}>
          <h3>👦 {c.name} — {t('classNumber', lang).replace('{n}', String(c.class_grade))} ({c.board})</h3>
          <div className="stat-row" style={{ marginBottom: 10 }}>
            <div className="stat"><div className="num">{c.lessons_completed}</div><div className="lbl">{t('lessonsDone', lang)}</div></div>
            <div className="stat"><div className="num">{Math.floor(c.week_minutes / 60)}h {c.week_minutes % 60}m</div><div className="lbl">{t('studyTime', lang)} / week</div></div>
            <div className="stat"><div className="num">{c.quiz_avg_pct === null ? '—' : `${c.quiz_avg_pct}%`}</div><div className="lbl">{t('quizAvg', lang)}</div></div>
            <div className="stat"><div className="num">🔥 {c.streak_days}</div><div className="lbl">{t('streak', lang)}</div></div>
            <div className="stat"><div className="num">{c.badges}</div><div className="lbl">{t('badges', lang)}</div></div>
            <div className="stat"><div className="num">{c.certificates}</div><div className="lbl">{t('certificates', lang)}</div></div>
          </div>
          {c.weak_subjects.length > 0 && <p><span className="badge orange">{t('needHelp', lang)}: {c.weak_subjects.join(', ')}</span></p>}
        </div>
      ))}
    </div>
  );
}
