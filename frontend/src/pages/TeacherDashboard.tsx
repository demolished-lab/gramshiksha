import { useEffect, useState } from 'react';
import { apiDoubts, apiReplyDoubt, apiTeacherOverview, apiTeacherStudents } from '../api';
import { t } from '../i18n';
import type { Doubt, Lang, TeacherStudent } from '../types';

export default function TeacherDashboard({ lang }: { lang: Lang }) {
  const [overview, setOverview] = useState<Awaited<ReturnType<typeof apiTeacherOverview>> | null>(null);
  const [students, setStudents] = useState<TeacherStudent[]>([]);
  const [doubts, setDoubts] = useState<Doubt[]>([]);
  const [replyFor, setReplyFor] = useState<number | null>(null);
  const [replyText, setReplyText] = useState('');
  const [error, setError] = useState('');

  const load = () => {
    Promise.all([apiTeacherOverview(), apiTeacherStudents(), apiDoubts()])
      .then(([ov, st, db]) => { setOverview(ov); setStudents(st); setDoubts(db.filter((d) => d.status === 'pending')); })
      .catch((e) => setError(String(e)));
  };
  useEffect(load, []);

  if (error) return <p className="error">{t('errorLoad', lang)} — {error}</p>;

  return (
    <div>
      <h1>👩‍🏫 {t('teacher', lang)}</h1>

      {overview && (
        <div className="stat-row">
          <div className="stat"><div className="num">{overview.total_students}</div><div className="lbl">{t('students', lang)}</div></div>
          <div className="stat"><div className="num">{overview.my_courses.length}</div><div className="lbl">{t('courses', lang)}</div></div>
          <div className="stat"><div className="num">{overview.pending_material_reviews}</div><div className="lbl">{t('pending', lang)}</div></div>
          <div className="stat"><div className="num">{overview.pending_doubts}</div><div className="lbl">{t('doubts', lang)}</div></div>
        </div>
      )}

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
