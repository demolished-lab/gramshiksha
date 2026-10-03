import { useEffect, useState } from 'react';
import { apiMyCourses, apiNotifications, apiProgressSummary, apiReadingList, apiToday, apiWeakTopics } from '../api';
import { getUser, getToken } from '../auth';
import { monthLabel, t } from '../i18n';
import { streamName } from '../components/StreamPicker';
import { setTextbookPref } from '../prefs';
import type { Lang, TodayPlan, WeakTopics, ProgressSummary, Notification, ReadingPick } from '../types';

export default function StudentDashboard({ lang, go }: { lang: Lang; go: (p: string, id?: number) => void }) {
  const [today, setToday] = useState<TodayPlan | null>(null);
  const [weak, setWeak] = useState<WeakTopics | null>(null);
  const [summary, setSummary] = useState<ProgressSummary | null>(null);
  const [courses, setCourses] = useState<{ id: number; title_en: string; progress_pct: number }[]>([]);
  const [notifs, setNotifs] = useState<Notification[]>([]);
  const [picks, setPicks] = useState<ReadingPick[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) { go('home'); return; }
    setLoading(true);
    setError('');
    let active = true;
    (async () => {
      const mark = `dashboard-load-${Date.now()}`;
      if (typeof performance !== 'undefined') performance.mark(`${mark}-start`);
      try {
        // The plan and enrolled courses are the critical path. Render the
        // workspace as soon as those two requests finish.
        const [td, mc] = await Promise.all([apiToday(lang), apiMyCourses()]);
        if (!active) return;
        setToday(td); setCourses(mc); setLoading(false);
        if (typeof performance !== 'undefined') {
          performance.mark(`${mark}-ready`);
          performance.measure('gramshiksha-dashboard-critical', `${mark}-start`, `${mark}-ready`);
        }
        // Secondary widgets load independently and cannot blank the dashboard.
        const [wk, sm, nf] = await Promise.allSettled([apiWeakTopics(), apiProgressSummary(), apiNotifications()]);
        if (!active) return;
        if (wk.status === 'fulfilled') setWeak(wk.value);
        if (sm.status === 'fulfilled') setSummary(sm.value);
        if (nf.status === 'fulfilled') setNotifs(nf.value.filter((n) => !n.read));
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : 'Unable to load your learning plan');
      } finally {
        if (active) setLoading(false);
      }
    })();
    // The reading list is public, so a failed fetch must never take this
    // dashboard down with it — it simply stays off the card.
    apiReadingList().then((value) => { if (active) setPicks(value); }).catch(() => { if (active) setPicks([]); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  if (!getToken()) return null;
  if (error) return <div className="error-state"><div className="empty-state"><div className="icon">📡</div><h2>{t('errorLoad', lang)}</h2><p className="muted">{error}</p><button className="btn" onClick={() => window.location.reload()}>Try again</button></div></div>;
  if (loading || !today) return <div aria-busy="true" aria-label="Loading your learning plan"><div className="skeleton skeleton-title" /><div className="skeleton skeleton-panel" /><div className="skeleton skeleton-panel" /></div>;

  let user: { name?: string } = {};
  try { user = JSON.parse(localStorage.getItem('gs_user') || '{}') as { name?: string }; } catch { /* use the fallback greeting */ }

  /** Send a pick to the library, prefilled: a readable one lands with the
   * reader already open, anything else with the search filled and running.
   * The pick's own class/board/medium travel with it so the portal scan (if
   * needed) looks in the right place. */
  const openFromList = (p: ReadingPick) => {
    const me = getUser();
    setTextbookPref({
      grade: p.class_grade ?? me?.class_grade ?? 8,
      board: p.board || me?.board || 'Maharashtra SSC',
      lang: p.lang || undefined,
      stream: p.stream || undefined,
      q: p.title,
      open: p.readable && p.textbook_id ? p.textbook_id : undefined,
    });
    go('textbooks');
  };

  const overall = courses.length
    ? Math.round(courses.reduce((n, c) => n + c.progress_pct, 0) / courses.length)
    : 0;

  return (
    <div>
      {/* Mockup greeting hero: name, streak, overall progress on the blue
          gradient card — same data as before, new presentation. */}
      <div className="dash-hero">
        <div className="dash-hero-row">
          <div><span className="eyebrow" style={{ color: '#c9d8f7' }}>{t('todaysLearning', lang)}</span><h1>👋 {user.name || 'Learner'}</h1><p className="muted" style={{ margin: '4px 0 0' }}>Keep learning, keep growing.</p></div>
          <div className="streak-pill">🔥 <strong>{today.streak_days}</strong> {t('streak', lang)}</div>
        </div>
        <div className="progressbar" aria-label="Overall course progress"><div style={{ width: `${overall}%` }} /></div>
        <div className="dashboard-meta" style={{ color: '#c9d8f7', margin: '12px 0 0' }}><span>⚡ {today.xp} {t('xp', lang)}</span><span>⏱️ {today.study_minutes_today} min studied today</span><span style={{ marginLeft: 'auto' }}>{overall}%</span></div>
      </div>

      <section className="reference-progress-panel" aria-labelledby="progress-panel-title">
        <div><span className="eyebrow">Your progress</span><h2 id="progress-panel-title">Overall course progress</h2></div>
        <strong>{overall}%</strong>
        <div className="progressbar"><div style={{ width: `${overall}%` }} /></div>
        <button className="btn small" onClick={() => go('progress')}>View details →</button>
      </section>

      <div className="reference-metric-grid" aria-label="Learning summary">
        <div className="reference-metric"><span>📚</span><strong>{courses.length}</strong><small>Courses enrolled</small></div>
        <div className="reference-metric"><span>✅</span><strong>{summary?.lessons_completed ?? 0}</strong><small>Lessons completed</small></div>
        <div className="reference-metric"><span>📝</span><strong>{summary?.quizzes_taken ?? 0}</strong><small>Assignments</small></div>
        <div className="reference-metric"><span>🏆</span><strong>{summary?.certificates.length ?? 0}</strong><small>Certificates</small></div>
      </div>

      {notifs.length > 0 && (
        <div className="card" style={{ borderLeft: '4px solid var(--accent)' }}>
          <strong>🔔 {notifs.length}</strong>
          {/* A queued book that the keep-warm scan just found carries the book
              title only — name the event, otherwise the learner reads a bare
              subject name with no idea why it is here. */}
          <div className="muted">
            {notifs[0].type === 'book_available'
              ? `📖 ${t('bookArrived', lang)} — ${String(notifs[0].payload.title ?? '')}`
              : String(notifs[0].payload.title ?? notifs[0].payload.badge ?? notifs[0].type)}
          </div>
        </div>
      )}

      {/* Monthly Reading List — the book club a teacher posts to once a month.
          One hop to the library either way: a readable pick opens straight in
          the in-app reader, any other drops its title into the Smart Book
          Finder. Nothing ever navigates to another site. */}
      {!!picks.length && (
        <div className="card reading-banner">
          <div className="reading-head">
            <strong>📚 {t('readingList', lang)} · {monthLabel(picks[0].month, lang)}</strong>
            <span className="muted">{t('readingClubHint', lang)}</span>
          </div>
          {picks.slice(0, 2).map((p) => (
            <div className="reading-row" key={p.id}>
              <div className="reading-text">
                <div className="reading-title">
                  {p.title}
                  {p.author && <span className="muted"> · {p.author}</span>}
                </div>
                <div className="muted reading-meta">
                  {p.teacher_name}{p.subject_name ? ` · ${p.subject_name}` : ''}{p.stream ? ` · ${streamName(p.stream, lang)}` : ''}
                </div>
                {p.note && <p className="reading-note">{p.note}</p>}
              </div>
              <button type="button"
                className={`btn small ${p.readable && p.textbook_id ? 'accent' : ''}`}
                onClick={() => openFromList(p)}>
                {p.readable && p.textbook_id ? `📖 ${t('read', lang)}` : `🔎 ${t('findThisBook', lang)}`}
              </button>
            </div>
          ))}
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
      {!!courses.length && (
        <div className="course-grid">
          {courses.map((c) => (
            <div className="course-card2" key={c.id}>
              <div className="course-thumb" aria-hidden="true"
                style={{ background: `linear-gradient(135deg, hsl(${(c.id * 47) % 360}, 62%, 52%), hsl(${((c.id * 47) % 360 + 40) % 360}, 60%, 42%)` }}>
                📖
              </div>
              <div className="course-body">
                <strong>{c.title_en}</strong>
                <div className="progressbar"><div style={{ width: `${c.progress_pct}%` }} /></div>
                <span className="muted">{Math.round(c.progress_pct)}%</span>
                <button className="btn small" onClick={() => go('course', c.id)}>
                  {t('continue', lang)}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <h3 className="section-title">Recommended for you <button className="text-link" onClick={() => go('explore')}>View all →</button></h3>
      <div className="recommendation-grid">
        {[
          ['🎬', 'Important questions', 'Board exam revision', 'practice'],
          ['🧠', 'Full chapter revision', 'Science Class 10', 'practice'],
          ['📄', 'Previous year papers', 'Maths 2020–2024', 'textbooks'],
          ['🌿', 'Short notes', 'All subjects', 'materials'],
        ].map(([icon, title, sub, route]) => (
          <button className="recommendation-card" key={title} onClick={() => go(route)}>
            <span className="recommendation-thumb">{icon}</span><strong>{title}</strong><small>{sub}</small>
          </button>
        ))}
      </div>

      {summary && (
        <>
          <h3 className="section-title">{t('progress', lang)}</h3>
          <div className="stat-cards">
            <div className="stat-card"><div className="ic" aria-hidden="true">📚</div><div className="num">{courses.length}</div><div className="lbl">{t('exploreCourses', lang)}</div></div>
            <div className="stat-card"><div className="ic" aria-hidden="true">✅</div><div className="num">{summary.lessons_completed}</div><div className="lbl">{t('lessonsDone', lang)}</div></div>
            <div className="stat-card"><div className="ic" aria-hidden="true">🎯</div><div className="num">{summary.quiz_avg_pct === null ? '—' : `${summary.quiz_avg_pct}%`}</div><div className="lbl">{t('quizAvg', lang)}</div></div>
            <div className="stat-card"><div className="ic" aria-hidden="true">🏆</div><div className="num">{summary.badges.length}</div><div className="lbl">{t('badges', lang)}</div></div>
          </div>
        </>
      )}
    </div>
  );
}
