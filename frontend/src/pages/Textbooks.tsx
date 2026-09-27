import { useEffect, useState } from 'react';
import { apiTextbooks } from '../api';
import { t } from '../i18n';
import type { Lang, Textbook } from '../types';

const BOARDS = ['Maharashtra SSC', 'Maharashtra HSC', 'CBSE'];
const GRADES = Array.from({ length: 12 }, (_, i) => i + 1);

export default function Textbooks({ lang, user }: { lang: Lang; user: { class_grade: number | null; board: string | null } | null }) {
  const [grade, setGrade] = useState<number>(user?.class_grade ?? 8);
  const [board, setBoard] = useState(user?.board ?? 'Maharashtra SSC');
  const [bookLang, setBookLang] = useState('');
  const [books, setBooks] = useState<Textbook[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    apiTextbooks(grade, board, bookLang || null)
      .then(setBooks).catch(() => setBooks([]))
      .finally(() => setLoading(false));
  }, [grade, board, bookLang]);

  return (
    <div>
      <h1>📕 {t('textbooks', lang)}</h1>
      <p className="muted">Official textbooks only — we link to the government portals; files are not re-hosted here.</p>
      <div className="card" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8 }}>
        <select value={grade} onChange={(e) => setGrade(Number(e.target.value))} aria-label="Class">
          {GRADES.map((g) => <option key={g} value={g}>Class {g}</option>)}
        </select>
        <select value={board} onChange={(e) => setBoard(e.target.value)} aria-label="Board">
          {BOARDS.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
        <select value={bookLang} onChange={(e) => setBookLang(e.target.value)} aria-label="Language">
          <option value="">All languages</option>
          <option value="en">English</option>
          <option value="hi">हिंदी</option>
          <option value="mr">मराठी</option>
        </select>
      </div>

      {loading && <div><div className="skeleton" /><div className="skeleton" /></div>}
      {!loading && !books.length && (
        <div className="empty-state"><div className="icon">📕</div><p>No textbooks listed for this selection — check ePathshala directly.</p></div>
      )}
      {books.map((b) => (
        <div className="card" key={b.id}>
          <strong>{b.title}</strong>
          <div style={{ margin: '4px 0' }}>
            <span className="badge">{b.board}</span>
            <span className="badge gray">Class {b.class_grade}</span>
            <span className="badge green">{b.subject_name}</span>
            <span className="badge orange">{b.lang}</span>
          </div>
          <a className="btn small" href={b.source_url} target="_blank" rel="noreferrer">
            🔗 Open at {b.publisher} source
          </a>
        </div>
      ))}
    </div>
  );
}
