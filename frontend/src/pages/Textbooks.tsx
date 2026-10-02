import { useEffect, useState } from 'react';
import { apiAvailability, apiSubjects, apiTextbookOpenUrl, apiTextbookPortals, apiTextbooks } from '../api';
import { booksIn, subjectLabel } from '../catalog';
import { pick, t } from '../i18n';
import { takeTextbookPref } from '../prefs';
import type { Availability, Lang, Subject, Textbook } from '../types';

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
  const [legacy, setLegacy] = useState<Subject[] | null>(null);
  const [books, setBooks] = useState<Textbook[]>([]);
  const [portals, setPortals] = useState<Portal[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { apiTextbookPortals().then(setPortals).catch(() => setPortals([])); }, []);

  useEffect(() => {
    let live = true;
    setAvail(null);
    setLegacy(null);
    apiAvailability(board, grade)
      .then((a) => { if (live) setAvail(a); })
      .catch(() => {
        // Availability unreachable (old backend mid-deploy, network blip) —
        // fall back to the legacy generic filters rather than render empty,
        // disabled dropdowns. The book list below still loads either way.
        if (!live) return;
        apiSubjects(grade, board)
          .then((rows) => { if (live) setLegacy(rows); })
          .catch(() => { if (live) setLegacy([]); });
      });
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
  const totalBooks = avail ? avail.mediums.reduce((n, m) => n + m.books, 0) : null;
  // Availability mode: only combinations with real books. Legacy fallback
  // (availability unreachable): the original generic lists, never empty.
  const subjectRows: { value: string; label: string }[] = avail
    ? avail.subjects.filter((s) => booksIn(s, bookLang) > 0).map((s) => ({
        value: s.name,
        label: `${subjectLabel(s, lang)} (${booksIn(s, bookLang)})`,
      }))
    : (legacy ?? []).map((s) => ({
        value: s.name_en,
        label: pick(lang, s.name_en, s.name_hi, s.name_mr),
      }));
  const mediumRows: { value: string; label: string }[] = avail
    ? avail.mediums.map((m) => ({ value: m.lang, label: `${m.label} (${m.books})` }))
    : [{ value: 'en', label: 'English' }, { value: 'hi', label: 'हिंदी' }, { value: 'mr', label: 'मराठी' }];

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
          disabled={!subjectRows.length && !subject}>
          <option value="">All subjects ({subjectRows.length})</option>
          {subjectRows.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <select value={bookLang} onChange={(e) => setBookLang(e.target.value)} aria-label="Medium">
          <option value="">{t('allMediums', lang)}{totalBooks !== null ? ` (${totalBooks})` : ''}</option>
          {mediumRows.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
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
      {/* e-book library grid: full-height cover tiles with a direct action
          per book (mirrors the official portals' layout). Deep-linked books
          get the orange Download button; the rest fall back to their source
          portal, visibly de-emphasised. Board/class context lives in the
          filter bar above — cards stay scannable. */}
      {!!books.length && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 14, marginTop: 10 }}>
          {books.map((b) => (
            <div className="card" key={b.id} style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {b.cover_url ? (
                <img src={b.cover_url} alt="" loading="lazy" decoding="async" className="cover-shimmer"
                  style={{ width: '100%', aspectRatio: '3 / 4', objectFit: 'cover', borderRadius: 6 }} />
              ) : (
                <div role="img" aria-label={`${b.subject_name} cover`}
                  style={{ aspectRatio: '3 / 4', borderRadius: 6, background: '#EFF6FF', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 44 }}>
                  📚
                </div>
              )}
              <div title={b.title}
                style={{ fontSize: '.86rem', lineHeight: 1.35, fontWeight: 600, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                {b.title}
              </div>
              <div className="muted" style={{ fontSize: '.74rem' }}>
                {b.subject_name} · {b.lang.toUpperCase()}{b.part_label ? ` · ${b.part_label}` : ''}{b.has_deep_link ? ' · 📄' : ''}
              </div>
              <a className={`btn small ${b.has_deep_link ? 'accent' : 'ghost'}`}
                href={apiTextbookOpenUrl(b.id)} target="_blank" rel="noreferrer"
                style={{ justifyContent: 'center', width: '100%' }}>
                {b.has_deep_link ? `⬇ ${t('download', lang)}` : `🔗 ${b.publisher} source`}
              </a>
            </div>
          ))}
        </div>
      )}

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
