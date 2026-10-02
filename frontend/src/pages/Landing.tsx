import { t } from '../i18n';
import type { Lang } from '../types';
import ShareButtons from '../components/ShareButtons';
import SupportBar from '../components/SupportBar';
import AdSlot from '../components/AdSlot';

const FAQS: [string, string][] = [
  ['Is GramShiksha free?', 'Yes — 100% free for students, teachers and parents.'],
  ['Does it work without internet?', 'Yes. Lessons you opened once are cached. Use Data Saver mode on slow networks.'],
  ['Which boards are covered?', 'Maharashtra SSC, Maharashtra HSC and CBSE (NCERT-aligned).'],
  ['Which languages?', 'English, हिंदी and मराठी — switch anytime from the top bar.'],
];

export default function Landing({ lang, go, onLogin }: { lang: Lang; go: (p: string, id?: number) => void; onLogin: () => void }) {
  return (
    <div>
      <section className="hero">
        <h1>{t('appName', lang)}</h1>
        <p>{t('tagline', lang)} — Class 1–12 · Maharashtra SSC · HSC · CBSE · English · हिंदी · मराठी</p>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button className="btn accent" onClick={() => onLogin()}>{t('startLearning', lang)}</button>
          <button className="btn ghost" onClick={() => go('explore')}>🧭 {t('explore', lang)}</button>
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap', marginTop: 10 }}>
          <a className="btn ghost" href="#/login/student">🎒 {t('studentLogin', lang)}</a>
          <a className="btn ghost" href="#/login/teacher">👩‍🏫 {t('teacherLogin', lang)}</a>
        </div>
      </section>

      <h2 className="section-title">{t('classes', lang)} 1–12</h2>
      <div className="grid-cards">
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((g) => (
          <div className="card course-card" key={g} style={{ cursor: 'pointer' }} onClick={() => go('explore', g)}>
            <div className="thumb" style={{ background: ['#2563EB', '#16A34A', '#F97316', '#7C3AED', '#DC2626'][g % 5] }}>
              {g}
            </div>
            <strong>Class {g}</strong>
            <div className="muted">SSC · HSC · CBSE</div>
          </div>
        ))}
      </div>

      <h2 className="section-title">Why {t('appName', lang)}</h2>
      <div className="stat-row">
        <div className="stat"><div className="num">📶</div><div className="lbl">Low-data mode</div></div>
        <div className="stat"><div className="num">📴</div><div className="lbl">Works offline</div></div>
        <div className="stat"><div className="num">🗣️</div><div className="lbl">3 languages</div></div>
        <div className="stat"><div className="num">🎯</div><div className="lbl">Weak-topic detection</div></div>
        <div className="stat"><div className="num">🏆</div><div className="lbl">Badges & streaks</div></div>
        <div className="stat"><div className="num">₹0</div><div className="lbl">Always free</div></div>
      </div>

      <h2 className="section-title">Learn → Practice → Test → Improve</h2>
      <div className="card">
        <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 2 }}>
          <li>Pick your class, board and language</li>
          <li>Learn with text, video and audio lessons</li>
          <li>Practice with instant feedback</li>
          <li>Take quizzes — see what went wrong</li>
          <li>Revise weak topics the app detects for you</li>
          <li>Earn certificates when you finish a course</li>
        </ol>
      </div>

      <h2 className="section-title">FAQ</h2>
      {FAQS.map(([q, a]) => (
        <details className="card" key={q}>
          <summary style={{ fontWeight: 700, cursor: 'pointer' }}>{q}</summary>
          <p className="muted" style={{ marginBottom: 0 }}>{a}</p>
        </details>
      ))}

      <AdSlot />
      <SupportBar />

      <footer className="site">
        {t('appName', lang)} · free & open, built for Bharat 🇮🇳
        <div style={{ marginTop: 8, display: 'flex', justifyContent: 'center' }}>
          <ShareButtons text="GramShiksha — free Class 1-12 lessons, quizzes & textbooks in English, हिंदी and मराठी" />
        </div>
      </footer>
    </div>
  );
}
