import { useEffect, useState, type FormEvent } from 'react';
import {
  apiAdminUsers, apiApproveUser, apiAssignableCourses, apiAssignCourseTeacher,
  apiMe, apiSchoolAnnounce, apiSchoolStats, apiSuspendUser, type AssignableCourse,
  type AdminUser,
} from '../api';
import { getUser } from '../auth';
import { t } from '../i18n';
import type { Lang, RoleStatus } from '../types';

const statusKey = (s: RoleStatus) =>
  s === 'pending' ? 'statusPending' : s === 'suspended' ? 'statusSuspended' : 'statusActive';
const statusBadge = (s: RoleStatus) =>
  s === 'active' ? 'green' : s === 'pending' ? 'orange' : 'gray';
const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));
const isStaff = (role: string) =>
  role === 'teacher' || role === 'school_admin' || role === 'platform_admin';

export default function AdminDashboard({ lang }: { lang: Lang }) {
  const [stats, setStats] = useState<{ students: number; teachers: number; lessons_completed_total: number } | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersLoaded, setUsersLoaded] = useState(false);
  const [courses, setCourses] = useState<AssignableCourse[]>([]);
  const [courseId, setCourseId] = useState<number | null>(null);
  const [teacherId, setTeacherId] = useState<number | null>(null);
  const [announceTitle, setAnnounceTitle] = useState('');
  const [announceBody, setAnnounceBody] = useState('');
  const [announcementMessage, setAnnouncementMessage] = useState('');
  const [assignmentMessage, setAssignmentMessage] = useState('');
  const [currentUserId, setCurrentUserId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () => {
    setUsersLoaded(false);
    apiAdminUsers(100).then((rows) => {
      setUsers(rows);
      setTeacherId((current) => current !== null && rows.some((u) => u.id === current && u.role === 'teacher' && u.role_status === 'active')
        ? current : rows.find((u) => u.role === 'teacher' && u.role_status === 'active')?.id ?? null);
    }).catch((e) => setError(errText(e))).finally(() => setUsersLoaded(true));
    apiAssignableCourses().then((rows) => {
      setCourses(rows);
      setCourseId((current) => current ?? rows[0]?.id ?? null);
    }).catch((e) => setError(errText(e)));
  };

  useEffect(() => {
    apiSchoolStats().then(setStats).catch((e) => setError(errText(e)));
    apiMe().then((me) => setCurrentUserId(me.id)).catch(() => {});
    load();
  }, []);

  const setStatus = async (id: number, action: 'approve' | 'suspend') => {
    setBusy(true);
    setError('');
    try {
      await (action === 'approve' ? apiApproveUser(id) : apiSuspendUser(id));
      load();
    } catch (e) { setError(errText(e)); }
    finally { setBusy(false); }
  };

  const assignTeacher = async (event: FormEvent) => {
    event.preventDefault();
    if (courseId === null || teacherId === null) return;
    setBusy(true);
    setError('');
    setAssignmentMessage('');
    try {
      await apiAssignCourseTeacher(courseId, teacherId);
      setAssignmentMessage(t('courseAssignmentSaved', lang));
      load();
    } catch (e) { setError(errText(e)); }
    finally { setBusy(false); }
  };

  const announce = async (event: FormEvent) => {
    event.preventDefault();
    if (!announceTitle.trim()) return;
    setBusy(true);
    setError('');
    setAnnouncementMessage('');
    try {
      const result = await apiSchoolAnnounce(announceTitle.trim(), announceBody.trim());
      setAnnouncementMessage(t('announcementSent', lang).replace('{n}', String(result.notified)));
      setAnnounceTitle('');
      setAnnounceBody('');
    } catch (e) { setError(errText(e)); }
    finally { setBusy(false); }
  };

  const activeTeachers = users.filter((u) => u.role === 'teacher' && u.role_status === 'active');
  const currentUser = getUser();
  const canManageUsers = currentUser?.role === 'platform_admin';

  return (
    <div>
      <div className="page-head"><div><span className="eyebrow eyebrow-muted">{t('administration', lang)}</span><h1>🛠 {t('admin', lang)}</h1></div></div>
      {stats && (
        <div className="stat-cards">
          <div className="stat-card"><div className="ic" aria-hidden="true">👥</div><div className="num">{stats.students}</div><div className="lbl">{t('students', lang)}</div></div>
          <div className="stat-card"><div className="ic" aria-hidden="true">👩‍🏫</div><div className="num">{stats.teachers}</div><div className="lbl">{t('teacher', lang)}</div></div>
          <div className="stat-card"><div className="ic" aria-hidden="true">📖</div><div className="num">{stats.lessons_completed_total}</div><div className="lbl">{t('lessonsDone', lang)}</div></div>
        </div>
      )}

      <section className="card" aria-labelledby="announcement-title">
        <h2 id="announcement-title">📣 {t('schoolAnnouncement', lang)}</h2>
        <form onSubmit={announce}>
          <label htmlFor="announcement-heading">{t('announcementTitle', lang)}</label>
          <input id="announcement-heading" value={announceTitle} onChange={(e) => setAnnounceTitle(e.target.value)} required maxLength={160} />
          <label htmlFor="announcement-body">{t('announcementBody', lang)}</label>
          <textarea id="announcement-body" value={announceBody} onChange={(e) => setAnnounceBody(e.target.value)} rows={3} maxLength={2000} />
          <button className="btn accent" type="submit" disabled={busy || !announceTitle.trim()}>{t('sendAnnouncement', lang)}</button>
        </form>
        {announcementMessage && <p className="success" role="status">{announcementMessage}</p>}
      </section>

      {courses.length > 0 && activeTeachers.length > 0 && (
        <section className="card" aria-labelledby="course-assignment-title">
          <h2 id="course-assignment-title">{t('courseAssignmentTitle', lang)}</h2>
          <form onSubmit={assignTeacher}>
            <label htmlFor="assign-course">{t('courseLabel', lang)}</label>
            <select id="assign-course" value={courseId ?? ''} onChange={(e) => setCourseId(e.target.value ? Number(e.target.value) : null)}>
              {courses.map((course) => <option key={course.id} value={course.id}>Class {course.class_grade} · {course.title_en} · {course.board}</option>)}
            </select>
            <label htmlFor="assign-teacher">{t('teacherLabel', lang)}</label>
            <select id="assign-teacher" value={teacherId ?? ''} onChange={(e) => setTeacherId(e.target.value ? Number(e.target.value) : null)}>
              {activeTeachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.name} · {teacher.email}</option>)}
            </select>
            <button className="btn small" type="submit" disabled={busy || courseId === null || teacherId === null}>{t('assignCourseTeacher', lang)}</button>
          </form>
          {assignmentMessage && <p className="success" role="status">{assignmentMessage}</p>}
        </section>
      )}

      {error && <p className="error" role="alert">{error}</p>}
      <div className="card">
        <h2>{t('students', lang)} &amp; {t('staff', lang)}</h2>
        <div className="table-scroll" role="region" aria-label={t('staff', lang)} tabIndex={0}>
          <table>
            <thead>
              <tr><th>{t('name', lang)}</th><th>{t('role', lang)}</th><th>{t('status', lang)}</th><th>{t('classLabel', lang)}</th><th>{t('xp', lang)}</th>{canManageUsers && <th>{t('actions', lang)}</th>}</tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.name}<div className="muted">{u.email}</div></td>
                  <td><span className="badge gray">{u.role}</span></td>
                  <td><span className={`badge ${statusBadge(u.role_status)}`}>{t(statusKey(u.role_status), lang)}</span></td>
                  <td>{u.class_grade ?? '—'}</td>
                  <td>{u.xp}</td>
                  {canManageUsers && <td>
                    {isStaff(u.role) && currentUserId !== null && u.id !== currentUserId && (u.role_status === 'active'
                      ? <button className="btn small ghost" disabled={busy} onClick={() => setStatus(u.id, 'suspend')}>⛔ {t('suspend', lang)}</button>
                      : <button className="btn small" disabled={busy} onClick={() => setStatus(u.id, 'approve')}>✓ {t('approve', lang)}</button>)}
                  </td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!users.length && !error && <p className="muted">{usersLoaded ? t('empty', lang) : t('loading', lang)}</p>}
      </div>
    </div>
  );
}
