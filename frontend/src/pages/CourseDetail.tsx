import { useEffect, useState } from 'react';
import { apiCourse, apiEnroll, apiMyCourses, apiProgressSummary } from '../api';
import { getToken } from '../auth';
import { pick, t } from '../i18n';
import type { Course, Lang, ProgressSummary } from '../types';

export default function CourseDetail({ lang, go, courseId }: { lang: Lang; go: (p: string, id?: number) => void; courseId: number }) {
  const [course, setCourse] = useState<Course | null>(null);
  const [enrolled, setEnrolled] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiCourse(courseId).then(setCourse).catch((e) => setError(String(e)));
    if (getToken()) {
      apiMyCourses().then((mine) => setEnrolled(mine.some((c) => c.id === courseId))).catch(() => {});
    }
  }, [courseId]);

  const enroll = async () => {
    if (!getToken()) { go('home'); return; }
    setBusy(true);
    try {
      await apiEnroll(courseId);
      setEnrolled(true);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };

  if (error) return <p className="error">{t('errorLoad', lang)}</p>;
  if (!course) return <div><div className="skeleton" style={{ width: '50%' }} /><div className="skeleton" /></div>;

  const totalLessons = course.chapters?.reduce((n, ch) => n + ch.lessons.length, 0) ?? 0;

  return (
    <div>
      <button className="btn ghost small" onClick={() => go('explore')}>← {t('back', lang)}</button>
      <div className="card">
        <h1>{pick(lang, course.title_en, course.title_hi, course.title_mr)}</h1>
        <div style={{ margin: '8px 0' }}>
          <span className="badge">Class {course.class_grade}</span>
          <span className="badge">{course.board}</span>
          <span className="badge gray">{course.difficulty}</span>
          <span className="badge orange">★ {course.rating}</span>
          <span className="badge green">₹0</span>
        </div>
        <p className="muted">{pick(lang, course.desc_en, course.desc_hi, course.desc_mr)}</p>
        <p className="muted" style={{ marginBottom: 0 }}>
          📖 {totalLessons} lessons · ⏱ {Math.round(course.duration_min / 60)}h · 👥 {course.students_count}
        </p>
        {!enrolled && (
          <button className="btn accent" style={{ marginTop: 12 }} disabled={busy} onClick={enroll}>
            {t('enroll', lang)}
          </button>
        )}
      </div>

      {(course.chapters ?? []).map((ch) => (
        <div className="card" key={ch.id}>
          <h3>{ch.order}. {pick(lang, ch.title_en, ch.title_hi, ch.title_mr)}</h3>
          {ch.lessons.map((l) => (
            <div key={l.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <span>{l.type === 'video' ? '🎬' : l.type === 'audio' ? '🎧' : '📄'}</span>
              <div style={{ flex: 1, fontWeight: 500 }}>
                {pick(lang, l.title_en, l.title_hi, l.title_mr)}
                <span className="muted" style={{ marginLeft: 8 }}>{l.duration_min} min · ~{l.estimate_mb} MB</span>
              </div>
              <button className="btn small" onClick={() => go('lesson', l.id)}>{t('continue', lang)}</button>
            </div>
          ))}
        </div>
      ))}
      {getToken() && <ProgressHint lang={lang} />}
    </div>
  );
}

function ProgressHint({ lang }: { lang: Lang }) {
  const [summary, setSummary] = useState<ProgressSummary | null>(null);
  useEffect(() => { apiProgressSummary().then(setSummary).catch(() => {}); }, []);
  if (!summary) return null;
  return (
    <p className="muted">
      {t('lessonsDone', lang)}: {summary.lessons_completed} · {t('quizAvg', lang)}: {summary.quiz_avg_pct ?? '—'}%
    </p>
  );
}
