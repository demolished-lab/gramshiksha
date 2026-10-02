import { useEffect, useState } from 'react';
import { apiAvailability, apiTextbookOpenUrl, apiTextbookPortals, apiTextbooks } from '../api';
import { booksIn, subjectLabel } from '../catalog';
import { t } from '../i18n';
import { takeTextbookPref } from '../prefs';
import type { Availability, Lang, Textbook } from '../types';

const BOARDS = ['Maharashtra SSC', 'Maharashtra HSC', 'CBSE'];
const GRADES = Array.from({ length: 12 }, (_, i) => i + 1);

interface Portal { name: string; url: string; boards: string[]; langs: string[] }

/**
 * Every option in the two content filters (medium, subject) is derived from
 * /catalog/availability for the chosen class+board — not from fixed lists —
 * so this page can never offer a medium or subject that has zero books, and
 * an explore-hub pick opens it pre-filtered (takeTextbookPref).
 */
export default function Textbooks({ lang, user }: { lang: Lang; user: { class_grade: number | null; board: string | null } | null }) {
  const pref = takeTextbookPref();
  const [grade, setGrade] = useState<number>(pref?.grade ?? user?.class_grade ?? 8);
  const [board, setBoard] = useState<string>(pref?.board ?? user?.board ?? 'Maharashtra SSC');
  const [bookLang, setBookLang] = useState<string>(pref?.lang ?? '');
  const [subject, setSubject] = useState<string>(pref?.subject ?? '');
  const [avail, setAvail] = useState<Availability | null>(null);
  const [books, setBooks] = useState<Textbook[]>([]);
  const [portals, setPortals] = useState<Portal[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { apiTextbookPortals().then(setPortals).catch(() => setPortals([])); }, []);

  useEffect(() => {
    let live = true;
    apiAvailability(board, grade)
      .then((a) => { if (live) setAvail(a); })
      .catch(() => { if (live) setAvail(null); });
    return () => { live = false; };
  }, [grade, board]);

  // Drop filter choices the new combo doesn't have: a medium with no books
  // here, or a subject with no books in the selected medium.
  useEffect(() => {
    if (!avail) return;
    if (bookLang && !avail.mediums.some((m) => m.lang === bookLang)) setBookLang('');
  }, [avail, bookLang]);
  useEffect(() => {
    if (!avail) return;
    if (subject && !avail.subjects.some((s) => booksIn(s, bookLang) > 0 && s.name === subject)) {
      setSubject('');
    }
  }, [avail, bookLang, subject]);

  useEffect(() => {
    setLoading(true);
    apiTextbooks(grade, board, bookLang || null, subject || null)
      .then(setBooks).catch(() => setBooks([]))
      .finally(() => setLoading(false));
  }, [grade, board, bookLang, subject]);

  const relevantPortals = portals.filter((p) => p.boards.includes(board));
  const mediumOptions = avail?.mediums ?? [];
  const subjectOptions = (avail?.subjects ?? []).filter((s) => booksIn(s, bookLang) > 0);
  const totalBooks = mediumOptions.reduce((n, m) => n + m.books, 0);

  return (
    <div>
      <h1>📕 {t('textbooks', lang)}</h1>
      <p className="muted">Official textbooks only — we link to the government portals; files are not re-hosted here.</p>
      <div className="card" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8 }}>
        <select value={grade} onChange={(e) => { setGrade(Number(e.target.value)); setSubject(''); }} aria-label="Class">
          {GRADES.map((g) => <option key={g} value={g}>Class {g}</option>)}
        </select>
        <select value={board} onChange={(e) => { setBoard(e.target.value); setSubject(''); }} aria-label="Board">
          {BOARDS.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
        <select value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject"
          disabled={!subjectOptions.length && !subject}>
          <option value="">All subjects ({subjectOptions.length})</option>
          {subjectOptions.map((s) => (
            <option key={s.name} value={s.name}>
              {subjectLabel(s, lang)} ({booksIn(s, bookLang)})
            </option>
          ))}
        </select>
        <select value={bookLang} onChange={(e) => setBookLang(e.target.value)} aria-label="Medium">
          <option value="">{t('allMediums', lang)} ({totalBooks})</option>
          {mediumOptions.map((m) => (
            <option key={m.lang} value={m.lang}>{m.label} ({m.books})</option>
          ))}
        </select>
      </div>

      {!loading && (
        <p className="muted" style={{ margin: '8px 2px' }}>
          {books.length} book{books.length === 1 ? '' : 's'} · Class {grade} · {board}
          {subject ? ` · ${subject}` : ''}
        </p>
      )}

      {loading && <div><div className="skeleton" /><div className="skeleton" /></div>}
      {!loading && !books.length && (
        <div className="empty-state">
          <div className="icon">📕</div>
          <p>No textbooks match this filter — try “All subjects/languages”, or open the official portal below.</p>
        </div>
      )}
      {books.map((b) => (
        <div className="card" key={b.id}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            {b.cover_url && (
              <img src={b.cover_url} alt="" loading="lazy" width={56}
                style={{ borderRadius: 4, boxShadow: '0 1px 4px rgba(0,0,0,.2)' }} />
            )}
            <div>
              <strong>{b.title}</strong>
              <div style={{ margin: '4px 0' }}>
                <span className="badge">{b.board}</span>
                <span className="badge gray">Class {b.class_grade}</span>
                <span className="badge green">{b.subject_name}</span>
                <span className="badge orange">{b.lang}</span>
                {b.has_deep_link && <span className="badge">📄 direct PDF</span>}
              </div>
              <a className="btn small" href={apiTextbookOpenUrl(b.id)} target="_blank" rel="noreferrer">
                🔗 {b.has_deep_link ? 'Open PDF' : `Open at ${b.publisher} source`}
              </a>
            </div>
          </div>
        </div>
      ))}

      <h2 style={{ marginTop: 20 }}>🏛️ Official sources (always available)</h2>
      <p className="muted">If a book link is missing, get it free directly from the government portal:</p>
      {(relevantPortals.length ? relevantPortals : portals).map((p) => (
        <div className="card" key={p.name}>
          <strong>{p.name}</strong>
          <div style={{ margin: '4px 0' }}>
            {p.boards.map((b) => <span key={b} className="badge">{b}</span>)}
          </div>
          <a className="btn small" href={p.url} target="_blank" rel="noreferrer">🔗 {p.url}</a>
        </div>
      ))}
    </div>
  );
}
