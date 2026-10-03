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

const FEATURES = [
  ['📶', 'Built for real connections', 'Save data, keep learning on slow networks, and revisit cached lessons offline.'],
  ['🎯', 'Practice that adapts', 'Get instant explanations and focused revision for the topics you find difficult.'],
  ['🏆', 'Progress you can feel', 'Build streaks, earn badges, and see your learning journey grow over time.'],
];

export default function Landing({ lang, go, onLogin }: { lang: Lang; go: (p: string, id?: number) => void; onLogin: () => void }) {
  return (
    <div className="landing-page">
      <section className="hero hero-home">
        <div className="hero-glow" aria-hidden="true" />
        <div className="hero-copy-block">
          <div className="eyebrow"><span className="eyebrow-dot" /> Free learning for every learner</div>
          <h1>Quality education<br /><span>for every child.</span></h1>
          <p className="hero-copy">{t('tagline', lang)} — a friendly, low-data learning space for Classes 1–12, built for Bharat.</p>
          <div className="hero-actions">
            <button className="btn accent btn-lg" onClick={onLogin}>{t('startLearning', lang)} <span aria-hidden="true">→</span></button>
            <button className="btn ghost btn-lg" onClick={() => go('explore')}>🧭 {t('explore', lang)}</button>
          </div>
          <div className="quick-entry" aria-label="Quick sign in options">
            <span>Already learning with us?</span>
            <a href="#/login/student">Student login</a>
            <span className="quick-divider" aria-hidden="true">·</span>
            <a href="#/login/teacher">Teacher login</a>
          </div>
          <div className="hero-proof"><span>✓</span> SSC · HSC · CBSE <span>✓</span> English · हिंदी · मराठी <span>✓</span> Always free</div>
        </div>
        <div className="hero-visual" aria-label="Students learning together">
          <div className="hero-visual-orbit orbit-one" aria-hidden="true" />
          <div className="hero-visual-orbit orbit-two" aria-hidden="true" />
          <div className="student-illustration"><img src="/images/gramshiksha-hero-classroom.jpg" alt="Students learning together in a bright classroom" /><span className="student-card">Education<br /><strong>changes lives</strong></span></div>
          <div className="floating-topic topic-book">📚<small>Learn</small></div>
          <div className="floating-topic topic-star">✦<small>Grow</small></div>
        </div>
      </section>

      <section className="section-block" aria-labelledby="classes-heading">
        <div className="section-heading"><div><span className="eyebrow eyebrow-muted">Start here</span><h2 id="classes-heading">Choose your class</h2></div><button className="text-link" onClick={() => go('explore')}>Browse all courses <span aria-hidden="true">→</span></button></div>
        <div className="grade-grid">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((g) => (
            <button className={`grade-card grade-${(g - 1) % 5}`} key={g} onClick={() => go('explore', g)}>
              <span className="grade-number">{g}</span><span>Class {g}</span><small>{g <= 10 ? 'SSC · CBSE' : 'HSC · CBSE'}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="section-block" aria-labelledby="popular-heading">
        <div className="section-heading"><div><span className="eyebrow eyebrow-muted">Levels</span><h2 id="popular-heading">Popular classes</h2></div></div>
        <div className="band-grid">
          {[['🧒', 'Class 1–5', 'Foundational learning', 3, '/images/gramshiksha-classroom-learning.jpg'], ['🧑‍🎓', 'Class 6–8', 'Build strong concepts', 7, '/images/gramshiksha-science-study.jpg'], ['📝', 'Class 9–10', 'Board preparation', 10, '/images/gramshiksha-math-lesson.jpg'], ['🎓', 'Class 11–12', 'Higher studies', 12, '/images/gramshiksha-teacher-support.jpg']].map(([icon, title, sub, g, image]) => (
            <button className="band-card" key={title as string} onClick={() => go('explore', g as number)}>
              <span className="band-image"><img src={image as string} alt="" loading="lazy" /><span className="band-ic" aria-hidden="true">{icon}</span></span>
              <strong>{title}</strong>
              <small>{sub}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="feature-grid" aria-label="Why GramShiksha">
        {FEATURES.map(([icon, title, body]) => <article className="feature-card" key={title}><div className="feature-icon" aria-hidden="true">{icon}</div><h3>{title}</h3><p>{body}</p></article>)}
      </section>

      <section className="section-block learning-path" aria-labelledby="path-heading">
        <div className="path-copy"><span className="eyebrow eyebrow-muted">A simple way to improve</span><h2 id="path-heading">Learn → Practice → Test → Improve</h2><p className="muted">Everything you need to make steady progress, without the pressure.</p><button className="btn" onClick={onLogin}>Create your free account <span aria-hidden="true">→</span></button></div>
        <ol className="path-list">
          {['Pick your class, board and language', 'Learn with text, video and audio lessons', 'Practice with instant feedback', 'Take quizzes and understand mistakes', 'Revise weak topics we detect for you'].map((item, i) => <li key={item}><span>{i + 1}</span>{item}</li>)}
        </ol>
      </section>

      <section className="section-block faq-block" aria-labelledby="faq-heading"><div className="section-heading"><div><span className="eyebrow eyebrow-muted">Good to know</span><h2 id="faq-heading">Frequently asked questions</h2></div></div>{FAQS.map(([q, a]) => <details className="faq-item" key={q}><summary>{q}<span aria-hidden="true">+</span></summary><p>{a}</p></details>)}</section>

      <AdSlot /><SupportBar />
      <footer className="site">{t('appName', lang)} · free & open, built for Bharat 🇮🇳<div style={{ marginTop: 8, display: 'flex', justifyContent: 'center' }}><ShareButtons text="GramShiksha — free Class 1-12 lessons, quizzes & textbooks in English, हिंदी and मराठी" /></div></footer>
    </div>
  );
}
