import type { ReactNode } from 'react';
import type { Lang } from '../types';

/**
 * Public trust pages. AdSense review and Google Search both expect a real
 * privacy policy, terms, about and contact page on the same domain as the
 * content. They are deliberately plain-English and static: no account is
 * needed to read them, and they describe exactly what the app already does.
 */
const UPDATED = '20 October 2026';
const REPO = 'https://github.com/demolished-lab/gramshiksha';
const ISSUES = `${REPO}/issues`;

function Page({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="legal-page">
      <p className="eyebrow eyebrow-muted">GramShiksha Academy</p>
      <h1>{title}</h1>
      <p className="muted">Last updated: {UPDATED}</p>
      {children}
    </article>
  );
}

export function AboutPage(_: { lang: Lang }) {
  return (
    <Page title="About GramShiksha Academy">
      <p>
        GramShiksha Academy is a free learning website for students in Class 1–12 in India.
        It brings lessons, practice questions, study materials and links to official textbooks
        together in one low-data, offline-friendly place.
      </p>
      <h2>Why it exists</h2>
      <p>
        Many students in villages and small towns learn with a phone, a shared connection and
        limited data. GramShiksha is built for that reality: pages are lightweight, opened
        lessons can be cached, and the important learning flow does not depend on a fast network.
        The interface is available in English, हिंदी and मराठी.
      </p>
      <h2>What is inside</h2>
      <ul>
        <li>Courses and lessons for Maharashtra SSC, Maharashtra HSC and CBSE.</li>
        <li>Practice questions with explanations and progress tracking when signed in.</li>
        <li>Teacher-contributed notes, question papers, worksheets and revision material.</li>
        <li>Links to official textbook PDFs on government and board portals.</li>
        <li>Offline saving and a data-saver mode for slow connections.</li>
      </ul>
      <h2>Who runs it</h2>
      <p>
        GramShiksha Academy is an independent education project created and maintained by
        Pravesh Kumar. It is not affiliated with, endorsed by, or an official website of any
        government, school board or textbook publisher. Textbook links point to the original
        official source whenever one is available.
      </p>
      <h2>Editorial approach</h2>
      <p>
        Lessons and materials are reviewed before they are published. If you find a mistake,
        a broken textbook link or content that should not be public, please report it through
        our <a href="/contact">contact page</a>. Corrections take priority over new content.
      </p>
      <h2>Free, with optional support</h2>
      <p>
        Learning is free. The project may show advertising or optional support links to pay
        for hosting and verification work. Paid support never unlocks a lesson that a free
        learner cannot use. See the <a href="/privacy">privacy policy</a> for how advertising
        and cookies work.
      </p>
    </Page>
  );
}

export function ContactPage(_: { lang: Lang }) {
  return (
    <Page title="Contact GramShiksha Academy">
      <p>
        Questions, corrections and removal requests are welcome. The public issue tracker is
        the fastest route because it keeps a record of the fix.
      </p>
      <h2>Report a problem</h2>
      <p>
        Open an issue at{' '}
        <a href={ISSUES} target="_blank" rel="noopener noreferrer">{ISSUES}</a>.
      </p>
      <p>Please include the page address, what you expected, and what happened. For a broken textbook link, include the class, subject and board.</p>
      <h2>Privacy or account requests</h2>
      <p>
        Ask for access, correction or deletion of your account data in the same issue tracker
        and say that the request is private. Do not post your password, a reset code, an ID
        document or other sensitive personal information in a public issue. We will arrange a
        private channel and verify that the request comes from the account owner.
      </p>
      <h2>Copyright and textbook notices</h2>
      <p>
        If you are a rights holder and believe a file or link should not be listed, identify
        the work, the exact page, and your relationship to the work. GramShiksha links to
        official textbook portals and hosts teacher-contributed material; we remove or
        replace content when a claim is verified.
      </p>
      <h2>What to expect</h2>
      <p>
        This is a small independent project, so replies are not instant. Safety, privacy and
        broken official links are handled before general suggestions. There is no paid support
        line and no guarantee of a response time.
      </p>
      <p className="muted">
        Project source and history: <a href={REPO} target="_blank" rel="noopener noreferrer">{REPO}</a>.
      </p>
    </Page>
  );
}

export function PrivacyPage(_: { lang: Lang }) {
  return (
    <Page title="Privacy Policy">
      <p>
        This policy explains what GramShiksha Academy collects, why, and the choices you have.
        It applies to the website at gramshiksha-academy.vercel.app and to the learning features
        served from it.
      </p>
      <h2>1. Information we collect</h2>
      <ul>
        <li><strong>Account information:</strong> your name, email address, role (student, teacher, parent or administrator), class, board and language preference when you register.</li>
        <li><strong>Learning information:</strong> lessons opened, practice answers, scores, progress, badges, saved materials, reading-list picks and doubts you post.</li>
        <li><strong>Teacher content:</strong> files and descriptions uploaded by teachers, and review notes attached to them.</li>
        <li><strong>Technical information:</strong> server logs such as IP address, browser type, requested page and time of request, kept to operate and secure the service.</li>
        <li><strong>Device storage:</strong> a login token, language choice, data-saver setting, referral code, Study Studio packs and cached lessons/materials stored in your browser. Cached content stays on your device until you clear it.</li>
        <li><strong>Study Studio imports:</strong> text you paste or a PDF, DOCX, HTML, Markdown or text file you upload is read to build your study pack. The uploaded file is parsed in memory for that request and is not stored; the pack stays in your browser.</li>
        <li><strong>Optional Google Drive import:</strong> if you choose it, Google asks for read-only access to your Drive so you can pick one document. The short-lived access token stays in your browser tab and is not stored on our servers. We do not read files you do not select, and we do not use Google user data for advertising.</li>
      </ul>
      <p>We do not ask for a student's home address, government ID, payment card or precise location.</p>

      <h2>2. How we use information</h2>
      <ul>
        <li>Create and secure accounts, and show the right dashboard for your role.</li>
        <li>Save progress, sync offline work and let teachers review their classes.</li>
        <li>Publish approved materials and answer doubts.</li>
        <li>Keep the service available, prevent abuse and diagnose errors.</li>
        <li>Measure whether public pages load correctly and improve the learning flow.</li>
        <li>Show advertising or optional support links that keep free learning running.</li>
      </ul>

      <h2>3. Legal bases</h2>
      <p>
        Where the law requires a legal basis, we rely on performance of a contract (providing
        the account and learning service), legitimate interests (security, reliability and
        improving the service), consent (optional advertising cookies where consent is
        required) and legal obligations.
      </p>

      <h2>4. Cookies, local storage and advertising</h2>
      <p>
        The app uses browser storage for essential functions such as staying signed in,
        remembering your language and saving lessons for offline use. These are not used to
        build a profile for sale.
      </p>
      <p>
        If advertising is enabled, Google AdSense and its partners may use cookies or similar
        technologies to serve ads, measure performance and, where permitted, personalise ads.
        Google may collect information such as your IP address, approximate location, device
        and browser, and the pages you visit. You can learn how Google uses information from
        sites that use its services at{' '}
        <a href="https://policies.google.com/technologies/partner-sites" target="_blank" rel="noopener noreferrer">policies.google.com/technologies/partner-sites</a>.
        You can manage personalised advertising at{' '}
        <a href="https://adssettings.google.com" target="_blank" rel="noopener noreferrer">adssettings.google.com</a>{' '}
        and learn about industry choices at{' '}
        <a href="https://www.aboutads.info/choices/" target="_blank" rel="noopener noreferrer">aboutads.info/choices</a>.
      </p>
      <p>
        Where consent is required by law, a consent message from Google or another compliant
        consent tool appears before personalised advertising cookies are used. Declining
        personalised ads does not block free learning.
      </p>
      <p>
        Optional support links (for example a donation page or an affiliate bookstore) may set
        their own cookies after you click them. Those sites have their own privacy policies.
      </p>

      <h2>5. Sharing</h2>
      <p>
        We do not sell personal information. We share only what is needed with service providers
        that host the site, run the API and database, store uploaded files, deliver email, or
        serve advertising. These providers process data for us under their own terms. We may
        also disclose information when required by law, to protect a user, or to investigate
        abuse. Aggregated, non-identifying statistics may be published.
      </p>
      <p>
        Google Drive import is initiated by you. Google processes the authorization and the
        selected document under Google's own terms and privacy policy; GramShiksha receives only
        the document text you choose to import.
      </p>

      <h2>6. Retention</h2>
      <p>
        Account and learning records are kept while your account is active and for a reasonable
        period afterwards for backups, security and legal obligations. Server logs are kept for
        a shorter operational window. Cached lessons and login state stay on your device until
        you clear them or sign out. You can ask for deletion using the contact page.
      </p>

      <h2>7. Security</h2>
      <p>
        Passwords are stored as one-way hashes, sessions use signed tokens, and API access is
        role-checked. No internet service can promise perfect security, so use a unique password
        and tell us promptly if you think an account has been compromised.
      </p>

      <h2>8. Children and schools</h2>
      <p>
        GramShiksha is intended for school-age learners. Students under 13 should use it with a
        parent, guardian or teacher. We do not knowingly collect more information from a child
        than is needed for the learning service. A parent or guardian can ask us to review or
        delete a child's account through the <a href="/contact">contact page</a>.
      </p>

      <h2>9. Your choices and rights</h2>
      <p>
        Depending on where you live, you may have the right to access, correct, delete, restrict
        or object to processing, or to receive a copy of your data. You can update your profile
        in the app, clear browser storage yourself, and contact us for account deletion. You may
        also complain to your local data-protection authority.
      </p>

      <h2>10. International processing</h2>
      <p>
        Our hosting and service providers may process data in countries other than India. Where
        required, transfers rely on contractual safeguards offered by those providers.
      </p>

      <h2>11. Changes</h2>
      <p>
        If this policy changes materially, the updated date above will change and a notice will
        appear on the site where practical. Continued use after an update means you accept the
        revised policy.
      </p>

      <h2>12. Contact</h2>
      <p>
        For privacy questions or requests, use the <a href="/contact">contact page</a>. Please do
        not send passwords, reset codes or identity documents through a public issue.
      </p>
    </Page>
  );
}

export function TermsPage(_: { lang: Lang }) {
  return (
    <Page title="Terms of Use">
      <p>
        These terms govern your use of GramShiksha Academy. By opening the site or creating an
        account, you agree to them. If you do not agree, please do not use the service.
      </p>
      <h2>1. The service</h2>
      <p>
        GramShiksha Academy provides free lessons, practice questions, study materials, progress
        tools and links to official textbooks for Class 1–12. Features may change, be tested, or
        be withdrawn. Free learning is the core of the service, but no particular lesson, course
        or feature is guaranteed to remain available forever.
      </p>
      <h2>2. Accounts</h2>
      <p>
        Give accurate registration information, keep your password private, and use an account
        that belongs to you. Teachers and administrators may need approval before privileged
        features become available. You are responsible for activity under your account. Tell us
        promptly if you believe it has been used without permission.
      </p>
      <h2>3. Acceptable use</h2>
      <p>Do not use GramShiksha to:</p>
      <ul>
        <li>break the law, harass another person, or post hateful or harmful content;</li>
        <li>upload a file you do not have the right to share, or remove a copyright notice;</li>
        <li>attempt to access another user's account, private data or an administrative area;</li>
        <li>probe, overload or disrupt the service, or bypass rate limits and security controls;</li>
        <li>scrape the service at a volume that harms other learners; or</li>
        <li>misrepresent the service as an official government or board website.</li>
      </ul>
      <h2>4. Your content</h2>
      <p>
        You keep ownership of material you create and upload. By publishing it, you give
        GramShiksha a non-exclusive, worldwide, royalty-free licence to store, display, adapt for
        format and distribute it on the service for teaching and review. You confirm that you
        have the rights needed to grant that licence. We may remove content that is unlawful,
        inaccurate, off-topic, or subject to a verified rights claim.
      </p>
      <h2>5. Textbooks and third-party links</h2>
      <p>
        Textbook links point to official or third-party sources. We do not claim ownership of
        those works and do not control their availability, terms or privacy practices. A broken
        link can be reported through the <a href="/contact">contact page</a>.
      </p>
      <h2>6. Advertising and support links</h2>
      <p>
        The site may display advertising and may link to optional support, donation, premium or
        affiliate offers. Advertising does not change the free learning content. Affiliate and
        sponsored links are marked. Any purchase is between you and the third party, under that
        party's terms; GramShiksha does not process the payment.
      </p>
      <h2>7. Educational disclaimer</h2>
      <p>
        Content is provided for general study support. It is not a substitute for a teacher,
        official syllabus, examination notice or professional advice. Verify important
        information with your school or board. We work to correct errors but do not warrant that
        every page is complete, current or error-free.
      </p>
      <h2>8. Availability and limitation of liability</h2>
      <p>
        The service is provided "as is" and "as available", without warranties to the extent
        permitted by law. To the extent permitted by law, GramShiksha and its maintainers are not
        liable for indirect or consequential loss, lost data, or loss caused by reliance on
        content or a third-party link. Nothing in these terms limits liability that cannot be
        limited by law.
      </p>
      <h2>9. Suspension and termination</h2>
      <p>
        We may suspend or remove an account or content that violates these terms or creates a
        security or legal risk. You may stop using the service at any time and ask for account
        deletion through the contact page.
      </p>
      <h2>10. Changes and governing law</h2>
      <p>
        We may update these terms; the date above will change. Material changes will be flagged
        on the site where practical. These terms are governed by the laws of India, and disputes
        are subject to the competent courts in India, without affecting mandatory consumer
        protections.
      </p>
      <h2>11. Contact</h2>
      <p>
        Questions about these terms can be raised through the <a href="/contact">contact page</a>.
      </p>
    </Page>
  );
}
