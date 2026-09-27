import { useEffect, useState } from 'react';
import { apiParentChildren } from '../api';
import { t } from '../i18n';
import type { Lang, ParentChild } from '../types';

export default function ParentDashboard({ lang }: { lang: Lang }) {
  const [children, setChildren] = useState<ParentChild[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    apiParentChildren().then(setChildren).catch((e) => setError(String(e)));
  }, []);

  return (
    <div>
      <h1>👪 {t('parent', lang)}</h1>
      {error && <p className="error">{t('errorLoad', lang)}</p>}
      {!children.length && !error && (
        <div className="empty-state">
          <div className="icon">👪</div>
          <p>No child linked yet. Ask your child's teacher to link the account, or register the child with your parent email.</p>
        </div>
      )}
      {children.map((c) => (
        <div className="card" key={c.id}>
          <h3>👦 {c.name} — Class {c.class_grade} ({c.board})</h3>
          <div className="stat-row" style={{ marginBottom: 10 }}>
            <div className="stat"><div className="num">{c.lessons_completed}</div><div className="lbl">{t('lessonsDone', lang)}</div></div>
            <div className="stat"><div className="num">{Math.floor(c.week_minutes / 60)}h {c.week_minutes % 60}m</div><div className="lbl">{t('studyTime', lang)} / week</div></div>
            <div className="stat"><div className="num">{c.quiz_avg_pct === null ? '—' : `${c.quiz_avg_pct}%`}</div><div className="lbl">{t('quizAvg', lang)}</div></div>
            <div className="stat"><div className="num">🔥 {c.streak_days}</div><div className="lbl">{t('streak', lang)}</div></div>
            <div className="stat"><div className="num">{c.badges}</div><div className="lbl">{t('badges', lang)}</div></div>
            <div className="stat"><div className="num">{c.certificates}</div><div className="lbl">{t('certificates', lang)}</div></div>
          </div>
          {c.weak_subjects.length > 0 && (
            <p><span className="badge orange">{t('needHelp', lang)}: {c.weak_subjects.join(', ')}</span></p>
          )}
        </div>
      ))}
    </div>
  );
}
