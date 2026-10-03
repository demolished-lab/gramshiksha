import { useEffect, useState } from 'react';
import { apiPracticeAnswer, apiPracticeQuestions, apiWeakTopics } from '../api';
import { getToken, enqueue } from '../auth';
import { t } from '../i18n';
import type { Lang, Question, WeakTopics } from '../types';

export default function Practice({ lang }: { lang: Lang }) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [idx, setIdx] = useState(0);
  const [feedback, setFeedback] = useState<{ correct: boolean; explanation: string } | null>(null);
  const [chosen, setChosen] = useState<unknown>(null);
  const [fillText, setFillText] = useState('');
  const [stats, setStats] = useState({ attempted: 0, correct: 0 });
  const [weak, setWeak] = useState<WeakTopics | null>(null);
  const [difficulty, setDifficulty] = useState('');
  const [error, setError] = useState('');
  const [flagged, setFlagged] = useState<number[]>([]);
  const [answered, setAnswered] = useState<number[]>([]);

  const load = (diff: string) => {
    setQuestions([]); setIdx(0); setFeedback(null); setChosen(null);
    setFlagged([]); setAnswered([]);
    apiPracticeQuestions({ difficulty: diff || undefined, limit: 10, lang })
      .then(setQuestions).catch((e) => setError(String(e)));
  };

  useEffect(() => {
    load('');
    if (getToken()) apiWeakTopics().then(setWeak).catch(() => {});
  }, [lang]);

  const q = questions[idx];

  const answer = async (val: unknown) => {
    if (!q || feedback) return;
    setChosen(val);
    setAnswered((a) => (a.includes(q.id) ? a : [...a, q.id]));
    if (navigator.onLine && getToken()) {
      try {
        const r = await apiPracticeAnswer(q.id, val);
        setFeedback(r);
        setStats((s) => ({ attempted: s.attempted + 1, correct: s.correct + (r.correct ? 1 : 0) }));
        return;
      } catch { /* fall through to offline */ }
    }
    enqueue({ kind: 'practice_answer', question_id: q.id, payload: { answer: val } });
    setFeedback({ correct: false, explanation: 'Saved offline — will sync when online.' });
    setStats((s) => ({ attempted: s.attempted + 1, correct: s.correct }));
  };

  if (error && !questions.length) return <p className="error">{t('errorLoad', lang)}</p>;

  return (
    <div>
      <h1>✏️ {t('practice', lang)}</h1>

      {weak && weak.weak.length > 0 && (
        <div className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
          <strong>🎯 {t('weakTopics', lang)}:</strong>{' '}
          {weak.weak.map((w) => (
            <button key={w.topic} className="btn small ghost" style={{ margin: 4 }}
              onClick={() => { setDifficulty('easy'); load('easy'); }}>
              {w.topic.replace(/_/g, ' ')} ({w.accuracy_pct}%)
            </button>
          ))}
        </div>
      )}

      <div className="quiz-shell">
      <div className="card quiz-main">
        <div className="quiz-top">
          <span className="quiz-count">Question {questions.length ? idx + 1 : '—'} of {questions.length || '—'}</span>
          <span style={{ flex: 1 }} />
          <span className="muted">✓ {stats.correct}/{stats.attempted}</span>
          {q && (
            <button type="button" className={`btn small ${flagged.includes(q.id) ? '' : 'ghost'}`}
              onClick={() => setFlagged((f) => (f.includes(q.id) ? f.filter((x) => x !== q.id) : [...f, q.id]))}>
              ⚑ Review
            </button>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
          {['', 'easy', 'medium', 'hard'].map((d) => (
            <button key={d || 'all'} className={`btn small ${difficulty === d ? '' : 'ghost'}`}
              onClick={() => { setDifficulty(d); load(d); }}>
              {d || 'all'}
            </button>
          ))}
        </div>

        {!questions.length && !error && <div className="skeleton" style={{ height: 80 }} />}

        {q && (
          <>
            <strong style={{ fontSize: '1.05rem' }}>{q.prompt}</strong>
            {q.type === 'fill' ? (
              <>
                <input style={{ marginTop: 10 }} value={fillText} disabled={!!feedback}
                  onChange={(e) => setFillText(e.target.value)} placeholder="Answer" />
                {!feedback && <button className="btn" style={{ marginTop: 10 }} disabled={!fillText.trim()} onClick={() => answer(fillText.trim())}>{t('submit', lang)}</button>}
              </>
            ) : (
              q.options.map((o, oi) => {
                let cls = 'opt';
                if (!feedback && chosen === oi) cls += ' selected';
                if (feedback) {
                  const correctArr = Array.isArray(feedback) ? [] : null;
                  void correctArr;
                  const r = feedback as unknown as { correct_answer?: unknown };
                  const arr = Array.isArray(r.correct_answer) ? r.correct_answer as number[] : r.correct_answer === oi ? [oi] : [];
                  if (arr.includes(oi)) cls += ' correct';
                  else if (chosen === oi) cls += ' wrong';
                }
                return (
                  <div key={oi} className={cls} onClick={() => answer(oi)}>
                    {String.fromCharCode(65 + oi)}. {o}
                  </div>
                );
              })
            )}
            {feedback && (
              <>
                <p className={feedback.correct ? 'success' : 'error'}>
                  {feedback.correct ? '✅ ' + t('completed', lang) : '❌'}
                </p>
                <p className="muted">{feedback.explanation}</p>
              </>
            )}
          </>
        )}
        </div>
        {!!questions.length && (
          <div className="card quiz-palette" aria-label="Question palette">
            <strong>Questions</strong>
            <div className="qgrid">
              {questions.map((qq, qi) => (
                <button key={qq.id} type="button"
                  className={`qnum${qi === idx ? ' cur' : ''}${answered.includes(qq.id) ? ' done' : ''}${flagged.includes(qq.id) ? ' flagged' : ''}`}
                  onClick={() => {
                    setFeedback(null); setChosen(null); setFillText(''); setIdx(qi);
                  }}>
                  {qi + 1}
                </button>
              ))}
            </div>
            <div className="quiz-legend muted"><span>🟩 answered</span><span>⚑ review</span></div>
          </div>
        )}
      </div>
      {!!questions.length && (
        <div className="quiz-nav">
          <button className="btn ghost" disabled={!idx} onClick={() => {
            setFeedback(null); setChosen(null); setFillText(''); setIdx(idx - 1);
          }}>
            ← {t('back', lang)}
          </button>
          <button className="btn" onClick={() => {
            if (feedback || !q) {
              setFeedback(null); setChosen(null); setFillText('');
              if (idx + 1 >= questions.length) load(difficulty);
              else setIdx(idx + 1);
            } else {
              setFeedback(null); setChosen(null); setFillText(''); setIdx((idx + 1) % questions.length);
            }
          }}>
            {t('next', lang)} →
          </button>
        </div>
      )}
    </div>
  );
}
