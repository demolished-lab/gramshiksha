import { useEffect, useState } from 'react';
import { apiDeletePick, apiDoubts, apiReadingList, apiReplyDoubt, apiSavePick, apiTeacherOverview, apiTeacherStudents } from '../api';
import { monthLabel, t } from '../i18n';
import type { Doubt, Lang, ReadingPick, TeacherStudent } from '../types';

/** Current month as the API expects it ("2026-10"), in the teacher's own
 * timezone — the pick is posted for the month they are actually in. */
const currentMonth = (): string => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
};

export default function TeacherDashboard({ lang }: { lang: Lang }) {
  const [overview, setOverview] = useState<Awaited<ReturnType<typeof apiTeacherOverview>> | null>(null);
  const [students, setStudents] = useState<TeacherStudent[]>([]);
  const [doubts, setDoubts] = useState<Doubt[]>([]);
  const [replyFor, setReplyFor] = useState<number | null>(null);
  const [replyText, setReplyText] = useState('');
  const [error, setError] = useState('');

  // Monthly Reading List: the teacher's own picks (`mine=1`) plus the form.
  const [picks, setPicks] = useState<ReadingPick[]>([]);
  const [month, setMonth] = useState(currentMonth);
  const [title, setTitle] = useState('');
  const [author, setAuthor] = useState('');
  const [note, setNote] = useState('');
  const [saved, setSaved] = useState('');
  const [formError, setFormError] = useState('');

  const loadPicks = () => {
    apiReadingList(true).then(setPicks).catch(() => setPicks([]));
  };

  const load = () => {
    Promise.all([apiTeacherOverview(), apiTeacherStudents(), apiDoubts()])
      .then(([ov, st, db]) => { setOverview(ov); setStudents(st); setDoubts(db.filter((d) => d.status === 'pending')); })
      .catch((e) => setError(String(e)));
  };
  useEffect(load, []);
  // Kept off `load()` on purpose: a reading-list hiccup must not blank the
  // whole dashboard (load()'s failure is fatal by design).
  useEffect(loadPicks, []);

  /** Reposting the same title in the same month rewrites it server-side, so
   * the form never stacks duplicates; a save failure stays on the form. */
  const savePick = async () => {
    const clean = title.trim();
    if (clean.length < 2 || !month) return;
    setFormError('');
    setSaved('');
    try {
      const row = await apiSavePick({
        month, title: clean, author: author.trim(), note: note.trim(),
      });
      setTitle(''); setAuthor(''); setNote('');
      setSaved(`${t('saved', lang)} — ${row.title}`);
      loadPicks();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    }
  };

  const withdraw = async (id: number) => {
    setFormError('');
    try {
      await apiDeletePick(id);
      loadPicks();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    }
  };

  if (error) return <p className="error">{t('errorLoad', lang)} — {error}</p>;

  // Class performance, honestly: the share of students (with any quiz data)
  // in each score band. No quiz data yet → no chart, not a flat line.
  const scored = students.filter((s) => s.quiz_avg_pct !== null);
  const banded: [string, number][] = [['<40', 0], ['40–60', 0], ['60–80', 0], ['80+', 0]];
  for (const s of scored) {
    const v = s.quiz_avg_pct ?? 0;
    banded[v < 40 ? 0 : v < 60 ? 1 : v < 80 ? 2 : 3][1] += 1;
  }
  const bandMax = Math.max(1, ...banded.map((b) => b[1]));
  const weakStudents = students.filter((s) => s.weak_topics.length > 0
    || (s.quiz_avg_pct !== null && (s.quiz_avg_pct ?? 100) < 50));

  return (
    <div>
      <div className="dash-hero">
        <div className="dash-hero-row">
          <div><span className="eyebrow" style={{ color: '#c9d8f7' }}>{t('teacher', lang)}</span><h1>👩‍🏫 Welcome back</h1><p className="muted" style={{ margin: '4px 0 0' }}>{overview ? `${overview.total_students} students · ${overview.my_courses.length} courses` : t('loading', lang)}</p></div>
        </div>
      </div>

      {overview && (
        <div className="stat-cards">
          <div className="stat-card"><div className="ic" aria-hidden="true">👥</div><div className="num">{overview.total_students}</div><div className="lbl">{t('students', lang)}</div></div>
          <div className="stat-card"><div className="ic" aria-hidden="true">📚</div><div className="num">{overview.my_courses.length}</div><div className="lbl">{t('courses', lang)}</div></div>
          <div className="stat-card"><div className="ic" aria-hidden="true">📦</div><div className="num">{overview.pending_material_reviews}</div><div className="lbl">{t('pending', lang)}</div></div>
          <div className="stat-card"><div className="ic" aria-hidden="true">❓</div><div className="num">{overview.pending_doubts}</div><div className="lbl">{t('doubts', lang)}</div></div>
        </div>
      )}

      <div className="two-col">
        <div className="card">
          <h3>📰 Recent activity</h3>
          <div className="activity">
            {doubts.slice(0, 3).map((d) => (
              <div className="activity-item" key={`d${d.id}`}>
                <span className="activity-ava" aria-hidden="true">❓</span>
                <div><strong>{d.student_name}</strong> <span className="muted">asked in {d.subject_name}</span><div className="muted">{d.text.slice(0, 80)}{d.text.length > 80 ? '…' : ''}</div></div>
              </div>
            ))}
            {weakStudents.slice(0, 3).map((s) => (
              <div className="activity-item" key={`s${s.id}`}>
                <span className="activity-ava" aria-hidden="true">🎯</span>
                <div><strong>{s.name}</strong> <span className="muted">needs help{s.quiz_avg_pct !== null ? ` · quiz ${s.quiz_avg_pct}%` : ''}</span></div>
              </div>
            ))}
            {!doubts.length && !weakStudents.length && (
              <p className="muted">All quiet — no pending doubts, no struggling students ✓</p>
            )}
          </div>
        </div>
        <div className="card">
          <h3>📊 Class performance</h3>
          {!scored.length && <p className="muted">Quiz scores appear here once students attempt quizzes.</p>}
          {!!scored.length && (
            <div className="bars" role="img" aria-label={`Quiz score bands across ${scored.length} students`}>
              {banded.map(([label, n]) => (
                <div className="bar-col" key={label}>
                  <span className="muted">{n}</span>
                  <div className={`bar${n === 0 ? ' dim' : ''}`} style={{ height: `${Math.max(5, (n / bandMax) * 105)}px` }} />
                  <small>{label}</small>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>


      {/* Monthly Reading List: post one pick a month and every student sees
          it (book club — the audience is all students, not a class). The
          server links a pick to the catalog when the title is already there,
          so a posted book is readable in-app the moment it exists. */}
      <div className="card reading-banner">
        <div className="reading-head">
          <strong>📚 {t('readingList', lang)} · {monthLabel(month, lang)}</strong>
          <span className="muted">{t('readingClubHint', lang)}</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8, marginTop: 8 }}>
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)}
            aria-label={t('pickMonth', lang)} />
          <input value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder={t('pickTitle', lang)} aria-label={t('pickTitle', lang)}
            style={{ gridColumn: 'span 2' }}
            onKeyDown={(e) => { if (e.key === 'Enter') void savePick(); }} />
          <input value={author} onChange={(e) => setAuthor(e.target.value)}
            placeholder={t('pickAuthor', lang)} aria-label={t('pickAuthor', lang)} />
          <input value={note} onChange={(e) => setNote(e.target.value)}
            placeholder={t('pickNote', lang)} aria-label={t('pickNote', lang)} />
          <button type="button" className="btn accent" onClick={() => void savePick()}
            disabled={title.trim().length < 2 || !month}>
            ➕ {t('postPick', lang)}
          </button>
        </div>
        {formError && <p className="error">{formError}</p>}
        {saved && <p className="success">{saved}</p>}

        {!picks.length && <p className="muted">{t('readingEmpty', lang)}</p>}
        {!!picks.length && (
          <div style={{ marginTop: 6 }}>
            <div className="muted" style={{ fontSize: '.8rem' }}>{t('myPicks', lang)}</div>
            {picks.map((p) => (
              <div className="reading-row" key={p.id}>
                <div className="reading-text">
                  <div className="reading-title">
                    {p.title}
                    {p.author && <span className="muted"> · {p.author}</span>}
                  </div>
                  <div className="muted reading-meta">
                    {monthLabel(p.month, lang)}
                    {p.subject_name ? ` · ${p.subject_name}` : ''}
                    {p.readable ? ' · 📄' : ''}
                  </div>
                  {p.note && <p className="reading-note">{p.note}</p>}
                </div>
                <button type="button" className="btn small ghost" onClick={() => void withdraw(p.id)}>
                  ✕ {t('withdraw', lang)}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h3>🚨 Students needing help</h3>
        {!students.length && <p className="muted">{t('loading', lang)}</p>}
        {students.filter((s) => s.weak_topics.length > 0 || s.quiz_avg_pct !== null && s.quiz_avg_pct < 50).length === 0 && students.length > 0 && (
          <p className="success">All students are doing well ✓</p>
        )}
        <table>
          <thead>
            <tr><th>{t('name', lang)}</th><th>Class</th><th>{t('lessonsDone', lang)}</th><th>{t('quizAvg', lang)}</th><th>{t('needHelp', lang)}</th></tr>
          </thead>
          <tbody>
            {students.map((s) => (
              <tr key={s.id}>
                <td><strong>{s.name}</strong><div className="muted">🔥 {s.streak_days} · ⚡ {s.xp}</div></td>
                <td>{s.class_grade ?? '—'}</td>
                <td>{s.lessons_completed}</td>
                <td>{s.quiz_avg_pct === null ? '—' : `${s.quiz_avg_pct}%`}</td>
                <td>
                  {s.weak_topics.length === 0 ? '—' : s.weak_topics.map((w) => (
                    <span key={w.topic} className="badge orange" style={{ display: 'inline-block', marginBottom: 2 }}>
                      {w.topic.replace(/_/g, ' ')} {w.accuracy_pct}%
                    </span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>❓ Pending doubts ({doubts.length})</h3>
        {!doubts.length && <p className="muted">No pending doubts ✓</p>}
        {doubts.map((d) => (
          <div key={d.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
            <strong>{d.subject_name}</strong> <span className="muted">— {d.student_name}</span>
            <p style={{ margin: '6px 0' }}>{d.text}</p>
            {replyFor === d.id ? (
              <div style={{ display: 'flex', gap: 8 }}>
                <input value={replyText} onChange={(e) => setReplyText(e.target.value)} placeholder="Type your answer…" />
                <button className="btn small" onClick={async () => {
                  await apiReplyDoubt(d.id, replyText); setReplyFor(null); setReplyText(''); load();
                }}>{t('send', lang)}</button>
              </div>
            ) : (
              <button className="btn small" onClick={() => setReplyFor(d.id)}>💬 Answer</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
