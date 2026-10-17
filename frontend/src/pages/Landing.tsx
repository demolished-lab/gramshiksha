import { t } from '../i18n';
import type { Lang } from '../types';
import ShareButtons from '../components/ShareButtons';
import SupportBar from '../components/SupportBar';
import AdSlot from '../components/AdSlot';

const FAQS: [string, string][] = [
  ['faqFreeQuestion', 'faqFreeAnswer'],
  ['faqOfflineQuestion', 'faqOfflineAnswer'],
  ['faqBoardsQuestion', 'faqBoardsAnswer'],
  ['faqLanguagesQuestion', 'faqLanguagesAnswer'],
];

const FEATURES = [
  ['📶', 'featureConnectionTitle', 'featureConnectionBody'],
  ['🎯', 'featurePracticeTitle', 'featurePracticeBody'],
  ['🏆', 'featureProgressTitle', 'featureProgressBody'],
];

export default function Landing({ lang, go, onLogin }: { lang: Lang; go: (p: string, id?: number) => void; onLogin: () => void }) {
  return (
    <div className="landing-page">
      <section className="hero hero-home">
        <div className="hero-glow" aria-hidden="true" />
        <div className="hero-copy-block">
          <div className="eyebrow"><span className="eyebrow-dot" /> {t('landingEyebrow', lang)}</div>
          <h1>{t('landingHeadlineLead', lang)}<br /><span>{t('landingHeadlineFinish', lang)}</span></h1>
          <p className="hero-copy">{t('tagline', lang)} — {t('landingHeroBody', lang)}</p>
          <div className="hero-actions">
            <button className="btn accent btn-lg" onClick={onLogin}>{t('startLearning', lang)} <span aria-hidden="true">→</span></button>
            <button className="btn ghost btn-lg" onClick={() => go('explore')}>🧭 {t('explore', lang)}</button>
          </div>
          <div className="quick-entry" role="group" aria-label={t('quickLoginLabel', lang)}>
            <span>{t('alreadyLearning', lang)}</span>
            <a href="#/login/student">{t('studentLogin', lang)}</a>
            <span className="quick-divider" aria-hidden="true">·</span>
            <a href="#/login/teacher">{t('teacherLogin', lang)}</a>
          </div>
          <div className="hero-proof"><span aria-hidden="true">✓</span> {t('proofBoards', lang)} <span aria-hidden="true">✓</span> {t('proofLanguages', lang)} <span aria-hidden="true">✓</span> {t('proofFree', lang)}</div>
        </div>
        <div className="hero-visual" role="img" aria-label={t('heroImageLabel', lang)}>
          <div className="hero-visual-orbit orbit-one" aria-hidden="true" />
          <div className="hero-visual-orbit orbit-two" aria-hidden="true" />
          <div className="student-illustration"><img src="/images/gramshiksha-hero-classroom.jpg" alt="" /><span className="student-card">{t('heroCardLine', lang)}<br /><strong>{t('heroCardEmphasis', lang)}</strong></span></div>
          <div className="floating-topic topic-book" aria-hidden="true">📚<small>{t('learn', lang)}</small></div>
          <div className="floating-topic topic-star" aria-hidden="true">✦<small>{t('grow', lang)}</small></div>
        </div>
      </section>

      <section className="section-block" aria-labelledby="classes-heading">
        <div className="section-heading"><div><span className="eyebrow eyebrow-muted">{t('landingStartHere', lang)}</span><h2 id="classes-heading">{t('landingChooseClass', lang)}</h2></div><button className="text-link" onClick={() => go('explore')}>{t('browseAllCourses', lang)} <span aria-hidden="true">→</span></button></div>
        <div className="grade-grid">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((g) => (
            <button className={`grade-card grade-${(g - 1) % 5}`} key={g} onClick={() => go('explore', g)}>
              <span className="grade-number">{g}</span><span>{t('classNumber', lang).replace('{n}', String(g))}</span><small>{g <= 10 ? 'SSC · CBSE' : 'HSC · CBSE'}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="section-block" aria-labelledby="popular-heading">
        <div className="section-heading"><div><span className="eyebrow eyebrow-muted">{t('landingLevels', lang)}</span><h2 id="popular-heading">{t('landingPopularClasses', lang)}</h2></div></div>
        <div className="band-grid">
          {[
            ['🧒', 'popularGroupPrimary', 'popularGroupPrimaryBody', 3, '/images/gramshiksha-classroom-learning.jpg'],
            ['🧑‍🎓', 'popularGroupMiddle', 'popularGroupMiddleBody', 7, '/images/gramshiksha-science-study.jpg'],
            ['📝', 'popularGroupBoard', 'popularGroupBoardBody', 10, '/images/gramshiksha-math-lesson.jpg'],
            ['🎓', 'popularGroupHigher', 'popularGroupHigherBody', 12, '/images/gramshiksha-teacher-support.jpg'],
          ].map(([icon, titleKey, bodyKey, grade, image]) => (
            <button className="band-card" key={titleKey as string} onClick={() => go('explore', grade as number)}>
              <span className="band-image"><img src={image as string} alt="" loading="lazy" /><span className="band-ic" aria-hidden="true">{icon}</span></span>
              <strong>{t(titleKey as string, lang)}</strong>
              <small>{t(bodyKey as string, lang)}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="feature-grid" aria-label={t('whyGramShiksha', lang)}>
        {FEATURES.map(([icon, titleKey, bodyKey]) => <article className="feature-card" key={titleKey}><div className="feature-icon" aria-hidden="true">{icon}</div><h3>{t(titleKey, lang)}</h3><p>{t(bodyKey, lang)}</p></article>)}
      </section>

      <section className="section-block learning-path" aria-labelledby="path-heading">
        <div className="path-copy"><span className="eyebrow eyebrow-muted">{t('landingSimpleWay', lang)}</span><h2 id="path-heading">{t('learningFlow', lang)}</h2><p className="muted">{t('learningFlowBody', lang)}</p><button className="btn" onClick={onLogin}>{t('createFreeAccount', lang)} <span aria-hidden="true">→</span></button></div>
        <ol className="path-list">
          {['learningStep1', 'learningStep2', 'learningStep3', 'learningStep4', 'learningStep5'].map((key, i) => <li key={key}><span>{i + 1}</span>{t(key, lang)}</li>)}
        </ol>
      </section>

      <section className="section-block faq-block" aria-labelledby="faq-heading"><div className="section-heading"><div><span className="eyebrow eyebrow-muted">{t('landingGoodToKnow', lang)}</span><h2 id="faq-heading">{t('faqHeading', lang)}</h2></div></div>{FAQS.map(([question, answer]) => <details className="faq-item" key={question}><summary>{t(question, lang)}<span aria-hidden="true">+</span></summary><p>{t(answer, lang)}</p></details>)}</section>

      <AdSlot /><SupportBar />
      <footer className="site">{t('landingFooter', lang)}<div style={{ marginTop: 8, display: 'flex', justifyContent: 'center' }}><ShareButtons text="GramShiksha — free Class 1-12 lessons, quizzes & textbooks in English, हिंदी and मराठी" /></div></footer>
    </div>
  );
}
