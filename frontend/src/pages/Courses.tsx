import { useEffect, useState } from 'react';
import { apiBoards, apiCourses, apiSubjects } from '../api';
import { pick, t } from '../i18n';
import type { Course, Lang, Subject } from '../types';

const GRADES = Array.from({ length: 12 }, (_, i) => i + 1);

export default function Courses({ lang, go }: { lang: Lang; go: (p: string, id?: number) => void }) {
  const [grade, setGrade] = useState<number | ''>('');
  const [board, setBoard] = useState('');
  const [subjectId, setSubjectId] = useState<number | ''>('');
  const [difficulty, setDifficulty] = useState('');
  const [sort, setSort] = useState('popular');
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [boards, setBoards] = useState<{ id: number; name: string }[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { apiBoards().then(setBoards).catch(() => {}); }, []);
  useEffect(() => {
    if (grade && board) apiSubjects(Number(grade), board).then(setSubjects).catch(() => setSubjects([]));
    else setSubjects([]);
  }, [grade, board]);

  useEffect(() => {
    setLoading(true); setError('');
    apiCourses({
      class_grade: grade || null, board: board || null,
      subject_id: subjectId || null, difficulty: difficulty || null, sort,
    }).then((r) => setCourses(r.items)).catch((e) => setError(String(e))).finally(() => setLoading(false));
  }, [grade, board, subjectId, difficulty, sort]);

  return (
    <div>
      <h1>{t('courses', lang)}</h1>
      <div className="card" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8 }}>
        <select value={grade} onChange={(e) => { setGrade(e.target.value ? Number(e.target.value) : ''); setSubjectId(''); }} aria-label="Class">
          <option value="">{t('classes', lang)}: all</option>
          {GRADES.map((g) => <option key={g} value={g}>Class {g}</option>)}
        </select>
        <select value={board} onChange={(e) => { setBoard(e.target.value); setSubjectId(''); }} aria-label="Board">
          <option value="">Board: all</option>
          {boards.map((b) => <option key={b.id} value={b.name}>{b.name}</option>)}
        </select>
        <select value={subjectId} onChange={(e) => setSubjectId(e.target.value ? Number(e.target.value) : '')} aria-label="Subject" disabled={!subjects.length}>
          <option value="">Subject: all</option>
          {subjects.map((s) => <option key={s.id} value={s.id}>{pick(lang, s.name_en, s.name_hi, s.name_mr)}</option>)}
        </select>
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} aria-label="Difficulty">
          <option value="">Level: all</option>
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
          <option value="popular">Popular</option>
          <option value="newest">Newest</option>
          <option value="rating">Highest rated</option>
          <option value="shortest">Shortest</option>
          <option value="longest">Longest</option>
        </select>
      </div>

      {loading && <div><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>}
      {error && <p className="error">{t('errorLoad', lang)}</p>}
      {!loading && !error && courses.length === 0 && (
        <div className="empty-state"><div className="icon">🔍</div><p>No courses found for this filter.</p></div>
      )}

      <div className="grid-cards">
        {courses.map((c) => (
          <div className="card course-card" key={c.id} style={{ cursor: 'pointer' }} onClick={() => go('course', c.id)}>
            <div className="thumb" style={{ background: c.thumb_color }}>{pick(lang, c.title_en, c.title_hi, c.title_mr).charAt(0)}</div>
            <strong>{pick(lang, c.title_en, c.title_hi, c.title_mr)}</strong>
            <div className="muted" style={{ margin: '4px 0 8px' }}>
              Class {c.class_grade} · {c.board}
            </div>
            <div>
              <span className="badge">{c.difficulty}</span>
              <span className="badge gray">⏱ {Math.round(c.duration_min / 60)}h</span>
              <span className="badge orange">★ {c.rating}</span>
            </div>
            <div className="muted" style={{ marginTop: 8 }}>👥 {c.students_count} {t('students', lang)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
