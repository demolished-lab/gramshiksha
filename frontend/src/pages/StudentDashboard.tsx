import { useEffect, useState } from 'react';
import { apiMyCourses, apiNotifications, apiProgressSummary, apiToday, apiWeakTopics } from '../api';
import { getToken } from '../auth';
import { t } from '../i18n';
import type { Lang, TodayPlan, WeakTopics, ProgressSummary, Notification } from '../types';

export default function StudentDashboard({ lang, go }: { lang: Lang; go: (p: string, id?: number) => void }) {
  const [today, setToday] = useState<TodayPlan | null>(null);
  const [weak, setWeak] = useState<WeakTopics | null>(null);
  const [summary, setSummary] = useState<ProgressSummary | null>(null);
  const [courses, setCourses] = useState<{ id: number; title_en: string; progress_pct: number }[]>([]);
  const [notifs, setNotifs] = useState<Notification[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!getToken()) { go('home'); return; }
    (async () => {
      try {
        const [td, wk, sm, mc, nf] = await Promise.all([
          apiToday(lang), apiWeakTopics(), apiProgressSummary(), apiMyCourses(), apiNotifications(),
        ]);
        setToday(td); setWeak(wk); setSummary(sm); setCourses(mc); setNotifs(nf.filter((n) => !n.read));
      } catch (e) {
        setError(String(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  if (!getToken()) return null;
  if (error) return <p className="error">{t('errorLoad', lang)} — {error}</p>;
  if (!today) return <div><div className="skeleton" style={{ width: '60%' }} /><div className="skeleton" /><div className="skeleton" style={{ width: '80%' }} /></div>;

  const user = JSON.parse(localStorage.getItem('gs_user') || '{}');

  return (
    <div>
      <h1>👋 {user.name}</h1>
      <p className="muted">{t('todaysLearning', lang)} · 🔥 {today.streak_days} {t('streak', lang)} · ⚡ {today.xp} {t('xp', lang)}</p>

      {notifs.length > 0 && (
        <div className="card" style={{ borderLeft: '4px solid var(--accent)' }}>
          <strong>🔔 {notifs.length}</strong>
          <div className="muted">{String(notifs[0].payload.title ?? notifs[0].payload.badge ?? notifs[0].type)}</div>
        </div>
      )}

      <div className="card">
        <h3>📅 {t('todaysLearning', lang)}</h3>
        {today.items.length === 0 && <p className="muted">{t('empty', lang)}</p>}
        {today.items.map((item) => (
          <div key={item.slot} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 22 }}>{item.kind === 'lesson' ? '📖' : item.kind === 'practice_quiz' ? '✏️' : '🔁'}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{item.label}</div>
              {item.minutes && <div className="muted">{item.minutes} min</div>}
            </div>
            <button className="btn small" onClick={() =>
              item.kind === 'lesson' ? go('lesson', item.lesson_id)
                : item.kind === 'practice_quiz' ? go('practice') : go('practice')}>
              {t('continue', lang)}
            </button>
          </div>
        ))}
        <p className="muted" style={{ marginBottom: 0 }}>⏱️ {t('studyTime', lang)}: {today.study_minutes_today} min</p>
      </div>

      {weak && weak.weak.length > 0 && (
        <div className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
          <h3>🎯 {t('weakTopics', lang)}</h3>
          {weak.weak.map((w) => (
            <div key={w.topic} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
              <span>{w.subject} → <strong>{w.topic.replace(/_/g, ' ')}</strong></span>
              <span className="badge orange">{w.accuracy_pct}%</span>
            </div>
          ))}
          <p className="muted" style={{ marginBottom: 0 }}>{weak.message}</p>
          <button className="btn small accent" style={{ marginTop: 8 }} onClick={() => go('practice')}>
            {t('recommendedPractice', lang)}
          </button>
        </div>
      )}

      <h3 className="section-title">{t('continueLearning', lang)}</h3>
      {courses.length === 0 && (
        <div className="empty-state"><div className="icon">📚</div>
          <p>{t('empty', lang)}</p>
          <button className="btn" onClick={() => go('explore')}>{t('exploreCourses', lang)}</button>
        </div>
      )}
      {courses.map((c) => (
        <div className="card" key={c.id} style={{ cursor: 'pointer' }} onClick={() => go('course', c.id)}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>{lang === 'hi' ? c.title_en : c.title_en}</strong>
            <span className="badge green">{Math.round(c.progress_pct)}%</span>
          </div>
          <div className="progressbar" style={{ marginTop: 8 }}>
            <div style={{ width: `${c.progress_pct}%` }} />
          </div>
        </div>
      ))}

      {summary && (
        <>
          <h3 className="section-title">{t('progress', lang)}</h3>
          <div className="stat-row">
            <div className="stat"><div className="num">{summary.lessons_completed}</div><div className="lbl">{t('lessonsDone', lang)}</div></div>
            <div className="stat"><div className="num">{summary.quiz_avg_pct === null ? '—' : `${summary.quiz_avg_pct}%`}</div><div className="lbl">{t('quizAvg', lang)}</div></div>
            <div className="stat"><div className="num">{summary.week_minutes}</div><div className="lbl">min / week</div></div>
            <div className="stat"><div className="num">{summary.badges.length}</div><div className="lbl">{t('badges', lang)}</div></div>
            <div className="stat"><div className="num">{summary.certificates.length}</div><div className="lbl">{t('certificates', lang)}</div></div>
          </div>
        </>
      )}
    </div>
  );
}
