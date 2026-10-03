import { useEffect, useState } from 'react';
import { apiAvailability, apiMaterials, apiMaterialUrl, apiPendingMaterials, apiReportMaterial, apiReviewMaterial, apiUploadMaterial } from '../api';
import StreamPicker, { streamName } from '../components/StreamPicker';
import { getToken, saveDownload } from '../auth';
import { t } from '../i18n';
import type { AvailabilityStream, Lang, Material } from '../types';

const TYPES = ['notes', 'chapter_notes', 'revision_notes', 'question_paper', 'practice_paper', 'worksheet', 'sample_paper', 'important_questions', 'formula_sheet', 'audio'];
const REPORT_REASONS = ['incorrect', 'duplicate', 'poor_quality', 'copyright', 'inappropriate', 'wrong_class_subject', 'other'];

export default function Materials({ lang, user }: { lang: Lang; user: { role: string } | null }) {
  const [items, setItems] = useState<Material[]>([]);
  const [type, setType] = useState('');
  const [grade, setGrade] = useState<number | ''>('');
  const [board, setBoard] = useState('');
  const [streams, setStreams] = useState<AvailabilityStream[]>([]);
  const [stream, setStream] = useState('');
  const [showUpload, setShowUpload] = useState(false);
  const [pending, setPending] = useState<Material[]>([]);
  const [error, setError] = useState('');
  const isTeacher = user && ['teacher', 'school_admin', 'platform_admin'].includes(user.role);

  const load = () => {
    apiMaterials({
      type: type || undefined,
      class_grade: grade || undefined,
      board: board || undefined,
      stream: stream || undefined,
    }).then(setItems).catch((e) => setError(String(e)));
    if (isTeacher) apiPendingMaterials().then(setPending).catch(() => {});
  };
  useEffect(load, [type, grade, board, stream, user?.role]);

  useEffect(() => {
    if (grade && Number(grade) >= 11 && board) {
      apiAvailability(board, Number(grade)).then((a) => {
        setStreams(a.streams);
        setStream((s) => (s && a.streams.some((x) => x.code === s)) ? s : '');
      }).catch(() => setStreams([]));
    } else {
      setStreams([]);
      setStream('');
    }
  }, [grade, board]);

  return (
    <div>
      <h1>📚 {t('materials', lang)}</h1>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <select style={{ maxWidth: 140 }} value={grade} onChange={(e) => setGrade(e.target.value ? Number(e.target.value) : '')} aria-label="Class">
          <option value="">Class: all</option>
          {Array.from({ length: 12 }, (_, i) => i + 1).map((g) => <option key={g} value={g}>Class {g}</option>)}
        </select>
        <select style={{ maxWidth: 220 }} value={board} onChange={(e) => setBoard(e.target.value)} aria-label="Board">
          <option value="">Board: all</option>
          <option>Maharashtra SSC</option><option>Maharashtra HSC</option><option>CBSE</option>
        </select>
        <select style={{ maxWidth: 220 }} value={type} onChange={(e) => setType(e.target.value)} aria-label="Type">
          <option value="">All types</option>
          {TYPES.map((ty) => <option key={ty} value={ty}>{ty.replace(/_/g, ' ')}</option>)}
        </select>
        {getToken() && <button className="btn small" onClick={() => setShowUpload(!showUpload)}>⬆ {t('newMaterial', lang)}</button>}
      </div>
      <StreamPicker lang={lang} streams={streams} value={stream} onChange={setStream} />

      {showUpload && <UploadForm lang={lang} userRole={user?.role ?? 'student'} onDone={() => { setShowUpload(false); load(); }} />}

      {isTeacher && pending.length > 0 && (
        <div className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
          <h3>⏳ {t('pending', lang)} ({pending.length})</h3>
          {pending.map((m) => (
            <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <div style={{ flex: 1 }}><strong>{m.title}</strong> <span className="muted">by student</span></div>
              <button className="btn small" onClick={async () => { await apiReviewMaterial(m.id, 'approved'); load(); }}>✓ {t('approve', lang)}</button>
              <button className="btn small ghost" onClick={async () => { await apiReviewMaterial(m.id, 'rejected', 'Not suitable'); load(); }}>✗ {t('reject', lang)}</button>
            </div>
          ))}
        </div>
      )}

      {error && <p className="error">{t('errorLoad', lang)}</p>}
      {!items.length && !error && <div className="empty-state"><div className="icon">📄</div><p>No study materials found for this filter.</p></div>}

      {items.map((m) => (
        <div className="card" key={m.id}>
          <strong>{m.title}</strong>
          <div style={{ margin: '4px 0' }}>
            <span className="badge gray">{m.type.replace(/_/g, ' ')}</span>
            <span className="badge">Class {m.class_grade}</span>
            <span className="badge">{m.board}</span>
            {m.stream && <span className="badge gray">{streamName(m.stream, lang)}</span>}
            <span className="badge green">{m.lang}</span>
          </div>
          <p className="muted" style={{ margin: '6px 0' }}>{m.description}</p>
          <div className="muted">source: {m.source_of_content} · ⬇ {m.downloads} · {Math.round(m.file_size / 1024)} KB</div>
          <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
            <button className="btn small" onClick={async () => {
              try {
                const res = await fetch(apiMaterialUrl(m.id), {
                  headers: { Authorization: `Bearer ${getToken() ?? ''}` },
                });
                const text = await res.text();
                saveDownload({ material_id: m.id, title: m.title, saved_at: new Date().toISOString(), text: text.slice(0, 50000) });
                alert('Saved to My Downloads ✓');
              } catch { window.open(apiMaterialUrl(m.id), '_blank'); }
            }}>⬇ {t('download', lang)}</button>
            <button className="btn small ghost" onClick={() => {
              const reason = prompt(`Report reason (${REPORT_REASONS.join('/')}):`, 'incorrect');
              if (reason && REPORT_REASONS.includes(reason)) apiReportMaterial(m.id, reason, '').then(() => alert('Reported ✓'));
            }}>🚩 Report</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function UploadForm({ lang, userRole, onDone }: { lang: Lang; userRole: string; onDone: () => void }) {
  const [title, setTitle] = useState('');
  const [desc, setDesc] = useState('');
  const [type, setType] = useState('notes');
  const [classGrade, setClassGrade] = useState(8);
  const [board, setBoard] = useState('Maharashtra SSC');
  const [subject, setSubject] = useState('Science');
  const [langM, setLangM] = useState<string>(lang);
  const [source, setSource] = useState(userRole === 'student' ? 'Created by student' : 'Created by teacher');
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const submit = async () => {
    if (!file) { setErr('Choose a file (PDF/image/audio, max 10 MB)'); return; }
    const fd = new FormData();
    fd.set('title', title); fd.set('description', desc); fd.set('type', type);
    fd.set('class_grade', String(classGrade)); fd.set('board', board);
    fd.set('subject_name', subject); fd.set('lang', langM);
    fd.set('source_of_content', source); fd.set('file', file);
    try {
      const r = await apiUploadMaterial(fd);
      setMsg(userRole === 'student'
        ? `Submitted! Status: ${r.status === 'pending' ? 'pending review — a teacher will approve it' : r.status}`
        : `Uploaded ✓ (${r.status})`);
      setTimeout(onDone, 1400);
    } catch (e) { setErr(String(e)); }
  };

  return (
    <div className="card">
      <h3>⬆ {t('newMaterial', lang)}</h3>
      {userRole === 'student' && (
        <p className="muted">Your upload will be reviewed by a teacher before it becomes public. Only upload your own work — no copyrighted books.</p>
      )}
      <label>Title</label>
      <input value={title} onChange={(e) => setTitle(e.target.value)} />
      <label>Description</label>
      <textarea value={desc} onChange={(e) => setDesc(e.target.value)} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div>
          <label>Type</label>
          <select value={type} onChange={(e) => setType(e.target.value)}>
            {TYPES.map((ty) => <option key={ty} value={ty}>{ty.replace(/_/g, ' ')}</option>)}
          </select>
        </div>
        <div>
          <label>Class</label>
          <select value={classGrade} onChange={(e) => setClassGrade(Number(e.target.value))}>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
        <div>
          <label>Board</label>
          <select value={board} onChange={(e) => setBoard(e.target.value)}>
            <option>Maharashtra SSC</option><option>Maharashtra HSC</option><option>CBSE</option>
          </select>
        </div>
        <div>
          <label>Subject</label>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} />
        </div>
        <div>
          <label>Language</label>
          <select value={langM} onChange={(e) => setLangM(e.target.value)}>
            <option value="en">English</option><option value="hi">हिंदी</option><option value="mr">मराठी</option>
          </select>
        </div>
        <div>
          <label>Source of content</label>
          <input value={source} onChange={(e) => setSource(e.target.value)} />
        </div>
      </div>
      <label>File (PDF, PNG, JPG, MP3 · max 10 MB)</label>
      <input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.mp3,.m4a,.pptx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      {err && <p className="error">{err}</p>}
      {msg && <p className="success">{msg}</p>}
      <button className="btn" style={{ marginTop: 10 }} disabled={!title || !file} onClick={submit}>{t('submit', lang)}</button>
    </div>
  );
}
