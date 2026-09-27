import { useEffect, useState } from 'react';
import { apiAskDoubt, apiDoubts, apiReplyDoubt, apiResolveDoubt } from '../api';
import { getToken } from '../auth';
import { t } from '../i18n';
import type { Doubt, Lang } from '../types';

export default function Doubts({ lang, user }: { lang: Lang; user: { role: string } | null }) {
  const [doubts, setDoubts] = useState<Doubt[]>([]);
  const [subject, setSubject] = useState('Science');
  const [text, setText] = useState('');
  const [replyFor, setReplyFor] = useState<number | null>(null);
  const [replyText, setReplyText] = useState('');
  const [error, setError] = useState('');
  const isTeacher = user && ['teacher', 'school_admin', 'platform_admin'].includes(user.role);

  const load = () => {
    if (getToken()) apiDoubts().then(setDoubts).catch((e) => setError(String(e)));
  };
  useEffect(load, []);

  if (!getToken()) {
    return <div className="empty-state"><div className="icon">❓</div><p>{t('needLogin', lang) || 'Log in to ask doubts.'}</p></div>;
  }

  const ask = async () => {
    if (text.trim().length < 5) return;
    await apiAskDoubt(subject, '', text.trim()).catch((e) => setError(String(e)));
    setText('');
    load();
  };

  return (
    <div>
      <h1>❓ {t('doubts', lang)}</h1>

      {user?.role === 'student' && (
        <div className="card">
          <h3>{t('askDoubt', lang)}</h3>
          <select value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject">
            {['Mathematics', 'Science', 'English', 'Hindi', 'Marathi', 'Social Science', 'Physics', 'Chemistry', 'Biology'].map((s) => <option key={s}>{s}</option>)}
          </select>
          <textarea style={{ marginTop: 8 }} value={text} onChange={(e) => setText(e.target.value)}
            placeholder="Type your doubt… (अपना प्रश्न लिखें…)" />
          <button className="btn" style={{ marginTop: 8 }} disabled={text.trim().length < 5} onClick={ask}>{t('send', lang)}</button>
        </div>
      )}

      {error && <p className="error">{error}</p>}
      {!doubts.length && <div className="empty-state"><div className="icon">💬</div><p>No doubts submitted yet.</p></div>}

      {doubts.map((d) => (
        <div className="card" key={d.id}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>{d.subject_name}</strong>
            <span className={`badge ${d.status === 'resolved' ? 'green' : d.status === 'answered' ? '' : 'orange'}`}>{d.status}</span>
          </div>
          <p style={{ margin: '8px 0' }}>{d.text}</p>
          <div className="muted">— {d.student_name}, {new Date(d.created_at).toLocaleDateString()}</div>
          {d.replies.map((r, i) => (
            <div key={i} style={{ background: '#F0FDF4', borderRadius: 10, padding: '8px 12px', margin: '8px 0' }}>
              👩‍🏫 {r.body}
            </div>
          ))}
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            {isTeacher && d.status !== 'resolved' && (
              replyFor === d.id ? (
                <>
                  <input value={replyText} onChange={(e) => setReplyText(e.target.value)} placeholder="Your answer…" />
                  <button className="btn small" onClick={async () => {
                    await apiReplyDoubt(d.id, replyText); setReplyFor(null); setReplyText(''); load();
                  }}>{t('send', lang)}</button>
                </>
              ) : (
                <button className="btn small" onClick={() => setReplyFor(d.id)}>💬 Answer</button>
              )
            )}
            {(user?.role === 'student' || isTeacher) && d.status === 'answered' && (
              <button className="btn small ghost" onClick={async () => { await apiResolveDoubt(d.id); load(); }}>✓ Mark resolved</button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
