import { apiStudentLogin } from '../api';
import RoleLoginForm from '../components/RoleLoginForm';
import { t } from '../i18n';
import type { Lang } from '../types';

/** Designated student login (#/login/student). Backed by POST
 * /auth/token/student — teacher credentials get a 403 here, not a session. */
export default function StudentLogin({ lang, go, onAuthed }: {
  lang: Lang; go: (p: string) => void; onAuthed: () => void;
}) {
  return (
    <RoleLoginForm
      lang={lang}
      title={t('studentLogin', lang)}
      subtitle={t('studentLoginTag', lang)}
      loginFn={apiStudentLogin}
      onDone={() => { onAuthed(); go('dashboard'); }}
      switchHref="#/login/teacher"
      switchLabel={t('teacherLogin', lang)}
    />
  );
}
