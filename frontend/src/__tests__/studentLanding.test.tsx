/**
 * "Log in as a student → see the e-book library" — the product ask.
 *
 * Two paths must land there and one must not:
 * 1. The designated #/login/student page navigates to 'textbooks' itself
 *    (role-enforcing endpoint, then straight to the covers).
 * 2. The generic login/register modal asks App for a destination via
 *    landingAfterAuth — textbooks only when the login started from the
 *    landing/login screens.
 * 3. Nobody else moves: other roles, or a student signing in mid-browse.
 */
import { describe, expect, it, vi } from 'vitest';
import { renderToString } from 'react-dom/server';
import { landingAfterAuth } from '../auth';
import StudentLogin from '../pages/StudentLogin';

const capture = vi.hoisted(() => ({ props: null as {
  onDone: () => void;
} | null }));

vi.mock('../components/RoleLoginForm', () => ({
  default: (props: { onDone: () => void }) => {
    capture.props = props;
    return null;
  },
}));

describe('student login lands in the e-book library', () => {
  it('#/login/student fires onAuthed then navigates to textbooks', () => {
    capture.props = null;
    const go = vi.fn();
    const onAuthed = vi.fn();
    renderToString(<StudentLogin lang="en" go={go} onAuthed={onAuthed} />);
    expect(capture.props).not.toBeNull();
    capture.props!.onDone();
    expect(onAuthed).toHaveBeenCalledTimes(1);
    expect(go).toHaveBeenCalledWith('textbooks');
    expect(go).not.toHaveBeenCalledWith('dashboard');
  });

  it('modal login redirects students only from home/login', () => {
    expect(landingAfterAuth('student', 'home')).toBe('textbooks');
    expect(landingAfterAuth('student', 'login')).toBe('textbooks');
  });

  it('never yanks a student out of the page they were browsing', () => {
    expect(landingAfterAuth('student', 'courses')).toBeNull();
    expect(landingAfterAuth('student', 'practice')).toBeNull();
    expect(landingAfterAuth('student', 'dashboard')).toBeNull();
  });

  it('other roles keep the historical no-redirect behaviour', () => {
    expect(landingAfterAuth('teacher', 'home')).toBeNull();
    expect(landingAfterAuth('parent', 'login')).toBeNull();
    expect(landingAfterAuth('platform_admin', 'home')).toBeNull();
    expect(landingAfterAuth(null, 'home')).toBeNull();
    expect(landingAfterAuth(undefined, 'login')).toBeNull();
  });
});
