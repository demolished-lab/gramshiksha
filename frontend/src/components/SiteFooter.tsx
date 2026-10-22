import { t } from '../i18n';
import type { Lang } from '../types';
import ShareButtons from './ShareButtons';

/**
 * One footer for every route. Keeping the legal and discovery links here
 * means a crawler can reach them from any public page without relying on the
 * landing page or on JavaScript-generated navigation.
 */
export default function SiteFooter({ lang }: { lang: Lang }) {
  return (
    <footer className="site">
      <img className="footer-logo" src="/images/gramshiksha-wordmark.png" alt="GramShiksha" width="699" height="118" loading="lazy" />
      <nav className="footer-links" aria-label="Site information">
        <a href="/about">{t('about', lang)}</a>
        <a href="/contact">{t('contact', lang)}</a>
        <a href="/privacy">{t('privacy', lang)}</a>
        <a href="/terms">{t('terms', lang)}</a>
        <a href="/sitemap.xml">Sitemap</a>
        <a href="/api/feed.xml">RSS</a>
      </nav>
      <p>{t('landingFooter', lang)}</p>
      <div className="footer-share">
        <ShareButtons text="GramShiksha Academy — free Class 1–12 lessons, quizzes and official textbooks in English, हिंदी and मराठी." />
      </div>
    </footer>
  );
}
