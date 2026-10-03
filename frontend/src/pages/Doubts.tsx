import { useEffect, useState } from 'react';
import { apiAskDoubt, apiDoubts, apiReplyDoubt, apiResolveDoubt } from '../api';
import { getToken, getUser } from '../auth';
import { t } from '../i18n';
import type { Doubt, Lang } from '../types';

export default function Doubts({ lang, user }: { lang: Lang; user: { role: string } | null }) {
  const [doubts, setDoubts] = useState<Doubt[]>([]);
  const [subject, setSubject] = useState('Science');
  const [text, setText] = useState('');
  const [replyFor, setReplyFor] = useState<number | null>(null);
  const [replyText, setReplyText] = useState('');
  const [error, setError] = useState('');
  const [tab, setTab] = useState<'all' | 'unanswered' | 'answered' | 'mine'>('all');
  const [term, setTerm] = useState('');
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
      <div className="page-head">
        <div><span className="eyebrow eyebrow-muted">Q & A</span><h1>❓ {t('doubts', lang)}</h1></div>
      </div>

      <div className="search-row">
        <input value={term} onChange={(e) => setTerm(e.target.value)}
          placeholder="Search your doubts…" aria-label="Search doubts" />
      </div>
      <div className="tabs" role="tablist" aria-label="Doubt filters">
        {(['all', 'unanswered', 'answered', 'mine'] as const).map((k) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k}
            className={tab === k ? 'active' : ''}
            onClick={() => setTab(k)}>
            {k === 'all' ? 'All' : k === 'unanswered' ? 'Unanswered' : k === 'answered' ? 'Answered' : 'My questions'}
          </button>
        ))}
      </div>

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
      {(() => {
        const q = term.trim().toLowerCase();
        const me = getUser()?.name;
        const rows = doubts.filter((d) =>
          (tab === 'all'
            || (tab === 'unanswered' && d.status !== 'resolved' && d.status !== 'answered')
            || (tab === 'answered' && (d.status === 'answered' || d.status === 'resolved'))
            || (tab === 'mine' && !!me && d.student_name === me))
          && (!q || d.text.toLowerCase().includes(q) || d.subject_name.toLowerCase().includes(q)));
        return (<>
          {!rows.length && <div className="empty-state"><div className="icon">💬</div><p>{doubts.length ? 'Nothing matches this filter.' : 'No doubts submitted yet.'}</p></div>}
          {rows.map((d) => (
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
        </>);})()}
    </div>
  );
}
