import { useEffect, useMemo, useRef, useState } from 'react';
import { apiStudioExtract } from '../api';
import { t } from '../i18n';
import type { SessionUser } from '../auth';
import type { Lang } from '../types';
import { buildStudyPack, packHtml, type StudyPack } from '../studio';
import { driveImportEnabled, exportGoogleDoc, googleClientId, pickGoogleDoc, requestDriveToken } from '../googleDrive';
import InstallPrompt from '../components/InstallPrompt';

type Tab = 'overview' | 'flashcards' | 'quiz' | 'checklist';

const STORAGE_PREFIX = 'gs_studio_packs_v1';
const MAX_PACKS = 20;
const SAMPLE = `Photosynthesis
Photosynthesis is the process by which green plants make their own food using sunlight, water and carbon dioxide.
Chlorophyll: the green pigment in leaves that absorbs sunlight.
Stomata: tiny pores on a leaf that let carbon dioxide in and oxygen out.
The reaction takes place in the chloroplast.
- Plants need sunlight, water and carbon dioxide.
- Chlorophyll absorbs light energy.
- Oxygen is released as a by-product.
- Glucose is stored as starch.
Question: Why are leaves green?
Answer: Chlorophyll reflects green light and absorbs the other colours.`;

const keyFor = (user: SessionUser): string =>
  `${STORAGE_PREFIX}:${user.name.slice(0, 40)}:${user.role}`;

function readPacks(key: string): StudyPack[] {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is StudyPack =>
      Boolean(item) && typeof item === 'object'
      && typeof (item as StudyPack).id === 'string'
      && typeof (item as StudyPack).title === 'string'
      && Array.isArray((item as StudyPack).keyPoints)
      && Array.isArray((item as StudyPack).flashcards));
  } catch {
    return [];
  }
}

function writePacks(key: string, packs: StudyPack[]): void {
  try {
    localStorage.setItem(key, JSON.stringify(packs.slice(0, MAX_PACKS)));
  } catch {
    // A full or private-mode storage must not break the page; the pack still
    // works for this session and can be downloaded as HTML.
  }
}

const safeFile = (title: string): string =>
  `${title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'study-pack'}.html`;

const validHttpUrl = (value: string): boolean => {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
};

export default function Studio({ lang, user }: { lang: Lang; user: SessionUser }) {
  const storageKey = useMemo(() => keyFor(user), [user]);
  const [packs, setPacks] = useState<StudyPack[]>(() => readPacks(storageKey));
  const [activeId, setActiveId] = useState<string | null>(() => readPacks(storageKey)[0]?.id ?? null);
  const [tab, setTab] = useState<Tab>('overview');
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [flipped, setFlipped] = useState<Record<number, boolean>>({});
  const [openAnswers, setOpenAnswers] = useState<Record<number, boolean>>({});
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const driveOn = driveImportEnabled();
  const [driveToken, setDriveToken] = useState('');
  const [driveBusy, setDriveBusy] = useState(false);
  const [driveError, setDriveError] = useState('');

  useEffect(() => {
    setPacks(readPacks(storageKey));
    setActiveId(readPacks(storageKey)[0]?.id ?? null);
    setTab('overview');
  }, [storageKey]);

  useEffect(() => {
    // Android's Web Share Target opens /studio?title=…&text=…&url=… after the
    // learner taps "Share → GramShiksha" in their own NotebookLM app. Read it
    // once, prefill the import form, then clean the address bar.
    const params = new URLSearchParams(window.location.search);
    const sharedTitle = (params.get('title') ?? '').slice(0, 120);
    const sharedText = (params.get('text') ?? '').slice(0, 120_000);
    const sharedUrl = (params.get('url') ?? '').slice(0, 500);
    if (!sharedTitle && !sharedText && !sharedUrl) return;
    if (sharedTitle) setTitle(sharedTitle);
    if (sharedText) setText(sharedText);
    if (validHttpUrl(sharedUrl)) setSourceUrl(sharedUrl);
    setToast(sharedText.trim().length >= 40
      ? 'Shared from your device. Review it, then build your pack.'
      : 'Link added. Paste the notes text from NotebookLM to build a pack.');
    window.history.replaceState(null, '', window.location.pathname);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(''), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const active = packs.find((pack) => pack.id === activeId) ?? null;

  const persist = (next: StudyPack[]) => {
    setPacks(next);
    writePacks(storageKey, next);
  };

  const updateActive = (patch: Partial<StudyPack>) => {
    if (!active) return;
    persist(packs.map((pack) => pack.id === active.id ? { ...pack, ...patch } : pack));
  };

  const build = () => {
    setError('');
    const cleanText = text.trim();
    if (cleanText.length < 40) {
      setError('Paste at least a short paragraph or a few bullet points first.');
      return;
    }
    setBusy(true);
    try {
      const pack = buildStudyPack({
        title: title.trim() || cleanText.split('\n')[0].slice(0, 90),
        text: cleanText,
        sourceUrl: validHttpUrl(sourceUrl.trim()) ? sourceUrl.trim() : '',
      });
      const next = [pack, ...packs].slice(0, MAX_PACKS);
      persist(next);
      setActiveId(pack.id);
      setTab('overview');
      setFlipped({});
      setOpenAnswers({});
      setTitle('');
      setText('');
      setSourceUrl('');
      setToast('Study pack created on this device.');
    } catch {
      setError('This text could not be turned into a pack. Try copying a little more detail.');
    } finally {
      setBusy(false);
    }
  };

  const importFile = async (file: File | undefined) => {
    if (!file) return;
    setError('');
    if (file.size > 10 * 1024 * 1024) {
      setError('File is larger than 10 MB. Export a shorter document or paste the notes.');
      if (fileInput.current) fileInput.current.value = '';
      return;
    }
    setBusy(true);
    try {
      const result = await apiStudioExtract(file);
      setText(result.text);
      if (!title.trim()) {
        setTitle(result.filename.replace(/\.[^.]+$/, '').slice(0, 120));
      }
      setToast(result.truncated
        ? 'Imported the first 120,000 characters. Build the pack and trim later if needed.'
        : 'File imported. Review it, then build your pack.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That file could not be read.');
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  };

  const connectDrive = async () => {
    setDriveError('');
    setDriveBusy(true);
    try {
      const token = driveToken || await requestDriveToken(googleClientId());
      setDriveToken(token);
      const file = await pickGoogleDoc(token);
      if (!file) {
        setToast('No document selected. You can try again whenever you are ready.');
        return;
      }
      const imported = await exportGoogleDoc(token, file);
      setText(imported);
      setTitle(file.name.replace(/\.[^.]+$/, '').slice(0, 120));
      if (file.webViewLink && validHttpUrl(file.webViewLink)) setSourceUrl(file.webViewLink);
      setToast('Google Doc imported. Review it, then build your pack.');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Google Drive could not connect.';
      setDriveError(message);
      if (/expired|reconnect|access/i.test(message)) setDriveToken('');
    } finally {
      setDriveBusy(false);
    }
  };

  const disconnectDrive = () => {
    setDriveToken('');
    setDriveError('');
    setToast('Google Drive disconnected. The access token was discarded.');
  };

  const paste = async () => {
    setError('');
    try {
      const clipboard = await navigator.clipboard.readText();
      if (!clipboard.trim()) {
        setError('The clipboard is empty. Copy the notes in NotebookLM first.');
        return;
      }
      setText((current) => current ? `${current}\n\n${clipboard}` : clipboard);
      setToast('Pasted from the clipboard.');
    } catch {
      setError('Your browser blocked clipboard access. Paste with the keyboard instead.');
    }
  };

  const useSample = () => {
    setTitle('Photosynthesis');
    setText(SAMPLE);
    setSourceUrl('');
    setError('');
  };

  const clearDraft = () => {
    setTitle('');
    setText('');
    setSourceUrl('');
    setError('');
  };

  const remove = (id: string) => {
    const pack = packs.find((item) => item.id === id);
    if (pack && !window.confirm(`Delete “${pack.title}” from this device?`)) return;
    const next = packs.filter((item) => item.id !== id);
    persist(next);
    if (activeId === id) setActiveId(next[0]?.id ?? null);
    setToast('Deleted from this device.');
  };

  const download = () => {
    if (!active) return;
    const blob = new Blob([packHtml(active)], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = safeFile(active.title);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    setToast('Download started.');
  };

  const print = () => {
    if (!active) return;
    window.print();
  };

  const toggleKnown = (front: string) => {
    if (!active) return;
    const known = new Set(active.reviewed ?? []);
    if (known.has(front)) known.delete(front);
    else known.add(front);
    updateActive({ reviewed: [...known] });
  };

  const toggleChecked = (item: string) => {
    if (!active) return;
    const checked = new Set(active.checked ?? []);
    if (checked.has(item)) checked.delete(item);
    else checked.add(item);
    updateActive({ checked: [...checked] });
  };

  const known = new Set(active?.reviewed ?? []);
  const checked = new Set(active?.checked ?? []);

  return (
    <div className="studio-page">
      <div className="studio-hero">
        <div>
          <p className="eyebrow">Native workspace</p>
          <h1>{t('studio', lang)}</h1>
          <p className="muted studio-lede">
            Turn notes, a study guide or a quiz you generated in your own
            NotebookLM account into a GramShiksha study pack. Your Google session
            stays in your browser; GramShiksha only receives the text you paste.
          </p>
        </div>
        <div className="studio-device-badge" title="Study packs are saved in this browser, not on a server.">
          <span aria-hidden="true">🔒</span> Saved on this device
        </div>
      </div>

      <InstallPrompt />

      {toast && <p className="studio-toast" role="status">{toast}</p>}
      {error && <p className="error" role="alert">{error}</p>}

      {active ? (
        <div className="studio-pack">
          <div className="studio-pack-head">
            <div>
              <span className="studio-badge">Imported by you · AI-assisted</span>
              <h2>{active.title}</h2>
              <p className="muted studio-meta">
                {new Date(active.createdAt).toLocaleString()}
                {' · '}
                {active.flashcards.length} flashcards · {active.quiz.length} quiz questions
              </p>
              {active.sourceUrl && (
                <p className="studio-meta">
                  Source: <a href={active.sourceUrl} target="_blank" rel="noopener noreferrer">the page you imported from</a>
                </p>
              )}
            </div>
            <div className="studio-actions no-print">
              <button className="btn ghost small" type="button" onClick={print}>Print / Save PDF</button>
              <button className="btn ghost small" type="button" onClick={download}>Download HTML</button>
              <button className="btn ghost small" type="button" onClick={() => setActiveId(null)}>New import</button>
            </div>
          </div>

          <div className="studio-tabs no-print" role="tablist" aria-label="Study pack sections">
            {(['overview', 'flashcards', 'quiz', 'checklist'] as const).map((item) => (
              <button
                key={item}
                type="button"
                role="tab"
                aria-selected={tab === item}
                className={tab === item ? 'active' : ''}
                onClick={() => setTab(item)}
              >
                {item === 'overview' ? 'Overview'
                  : item === 'flashcards' ? `Flashcards (${active.flashcards.length})`
                    : item === 'quiz' ? `Quiz (${active.quiz.length})` : 'Checklist'}
              </button>
            ))}
          </div>

          {/* Printing a single tab would silently drop the other study tools, so
              this print-only sheet carries the complete pack. */}
          <div className="studio-print-sheet" aria-hidden="true">
            <h2>Overview</h2>
            <p>{active.overview || 'No overview was found in the imported text.'}</p>
            <h2>Key points</h2>
            {active.keyPoints.length
              ? <ul>{active.keyPoints.map((point) => <li key={point}>{point}</li>)}</ul>
              : <p>No key points were found.</p>}
            <h2>Flashcards</h2>
            {active.flashcards.length
              ? <ol>{active.flashcards.map((card, index) => (
                  <li key={`${card.front}-${index}`}><strong>{card.front}</strong><br />{card.back}</li>
                ))}</ol>
              : <p>No flashcards were found.</p>}
            <h2>Quiz</h2>
            {active.quiz.length
              ? <ol>{active.quiz.map((card, index) => (
                  <li key={`${card.front}-${index}`}><strong>{card.front}</strong><br />{card.back}</li>
                ))}</ol>
              : <p>No quiz questions were found.</p>}
            <h2>Revision checklist</h2>
            {active.checklist.length
              ? <ul>{active.checklist.map((item) => <li key={item}>{item}</li>)}</ul>
              : <p>No checklist items were found.</p>}
          </div>

          {tab === 'overview' && (
            <section className="studio-section" aria-label="Overview">
              <p>{active.overview || 'No overview was found in the imported text.'}</p>
              <h3>Key points</h3>
              {active.keyPoints.length ? (
                <ul className="studio-points">
                  {active.keyPoints.map((point) => <li key={point}>{point}</li>)}
                </ul>
              ) : <p className="muted">No key points were found.</p>}
            </section>
          )}

          {tab === 'flashcards' && (
            <section className="studio-section" aria-label="Flashcards">
              {active.flashcards.length ? (
                <>
                  <p className="muted">Tap a card to flip it. Mark cards you know to track this session.</p>
                  <div className="flashcard-grid">
                    {active.flashcards.map((card, index) => (
                      <div className="flashcard-cell" key={`${card.front}-${index}`}>
                        <button
                          type="button"
                          className={`flashcard ${flipped[index] ? 'is-flipped' : ''} ${known.has(card.front) ? 'is-known' : ''}`}
                          onClick={() => setFlipped((current) => ({ ...current, [index]: !current[index] }))}
                          aria-pressed={Boolean(flipped[index])}
                        >
                          <span className="flashcard-side">{flipped[index] ? 'Answer' : 'Question'}</span>
                          <strong>{flipped[index] ? card.back : card.front}</strong>
                        </button>
                        <button
                          type="button"
                          className="studio-mark no-print"
                          aria-pressed={known.has(card.front)}
                          onClick={() => toggleKnown(card.front)}
                        >
                          {known.has(card.front) ? 'Known ✓' : 'Mark known'}
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="studio-known no-print">
                    <span>{known.size} of {active.flashcards.length} marked known</span>
                    <button className="btn ghost small" type="button" onClick={() => updateActive({ reviewed: [] })}>
                      Reset marks
                    </button>
                  </div>
                </>
              ) : <p className="muted">No flashcards were found. Add lines like “Term: definition” and import again.</p>}
            </section>
          )}

          {tab === 'quiz' && (
            <section className="studio-section" aria-label="Quiz">
              {active.quiz.length ? (
                <ol className="studio-quiz">
                  {active.quiz.map((card, index) => (
                    <li key={`${card.front}-${index}`}>
                      <p><strong>{card.front}</strong></p>
                      <button
                        className="btn ghost small no-print"
                        type="button"
                        onClick={() => setOpenAnswers((current) => ({ ...current, [index]: !current[index] }))}
                      >
                        {openAnswers[index] ? 'Hide answer' : 'Show answer'}
                      </button>
                      {openAnswers[index] && <p className="studio-answer">{card.back}</p>}
                    </li>
                  ))}
                </ol>
              ) : <p className="muted">No quiz questions were found in this import.</p>}
            </section>
          )}

          {tab === 'checklist' && (
            <section className="studio-section" aria-label="Revision checklist">
              {active.checklist.length ? (
                <ul className="studio-checklist">
                  {active.checklist.map((item) => (
                    <li key={item}>
                      <label>
                        <input
                          type="checkbox"
                          checked={checked.has(item)}
                          onChange={() => toggleChecked(item)}
                        />
                        <span>{item}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              ) : <p className="muted">No checklist items were found.</p>}
            </section>
          )}

          <p className="studio-disclaimer">
            AI-assisted study aid. Always check facts against your official textbook
            and ask your teacher when something is unclear.
          </p>
        </div>
      ) : (
        <div className="studio-import">
          <h2>Import from NotebookLM</h2>
          <ol className="studio-steps">
            <li>Open your own NotebookLM/Gemini Notebook account and generate a study guide, notes or quiz.</li>
            <li>Copy the text you want to study, or export the notebook as a PDF/DOCX.</li>
            <li>Paste it below or use <strong>Import a file</strong>. GramShiksha never asks for your Google password or stores your Google session.</li>
          </ol>

          <div className="studio-file-row">
            <label className="btn ghost small studio-file-button">
              Import a file
              <input
                ref={fileInput}
                type="file"
                accept=".pdf,.docx,.html,.htm,.md,.markdown,.txt,application/pdf,text/plain,text/markdown,text/html,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) => importFile(event.target.files?.[0])}
                disabled={busy}
              />
            </label>
            <span className="muted">PDF, DOCX, HTML, Markdown or TXT · up to 10 MB</span>
          </div>
          <p className="muted studio-file-hint">
            From Google Docs, choose <strong>File → Download → Microsoft Word (.docx)</strong>,
            then import that file. No Google sign-in is needed.
          </p>

          {driveOn && (
            <div className="studio-drive">
              <div className="studio-drive-head">
                <strong>Google Drive</strong>
                <span className="muted">Official · you pick the file</span>
              </div>
              <p className="muted">
                Export a NotebookLM notebook to Google Docs, then choose that one document
                in Google's picker. GramShiksha can read only the file you select and keeps
                the access token in this tab — never on a server.
              </p>
              <div className="studio-import-actions">
                <button className="btn ghost small" type="button" onClick={connectDrive} disabled={driveBusy}>
                  {driveBusy
                    ? 'Opening Google Drive…'
                    : driveToken
                      ? 'Choose another Google Doc'
                      : 'Choose from Google Drive'}
                </button>
                {driveToken && (
                  <button className="btn ghost small" type="button" onClick={disconnectDrive} disabled={driveBusy}>
                    Disconnect
                  </button>
                )}
              </div>
              {driveError && <p className="error" role="alert">{driveError}</p>}
            </div>
          )}

          <label htmlFor="studio-title">Title</label>
          <input
            id="studio-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. Photosynthesis — Class 8 Science"
            maxLength={120}
          />

          <label htmlFor="studio-source">Source URL <span className="muted">(optional)</span></label>
          <input
            id="studio-source"
            type="url"
            inputMode="url"
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
            placeholder="https://notebooklm.google.com/…"
          />

          <label htmlFor="studio-text">Notes, study guide or quiz text</label>
          <textarea
            id="studio-text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={12}
            placeholder="Paste the text you copied from your own notebook…"
          />

          <div className="studio-import-actions">
            <button className="btn" type="button" onClick={build} disabled={busy || text.trim().length < 40}>
              {busy ? 'Building…' : 'Build study pack'}
            </button>
            <button className="btn ghost" type="button" onClick={paste}>Paste from clipboard</button>
            <button className="btn ghost" type="button" onClick={useSample}>Use a sample</button>
            <button className="btn ghost" type="button" onClick={clearDraft} disabled={!title && !text && !sourceUrl}>Clear</button>
          </div>
          <p className="muted studio-hint">Packs are saved in this browser so they open offline. Download HTML to keep a copy.</p>
        </div>
      )}

      {packs.length > 0 && (
        <aside className="studio-library" aria-label="My study packs">
          <div className="studio-library-head">
            <h2>My packs</h2>
            <span className="muted">{packs.length} on this device</span>
          </div>
          <ul>
            {packs.map((pack) => (
              <li key={pack.id}>
                <button
                  type="button"
                  className={pack.id === activeId ? 'active' : ''}
                  onClick={() => { setActiveId(pack.id); setTab('overview'); setFlipped({}); setOpenAnswers({}); }}
                >
                  <strong>{pack.title}</strong>
                  <small>{new Date(pack.createdAt).toLocaleDateString()} · {pack.flashcards.length} cards</small>
                </button>
                <button
                  type="button"
                  className="studio-delete"
                  aria-label={`Delete ${pack.title}`}
                  onClick={() => remove(pack.id)}
                >✕</button>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  );
}
