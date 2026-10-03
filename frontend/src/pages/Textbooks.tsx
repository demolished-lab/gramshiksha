import { useEffect, useState } from 'react';
import { apiAvailability, apiLocate, apiMyRequests, apiReadingList, apiSubjects, apiTextbookOpenUrl, apiTextbooks } from '../api';
import { booksIn, subjectLabel } from '../catalog';
import { monthLabel, pick, t } from '../i18n';
import StreamPicker, { streamName } from '../components/StreamPicker';
import { takeTextbookPref } from '../prefs';
import type { Availability, BookAsk, Lang, ReadingPick, Subject, Textbook } from '../types';

const BOARDS = ['Maharashtra SSC', 'Maharashtra HSC', 'CBSE'];
const GRADES = Array.from({ length: 12 }, (_, i) => i + 1);

/** Smart Book Finder's local state. Only `scanning` ever waits on the
 * network: local filtering is instant, and everything else is a final
 * result the panel can render — found (read it now) or queued (you have a
 * position). The countdown is the honest ETA a scan of this scope takes,
 * not a spinner that never resolves. */
type Finder =
  | { kind: 'idle' }
  | { kind: 'scanning'; left: number }
  | { kind: 'found'; books: Textbook[]; official: boolean }
  | { kind: 'queued'; position: number }
  | { kind: 'error'; message: string };

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
  const [stream, setStream] = useState<string>(pref?.stream ?? '');
  const [avail, setAvail] = useState<Availability | null>(null);
  const [legacy, setLegacy] = useState<Subject[] | null>(null);
  const [books, setBooks] = useState<Textbook[]>([]);
  const [loading, setLoading] = useState(false);

  // Smart Book Finder + in-app viewer
  // `pref.q` seeds the box: "Find this book" on a reading-list pick lands here
  // with the title already chosen (and runs once, below).
  const [query, setQuery] = useState(pref?.q ?? '');
  const [reload, setReload] = useState(0);
  const [finder, setFinder] = useState<Finder>({ kind: 'idle' });
  const [asks, setAsks] = useState<BookAsk[]>([]);
  const [picks, setPicks] = useState<ReadingPick[]>([]);
  // The reader needs only what it shows: an id for the frame and a title for
  // the bar. A reading-list pick carries both, so it can open without first
  // re-fetching a whole Textbook row.
  const [viewer, setViewer] = useState<{ id: number; title: string } | null>(null);
  const [frameReady, setFrameReady] = useState(false);

  const signedIn = !!user;

  // The Monthly Reading List is public (book club), so a visitor sees it too.
  useEffect(() => { apiReadingList().then(setPicks).catch(() => setPicks([])); }, []);

  useEffect(() => {
    if (!signedIn) return;
    // My earlier asks, so a queued book is still visible after a reload.
    // Anonymous visitors simply skip this — a 401 here is not an error state.
    apiMyRequests().then(setAsks).catch(() => setAsks([]));
  }, [signedIn]);

  useEffect(() => {
    let live = true;
    setAvail(null);
    setLegacy(null);
    apiAvailability(board, grade)
      .then((a) => {
        if (!live) return;
        setAvail(a);
        // A stale stream lane must never filter everything out.
        setStream((s) => (s && a.streams.some((x) => x.code === s)) ? s : '');
      })
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
    apiTextbooks(grade, board, bookLang || null, subject || null, stream || null)
      .then(setBooks).catch(() => setBooks([]))
      .finally(() => setLoading(false));
  }, [grade, board, bookLang, subject, stream, reload]);

  // ETA countdown while the official portal is being scanned server-side.
  useEffect(() => {
    if (finder.kind !== 'scanning') return;
    const id = window.setInterval(() => {
      setFinder((f) => (f.kind === 'scanning' ? { ...f, left: Math.max(0, f.left - 1) } : f));
    }, 1000);
    return () => window.clearInterval(id);
  }, [finder.kind]);

  // Escape closes the viewer — same contract as the login dialog.
  useEffect(() => {
    if (!viewer) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setViewer(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [viewer]);

  /** Tier 1+2+3 happens server-side; the UI only ever shows a final state.
   * A miss is not an error — it is a queue position with an honest ETA.
   * `termIn`/`scope` come from "Find this book", where the title and class
   * belong to a reading-list pick rather than to this page's filters. */
  const runFinder = async (termIn?: string, scope?: { grade: number; board: string; lang: string; stream?: string }) => {
    const term = (termIn ?? query).trim();
    if (term.length < 2 || finder.kind === 'scanning') return;
    const g = scope?.grade ?? grade;
    const b = scope?.board ?? board;
    const l = scope?.lang ?? bookLang;
    const s = scope?.stream ?? stream;
    setFinder({ kind: 'scanning', left: l ? 10 : 30 });
    try {
      const res = await apiLocate(term, g, b, l, s || undefined);
      if (res.result === 'found') {
        setFinder({ kind: 'found', books: res.books ?? [], official: res.source === 'official' });
        if (res.source === 'official') setReload((n) => n + 1); // it is now in this class
      } else {
        setFinder({ kind: 'queued', position: res.position ?? 1 });
        if (signedIn) apiMyRequests().then(setAsks).catch(() => {});
      }
    } catch (e) {
      setFinder({ kind: 'error', message: e instanceof Error ? e.message : String(e) });
    }
  };

  // Arrived from "Read"/"Find this book" on a reading-list pick (the
  // dashboard card): open the book, or seed and run the search once, then
  // bring the panel into view. The box is already seeded (useState above).
  useEffect(() => {
    if (pref?.open) {
      setFrameReady(false);
      setViewer({ id: pref.open, title: pref.q ?? '' });
      return;
    }
    if (!pref?.q) return;
    void runFinder(pref.q, {
      grade: pref.grade ?? grade,
      board: pref.board || board,
      lang: pref.lang ?? '',
      stream: pref.stream ?? '',
    });
    document.getElementById('finder')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openBook = (b: Textbook) => { setFrameReady(false); setViewer(b); };

  /** "Read now" on a pick whose catalog row has a healthy PDF. */
  const openPick = (p: ReadingPick) => {
    if (!p.textbook_id) return;
    setFrameReady(false);
    setViewer({ id: p.textbook_id, title: p.title });
  };

  /** "Find this book" on a pick: adopt the pick's class/board/medium/lane so
   * the portal scan (tier 2) looks in the right place, then search right
   * here — never a redirect, only a final result in the panel below. */
  const findThisBook = (p: ReadingPick) => {
    const scope = {
      grade: p.class_grade ?? grade,
      board: p.board || board,
      lang: p.lang || bookLang,
      stream: p.stream || stream,
    };
    setGrade(scope.grade);
    setBoard(scope.board);
    setBookLang(scope.lang);
    setStream(scope.stream);
    setQuery(p.title);
    setFinder({ kind: 'idle' });
    void runFinder(p.title, scope);
    document.getElementById('finder')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  /** "Find this book" on a catalog row with no verified PDF yet: the same
   * scoped portal scan + queue as the finder, run right here — the card
   * never navigates anywhere. */
  const findBook = (b: Textbook) => {
    setQuery(b.title);
    setFinder({ kind: 'idle' });
    void runFinder(b.title, { grade, board, lang: bookLang, stream });
    document.getElementById('finder')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  /** Deterministic subject hue for the cover tile painted behind the CDN
   * raster (and left standing when the row has no cover or it fails). */
  const coverHue = (subject: string) => {
    let h = 0;
    for (const c of subject) h = (h * 31 + c.charCodeAt(0)) % 360;
    return h;
  };

  const totalBooks = avail ? avail.mediums.reduce((n, m) => n + m.books, 0) : null;
  // Availability mode: only combinations with real books. Legacy fallback
  // (availability unreachable): the original generic lists, never empty.
  const subjectRows: { value: string; label: string }[] = avail
    ? avail.subjects
      .filter((s) => booksIn(s, bookLang) > 0)
      .filter((s) => !stream || s.stream === '' || s.stream === stream)
      .map((s) => ({
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

  // Instant local filter: typing never waits on the network.
  const term = query.trim().toLowerCase();
  const shown = term
    ? books.filter((b) => b.title.toLowerCase().includes(term)
      || b.subject_name.toLowerCase().includes(term))
    : books;

  return (
    <div>
      <h1>📕 {t('textbooks', lang)}</h1>
      <p className="muted">Official textbooks only — files stream straight from the government portals into the reader below, never re-hosted here.</p>

      {/* Monthly Reading List — a book club, not homework: every student sees
          every teacher's pick. A pick that is already in the catalog opens the
          in-app reader; one that isn't hands its title to the Smart Book
          Finder below (never a dead end, never a redirect). */}
      {!!picks.length && (
        <div className="card reading-banner">
          <div className="reading-head">
            <strong>📚 {t('readingList', lang)} · {monthLabel(picks[0].month, lang)}</strong>
            <span className="muted">{t('readingClubHint', lang)}</span>
          </div>
          {picks.slice(0, 4).map((p) => (
            <div className="reading-row" key={p.id}>
              <div className="reading-text">
                <div className="reading-title">
                  {p.title}
                  {p.author && <span className="muted"> · {p.author}</span>}
                </div>
                <div className="muted reading-meta">
                  {p.teacher_name}
                  {p.subject_name ? ` · ${p.subject_name}` : ''}
                  {p.stream ? ` · ${streamName(p.stream, lang)}` : ''}
                  {p.lang ? ` · ${p.lang.toUpperCase()}` : ''}
                  {p.month !== picks[0].month ? ` · ${monthLabel(p.month, lang)}` : ''}
                </div>
                {p.note && <p className="reading-note">{p.note}</p>}
              </div>
              {p.readable && p.textbook_id ? (
                <button type="button" className="btn small accent" onClick={() => openPick(p)}>
                  📖 {t('read', lang)}
                </button>
              ) : (
                <button type="button" className="btn small" onClick={() => findThisBook(p)}>
                  🔎 {t('findThisBook', lang)}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Smart Book Finder: instant filter of this class, then (on request)
          a background scan of the official portal with an honest ETA. */}
      <div className="card" id="finder">
        <strong>{t('finder', lang)}</strong>
        <div className="finder">
          <input value={query} onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void runFinder(); }}
            placeholder={t('searchBooks', lang)} aria-label={t('searchBooks', lang)} />
          <button type="button" className="btn" onClick={() => void runFinder()}
            disabled={query.trim().length < 2 || finder.kind === 'scanning'}>
            🔎 {t('finder', lang)}
          </button>
        </div>
        <p className="muted" style={{ margin: '8px 0 0' }}>{t('finderHint', lang)}</p>

        {finder.kind === 'scanning' && (
          <div className="finder-panel">
            <div className="finder-step">⏳ {t('scanning', lang)}</div>
            <div className="muted">
              {finder.left > 0 ? `~${finder.left}s` : t('checking', lang)}
            </div>
          </div>
        )}
        {finder.kind === 'found' && (
          <div className="finder-panel">
            <div className="finder-step">
              ✅ {finder.official ? t('foundOfficial', lang) : `${finder.books.length} ${t('books', lang)}`}
            </div>
            {finder.books.map((b) => (
              <div className="finder-row" key={b.id}>
                <span title={b.title}>
                  {b.title}
                  <span className="muted"> · {b.subject_name} · {b.lang.toUpperCase()}{b.part_label ? ` · ${b.part_label}` : ''}</span>
                </span>
                {b.has_deep_link ? (
                  <button type="button" className="btn small accent" onClick={() => openBook(b)}>
                    📖 {t('read', lang)}
                  </button>
                ) : (
                  <button type="button" className="btn small ghost" onClick={() => findBook(b)}>
                    🔎 {t('findThisBook', lang)}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        {finder.kind === 'queued' && (
          <div className="finder-panel">
            <div className="finder-step">
              🕒 {t('queuedMsg', lang).replace('{n}', String(finder.position))}
            </div>
            {!!asks.length && (
              <div>
                <div className="muted">{t('myRequests', lang)}</div>
                {asks.map((a) => (
                  <div className="finder-row" key={a.id}>
                    <span title={a.query}>{a.query}</span>
                    <span className={`badge ${a.status === 'found' ? 'green' : 'gray'}`}>{a.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {finder.kind === 'error' && <p className="error">{finder.message}</p>}
      </div>

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
      {avail && <StreamPicker lang={lang} streams={avail.streams} value={stream} onChange={setStream} />}

      {!loading && (
        <p className="muted" style={{ margin: '8px 2px' }}>
          {shown.length} book{shown.length === 1 ? '' : 's'} · Class {grade} · {board}
          {subject ? ` · ${subject}` : ''}
          {term ? ` · “${query.trim()}”` : ''}
        </p>
      )}

      {loading && <div><div className="skeleton" /><div className="skeleton" /></div>}
      {!loading && !shown.length && (
        <div className="empty-state">
          <div className="icon">📕</div>
          <p>
            {term
              ? `${t('notHere', lang)} — “${query.trim()}”`
              : 'No textbooks match this filter — try “All subjects/languages”, or run the Smart Book Finder above.'}
          </p>
        </div>
      )}
      {/* e-book library grid: full-height cover tiles with a direct action
          per book (mirrors the official portals' layout). Deep-linked books
          open in the in-app reader — the PDF is proxied by our backend, so
          the browser never visibly leaves this site. Rows without a verified
          PDF run the Smart Book Finder in-page instead of linking out.
          Board/class context lives in the filter bar above — cards stay
          scannable. */}
      {!!shown.length && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 14, marginTop: 10 }}>
          {shown.map((b) => (
            <div className="card" key={b.id} style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div className="cover-wrap">
                <div className="cover-fallback"
                  style={{ background: `linear-gradient(160deg, hsl(${coverHue(b.subject_name)}, 65%, 88%), hsl(${(coverHue(b.subject_name) + 40) % 360}, 60%, 94%)` }}>
                  <span className="cover-ic" aria-hidden="true">📚</span>
                  <span className="cover-sub">{b.subject_name}</span>
                </div>
                {b.cover_url && (
                  <img src={b.cover_url} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer"
                    onError={(e) => { e.currentTarget.remove(); }} />
                )}
              </div>
              <div title={b.title}
                style={{ fontSize: '.86rem', lineHeight: 1.35, fontWeight: 600, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                {b.title}
              </div>
              <div className="muted" style={{ fontSize: '.74rem' }}>
                {b.subject_name} · {b.lang.toUpperCase()}{b.part_label ? ` · ${b.part_label}` : ''}{b.has_deep_link ? ' · 📄' : ''}
              </div>
              {b.stream && <div><span className="badge">{streamName(b.stream, lang)}</span></div>}
              {b.has_deep_link ? (
                <button type="button" className="btn small accent"
                  onClick={() => openBook(b)}
                  style={{ justifyContent: 'center', width: '100%' }}>
                  📖 {t('read', lang)}
                </button>
              ) : (
                <button type="button" className="btn small ghost" onClick={() => findBook(b)}
                  style={{ justifyContent: 'center', width: '100%' }}>
                  🔎 {t('findThisBook', lang)}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* In-app reader: a same-origin frame of /textbooks/{id}/open, which
          the backend answers with the PDF itself (200, application/pdf). */}
      {viewer && (
        <div className="viewer" role="dialog" aria-modal="true" aria-label={viewer.title}
          onClick={() => setViewer(null)}>
          <div className="viewer-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="viewer-bar">
              <strong title={viewer.title}>{viewer.title}</strong>
              <a className="btn small" href={apiTextbookOpenUrl(viewer.id, 'dl')}>
                ⬇ {t('saveFile', lang)}
              </a>
              <button type="button" className="btn small ghost" onClick={() => setViewer(null)}>
                ✕ {t('close', lang)}
              </button>
            </div>
            {!frameReady && (
              <div className="viewer-loading">
                <div className="skeleton" />
                <p className="muted">{t('opening', lang)}</p>
              </div>
            )}
            <iframe className="viewer-frame" title={viewer.title}
              src={apiTextbookOpenUrl(viewer.id)}
              onLoad={() => setFrameReady(true)} />
          </div>
        </div>
      )}
    </div>
  );
}
