import { apiTeacherLogin } from '../api';
import RoleLoginForm from '../components/RoleLoginForm';
import { t } from '../i18n';
import type { Lang } from '../types';

/** Designated teacher login (#/login/teacher). Backed by POST
 * /auth/token/teacher, which only ever yields teacher sessions — a student
 * credential gets a 403 naming the teacher page, not a session. Pending
 * teachers land on the approval notice via the router's approval gate. */
export default function TeacherLogin({ lang, go, onAuthed }: {
  lang: Lang; go: (p: string) => void; onAuthed: () => void;
}) {
  return (
    <RoleLoginForm
      lang={lang}
      title={t('teacherLogin', lang)}
      subtitle={t('teacherLoginTag', lang)}
      loginFn={apiTeacherLogin}
      onDone={() => { onAuthed(); go('teacher'); }}
      switchHref="#/login/student"
      switchLabel={t('studentLogin', lang)}
    />
  );
}
