import { useState } from 'react';
import { apiLogin, apiRegister } from './api';
import { saveSession } from './auth';
import { getReferral } from './growth';
import { t } from './i18n';
import type { Lang } from './types';

const BOARDS = ['Maharashtra SSC', 'Maharashtra HSC', 'CBSE'];

export default function AuthModal({ lang, onClose, onAuthed }: {
  lang: Lang; onClose: () => void; onAuthed: () => void;
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('student');
  const [classGrade, setClassGrade] = useState(8);
  const [board, setBoard] = useState('Maharashtra SSC');
  const [prefLang, setPrefLang] = useState<Lang>(lang);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true); setErr('');
    try {
      if (mode === 'login') {
        saveSession(await apiLogin(email, password));
      } else {
        await apiRegister({
          email, name, password, role, lang_pref: prefLang,
          class_grade: role === 'student' ? classGrade : null, board: role === 'student' ? board : null,
          ref: getReferral(),
        });
        saveSession(await apiLogin(email, password));
      }
      onAuthed();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60, padding: 16 }}
      onClick={onClose} role="dialog" aria-modal="true">
      <div className="card" style={{ width: 380, maxWidth: '94vw' }} onClick={(e) => e.stopPropagation()}>
        <h3>{mode === 'login' ? t('login', lang) : t('register', lang)}</h3>
        {mode === 'register' && (
          <>
            <label>{t('name', lang)}</label>
            <input value={name} onChange={(e) => setName(e.target.value)} />
            <label>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="student">{t('student', lang)}</option>
              <option value="teacher">{t('teacher', lang)}</option>
              <option value="parent">{t('parent', lang)}</option>
            </select>
            {role === 'student' && (
              <>
                <label>{t('classes', lang)}</label>
                <select value={classGrade} onChange={(e) => setClassGrade(Number(e.target.value))}>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((g) => (
                    <option key={g} value={g}>Class {g} / कक्षा {g} / इयत्ता {g}</option>
                  ))}
                </select>
                <label>Board</label>
                <select value={board} onChange={(e) => setBoard(e.target.value)}>
                  {BOARDS.map((b) => <option key={b} value={b}>{b}</option>)}
                </select>
                <label>Language / भाषा / भाषा</label>
                <select value={prefLang} onChange={(e) => setPrefLang(e.target.value as Lang)}>
                  <option value="en">English</option>
                  <option value="hi">हिंदी</option>
                  <option value="mr">मराठी</option>
                </select>
              </>
            )}
          </>
        )}
        <label>{t('email', lang)}</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
        <label>{t('password', lang)}</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
        {err && <p className="error">{err}</p>}
        <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
          <button className="btn" disabled={busy || !email || !password} onClick={submit}>
            {mode === 'login' ? t('login', lang) : t('register', lang)}
          </button>
          <button className="btn ghost" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
            {mode === 'login' ? t('register', lang) : t('login', lang)}
          </button>
          <span style={{ flex: 1 }} />
          <button className="btn ghost small" onClick={onClose} aria-label="Close">✕</button>
        </div>
      </div>
    </div>
  );
}
