import { useEffect, useState } from 'react';
import { apiAvailability } from '../api';
import { booksIn, subjectLabel, visibleSubjects } from '../catalog';
import StreamPicker, { streamName } from '../components/StreamPicker';
import { t } from '../i18n';
import { peekExplorePref, setCoursesPref, setExplorePref, setTextbookPref } from '../prefs';
import type { Availability, Lang } from '../types';

const GRADES = Array.from({ length: 12 }, (_, i) => i + 1);
const BOARDS = ['Maharashtra SSC', 'Maharashtra HSC', 'CBSE'];

/**
 * The one direct spine of the app: Class → Board → Medium → subjects that
 * actually have something → straight into books or lessons. Every chip and
 * card is rendered from /catalog/availability, so this page can never offer
 * a combination that ends in an empty result — the honest fix for "not every
 * class has every medium's book in every subject".
 */
export default function Explore({ lang, go, routeGrade, user }: {
  lang: Lang;
  go: (p: string, id?: number) => void;
  routeGrade?: number;
  user: { class_grade: number | null; board: string | null } | null;
}) {
  const saved = peekExplorePref();
  const [grade, setGrade] = useState<number>(
    routeGrade ?? saved?.grade ?? user?.class_grade ?? 8);
  const [board, setBoard] = useState<string>(
    saved?.board ?? user?.board ?? 'Maharashtra SSC');
  const [med, setMed] = useState(''); // selected medium lang, '' = all mediums
  const [stream, setStream] = useState(saved?.stream ?? ''); // 11-12 lane, '' = all
  const [data, setData] = useState<Availability | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);

  // A deep link (#/explore/7 from a class card) wins over session memory.
  useEffect(() => { if (routeGrade) setGrade(routeGrade); }, [routeGrade]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError('');
    setExplorePref({ grade, board, stream: stream || undefined });
    apiAvailability(board, grade)
      .then((a) => {
        if (!live) return;
        setData(a);
        // Keep the medium only if this combo still has it, else fall back to
        // the first available medium (or none — the page still works).
        setMed((m) => (m && a.mediums.some((x) => x.lang === m))
          ? m
          : (a.mediums[0]?.lang ?? ''));
        // Same for the stream lane: a stale lane must never filter everything out.
        setStream((s) => (s && a.streams.some((x) => x.code === s)) ? s : '');
      })
      .catch(() => { if (live) setError(t('errorLoad', lang)); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [grade, board, lang, reload]);

  const pickGrade = (g: number) => { setGrade(g); location.hash = `/explore/${g}`; };

  const openBooks = (subject: string) => {
    setTextbookPref({
      grade, board, subject,
      lang: med || undefined,
      stream: stream || undefined,
    });
    go('textbooks');
  };

  const startLessons = (subjectId: number | null, courseIds: number[]) => {
    // One course → straight into it; several → the filtered course list.
    if (courseIds.length === 1 || !subjectId) {
      go('course', courseIds[0]);
      return;
    }
    setCoursesPref({ grade, board, subjectId, stream: stream || undefined });
    go('courses');
  };

  // Stream lane first (common subjects always pass), then the medium filter.
  const subjects = data
    ? visibleSubjects(data, med).filter((s) => !stream || s.stream === '' || s.stream === stream)
    : [];

  return (
    <div>
      <h1>🧭 {t('explore', lang)}</h1>
      <p className="muted">{t('exploreHint', lang)}</p>

      <div className="card" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8 }}>
        <select value={grade} onChange={(e) => pickGrade(Number(e.target.value))} aria-label="Class">
          {GRADES.map((g) => <option key={g} value={g}>Class {g}</option>)}
        </select>
        <select value={board} onChange={(e) => setBoard(e.target.value)} aria-label="Board">
          {BOARDS.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
      </div>

      {data && data.mediums.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '12px 0', alignItems: 'center' }}>
          <span className="muted">{t('medium', lang)}:</span>
          <button className={`btn small ${med === '' ? 'accent' : 'ghost'}`}
            onClick={() => setMed('')}>{t('allMediums', lang)}</button>
          {data.mediums.map((m) => (
            <button key={m.lang} className={`btn small ${med === m.lang ? 'accent' : 'ghost'}`}
              onClick={() => setMed(m.lang)}>
              {m.label} · 📖 {m.books}
            </button>
          ))}
        </div>
      )}

      {data && <StreamPicker lang={lang} streams={data.streams} value={stream} onChange={setStream} />}

      {loading && <div><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>}
      {error && (
        <p className="error">
          {error}{' '}
          <button className="btn small ghost" onClick={() => setReload((r) => r + 1)}>
            {t('retry', lang)}
          </button>
        </p>
      )}

      {!loading && !error && data && (
        subjects.length === 0 ? (
          <div className="empty-state">
            <div className="icon">🧭</div>
            <p>{t('noContent', lang)}</p>
            <a className="btn ghost" href="#/textbooks">{t('textbooks', lang)}</a>
          </div>
        ) : (
          <div className="grid-cards">
            {subjects.map((s) => {
              const books = booksIn(s, med);
              return (
                <div className="card" key={s.name}>
                  <strong>{subjectLabel(s, lang)}</strong>
                  <div style={{ margin: '6px 0' }}>
                    {s.stream && <span className="badge">{streamName(s.stream, lang)}</span>}
                    {books > 0 && <span className="badge green">📖 {books} {t('books', lang)}</span>}
                    {s.lessons > 0 && <span className="badge">🎓 {s.lessons} {t('lessons', lang)}</span>}
                    {books === 0 && s.courses > 0 && (
                      <span className="badge gray">{t('noBooksMedium', lang)}</span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                    {books > 0 && (
                      <button className="btn small" onClick={() => openBooks(s.name)}>
                        📖 {t('openBooks', lang)}
                      </button>
                    )}
                    {s.course_ids.length > 0 && (
                      <button className="btn small accent"
                        onClick={() => startLessons(s.subject_id, s.course_ids)}>
                        🎓 {s.lessons > 0 ? t('startLessons', lang) : t('openCourse', lang)}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )
      )}
    </div>
  );
}
