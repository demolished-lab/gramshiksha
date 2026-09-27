import { useEffect, useState } from 'react';
import { apiAddBookmark, apiAddNote, apiCompleteLesson, apiLesson, apiNotes, apiQuizByChapter, apiQuizSubmit } from '../api';
import { dataSaver, enqueue, getToken } from '../auth';
import { t } from '../i18n';
import type { Lang, LessonDetail, QuizDetail, QuizResult } from '../types';

export default function LessonPage({ lang, go, lessonId }: { lang: Lang; go: (p: string, id?: number) => void; lessonId: number }) {
  const [lesson, setLesson] = useState<LessonDetail | null>(null);
  const [done, setDone] = useState(false);
  const [xpMsg, setXpMsg] = useState('');
  const [notes, setNotes] = useState<{ id: number; body: string }[]>([]);
  const [noteText, setNoteText] = useState('');
  const [showQuiz, setShowQuiz] = useState(false);
  const [quiz, setQuiz] = useState<QuizDetail | null>(null);
  const [quizResult, setQuizResult] = useState<QuizResult | null>(null);
  const [error, setError] = useState('');
  const saver = dataSaver();

  useEffect(() => {
    apiLesson(lessonId, lang).then((l) => {
      setLesson(l);
      setDone(l.completed);
    }).catch((e) => setError(String(e)));
    if (getToken()) apiNotes(lessonId).then(setNotes).catch(() => {});
  }, [lessonId, lang]);

  const complete = async () => {
    try {
      if (navigator.onLine && getToken()) {
        const r = await apiCompleteLesson(lessonId, lesson?.duration_min ?? 10);
        setXpMsg(`+${r.xp} XP · 🔥 ${r.streak_days}`);
      } else {
        enqueue({ kind: 'lesson_complete', lesson_id: lessonId, payload: { minutes: lesson?.duration_min ?? 10 } });
        setXpMsg('saved offline — will sync');
      }
      setDone(true);
    } catch (e) { setError(String(e)); }
  };

  const startQuiz = async () => {
    if (!lesson?.chapter_id) return;
    const q = await apiQuizByChapter(lesson.chapter_id, lang).catch(() => null);
    if (!q) { setError('No quiz for this chapter yet.'); return; }
    setQuiz(q);
    setShowQuiz(true);
  };

  const addNote = async () => {
    if (!noteText.trim() || !getToken()) return;
    const n = await apiAddNote(lessonId, noteText.trim()).catch(() => null);
    if (n) { setNotes([...notes, { id: n.id, body: noteText.trim() }]); setNoteText(''); }
  };

  if (error && !lesson) return <p className="error">{t('errorLoad', lang)}</p>;
  if (!lesson) return <div><div className="skeleton" style={{ width: '40%' }} /><div className="skeleton" style={{ height: 120 }} /><div className="skeleton" /></div>;

  return (
    <div>
      <button className="btn ghost small" onClick={() => lesson.course_id ? go('course', lesson.course_id) : go('courses')}>← {t('back', lang)}</button>

      <div className="card">
        <h1>{lesson.title}</h1>
        <div style={{ margin: '6px 0' }}>
          <span className="badge gray">{lesson.type}</span>
          <span className="badge">⏱ {lesson.duration_min} min</span>
          <span className="badge orange">📶 ~{lesson.estimate_mb} MB</span>
          {done && <span className="badge green">✓ {t('completed', lang)}</span>}
        </div>

        {/* Video: only load on tap in data-saver mode */}
        {lesson.video_url && (
          saver ? (
            <a className="btn ghost" href={lesson.video_url} target="_blank" rel="noreferrer" style={{ marginBottom: 10 }}>
              🎬 {saver ? 'Load video (~' + lesson.estimate_mb + ' MB)' : 'Watch video'}
            </a>
          ) : (
            <div style={{ background: '#0F172A', borderRadius: 10, padding: '32px 16px', textAlign: 'center', color: '#fff', marginBottom: 10 }}>
              🎬 video player — <a href={lesson.video_url} target="_blank" rel="noreferrer" style={{ color: '#93C5FD' }}>open</a>
              {lesson.video_url_low && <> · <a href={lesson.video_url_low} target="_blank" rel="noreferrer" style={{ color: '#93C5FD' }}>240p</a></>}
            </div>
          )
        )}

        <p style={{ whiteSpace: 'pre-line', lineHeight: 1.8 }}>{lesson.body}</p>

        {lesson.audio_url && <audio controls src={lesson.audio_url} style={{ width: '100%' }} />}

        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          {!done && <button className="btn" onClick={complete}>✓ {t('markComplete', lang)}</button>}
          {lesson.questions.length > 0 && !showQuiz && <button className="btn accent" onClick={startQuiz}>✏️ Practice</button>}
          {getToken() && <button className="btn ghost" onClick={() => apiAddBookmark(lessonId).catch(() => {})}>🔖 {t('bookmark', lang)}</button>}
        </div>
        {xpMsg && <p className="success">⚡ {xpMsg}</p>}
        {error && <p className="error">{error}</p>}
      </div>

      {/* Inline practice questions */}
      {showQuiz && quiz && (
        <InlineQuiz lang={lang} quiz={quiz} onDone={(r) => setQuizResult(r)} result={quizResult} />
      )}

      {/* Notes */}
      <div className="card">
        <h3>📝 {t('myNotes', lang)}</h3>
        {notes.map((n) => <p key={n.id} style={{ borderBottom: '1px solid var(--border)', paddingBottom: 6 }}>{n.body}</p>)}
        {getToken() ? (
          <>
            <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder={t('addNote', lang)} />
            <button className="btn small" style={{ marginTop: 8 }} disabled={!noteText.trim()} onClick={addNote}>{t('addNote', lang)}</button>
          </>
        ) : <p className="muted">Log in to save notes.</p>}
      </div>
    </div>
  );
}

function InlineQuiz({ lang, quiz, onDone, result }: {
  lang: Lang; quiz: QuizDetail; onDone: (r: QuizResult) => void; result: QuizResult | null;
}) {
  const [answers, setAnswers] = useState<Record<number, unknown>>({});
  const [startedAt] = useState(Date.now());
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await apiQuizSubmit(quiz.id, quiz.questions.map((q) => ({ question_id: q.id, answer: answers[q.id] ?? null })),
        Math.round((Date.now() - startedAt) / 1000));
      onDone(r);
    } finally { setBusy(false); }
  };

  return (
    <div className="card">
      <h3>✏️ {quiz.title}</h3>
      {quiz.questions.map((q, qi) => {
        const res = result?.per_question[qi];
        return (
          <div key={q.id} style={{ marginBottom: 18 }}>
            <strong>{qi + 1}. {q.prompt}</strong>
            {(q.type === 'fill') ? (
              <input style={{ marginTop: 8 }} placeholder="Answer"
                disabled={!!result}
                onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} />
            ) : (
              q.options.map((o, oi) => {
                let cls = 'opt';
                if (!result && answers[q.id] === oi) cls += ' selected';
                if (result && res) {
                  const correctArr = Array.isArray(res.correct_answer) ? res.correct_answer : [res.correct_answer];
                  if (correctArr.includes(oi)) cls += ' correct';
                  else if (answers[q.id] === oi) cls += ' wrong';
                }
                return (
                  <div key={oi} className={cls} onClick={() => !result && setAnswers({ ...answers, [q.id]: oi })}>
                    {String.fromCharCode(65 + oi)}. {o}
                  </div>
                );
              })
            )}
            {result && res && <p className="explanation muted">{res.correct ? '✅' : '❌'} {res.explanation}</p>}
          </div>
        );
      })}
      {!result ? (
        <button className="btn" disabled={busy || Object.keys(answers).length < quiz.questions.length} onClick={submit}>
          {t('submit', lang)}
        </button>
      ) : (
        <div className="scorebox" style={{ textAlign: 'center', background: '#F0FDF4', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--success)' }}>{result.percentage}%</div>
          <div className="muted">⏱ {Math.round(result.time_taken_s / 60)} min {t('yourScore', lang)}</div>
        </div>
      )}
    </div>
  );
}
