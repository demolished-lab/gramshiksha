import type {
  Doubt, LessonDetail, Lang, LoginResponse, Material, Me, Notification, ParentChild,
  ProgressSummary, Question, QuizDetail, QuizResult, RoleStatus, TeacherStudent,
  Textbook, TodayPlan, WeakTopics, Course,
} from './types';

const BASE = `${(import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL ?? ''}/api`;

async function req<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('gs_token');
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    // Token expired/invalid — drop session so the UI falls back to login.
    localStorage.removeItem('gs_token');
    localStorage.removeItem('gs_user');
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j);
    } catch { /* keep statusText */ }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  req<T>(path, {
    method: 'POST',
    // FormData must be passed through untouched: JSON.stringify(FormData) is
    // "{}", so material upload would post an empty JSON body and come back
    // 422 from the multipart parser. req() then also skips the Content-Type
    // header so the browser can set the boundary.
    body: body === undefined || body instanceof FormData ? body : JSON.stringify(body),
  });

// ---------- auth ----------
export const apiRegister = (payload: Record<string, unknown>) =>
  post<{ access_token: string }>('/auth/register', payload);
export const apiLogin = async (email: string, password: string): Promise<LoginResponse> => {
  const res = await fetch(`${BASE}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username: email, password }).toString(),
  });
  if (!res.ok) {
    const j = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof j.detail === 'string' ? j.detail : 'Login failed');
  }
  return res.json();
};
export const apiMe = () => req<Me>('/auth/me');
export const apiUpdateMe = (payload: Record<string, unknown>) =>
  req<{ ok: boolean }>('/auth/me', { method: 'PATCH', body: JSON.stringify(payload) });

// ---------- catalog ----------
export const apiBoards = () => req<{ id: number; name: string }[]>('/meta/boards');
export const apiSubjects = (classGrade: number, board: string) =>
  req<{ id: number; name_en: string; name_hi: string; name_mr: string }[]>(
    `/meta/subjects?class_grade=${classGrade}&board=${encodeURIComponent(board)}`);
export interface CourseQuery {
  class_grade?: number | null; board?: string | null; subject_id?: number | null;
  lang?: string | null; difficulty?: string | null; free_only?: boolean;
  sort?: string; limit?: number; offset?: number;
}
export const apiCourses = (q: CourseQuery = {}) => {
  const p = new URLSearchParams();
  Object.entries(q).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') p.set(k, String(v));
  });
  return req<{ total: number; items: Course[] }>(`/courses?${p.toString()}`);
};
export const apiCourse = (id: number) => req<Course>(`/courses/${id}`);
export const apiEnroll = (id: number) => post<{ ok: boolean }>(`/courses/${id}/enroll`);
export const apiMyCourses = () => req<(Course & { progress_pct: number })[]>('/my/courses');
export const apiTextbooks = (classGrade: number, board: string, lang?: string | null, subjectName?: string | null) => {
  const p = new URLSearchParams({ class_grade: String(classGrade), board });
  if (lang) p.set('lang', lang);
  if (subjectName) p.set('subject_name', subjectName);
  return req<Textbook[]>(`/textbooks?${p.toString()}`);
};
export const apiTextbookPortals = () =>
  req<{ name: string; url: string; boards: string[]; langs: string[] }[]>('/textbooks/portals');
export const apiTextbookOpenUrl = (id: number) => `${BASE}/textbooks/${id}/open`;

// ---------- learn ----------
export const apiLesson = (id: number, lang: Lang) => req<LessonDetail>(`/learn/lessons/${id}?lang=${lang}`);
export const apiCompleteLesson = (id: number, minutes = 10) =>
  post<{ ok: boolean; xp: number; streak_days: number }>(`/learn/lessons/${id}/complete?minutes=${minutes}`);
export const apiQuizByChapter = (chapterId: number, lang: Lang) =>
  req<QuizDetail>(`/learn/quizzes-by-chapter/${chapterId}?lang=${lang}`);
export const apiQuiz = (id: number, lang: Lang) => req<QuizDetail>(`/learn/quizzes/${id}?lang=${lang}`);
export const apiQuizSubmit = (quizId: number, answers: { question_id: number; answer: unknown }[], timeTakenS: number) =>
  post<QuizResult>(`/learn/quizzes/${quizId}/submit`, { answers, time_taken_s: timeTakenS });
export const apiPracticeQuestions = (opts: { subject_name?: string; topic?: string; difficulty?: string; limit?: number; lang?: Lang }) => {
  const p = new URLSearchParams();
  Object.entries(opts).forEach(([k, v]) => { if (v) p.set(k, String(v)); });
  return req<Question[]>(`/learn/practice/questions?${p.toString()}`);
};
export const apiPracticeAnswer = (questionId: number, answer: unknown) =>
  post<{ correct: boolean; correct_answer: unknown; explanation: string }>(
    '/learn/practice/answer', { question_id: questionId, answer });
export const apiToday = (lang: Lang) => req<TodayPlan>(`/learn/today?lang=${lang}`);
export const apiWeakTopics = () => req<WeakTopics>('/learn/weak-topics');
export const apiSyncQueue = (items: unknown[]) => post<{ synced: { ok: boolean }[] }>('/learn/sync', items);

// ---------- materials ----------
export const apiMaterials = (opts: { class_grade?: number; board?: string; subject_name?: string; type?: string; lang?: string; mine?: boolean }) => {
  const p = new URLSearchParams();
  Object.entries(opts).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') p.set(k, String(v)); });
  return req<Material[]>(`/materials?${p.toString()}`);
};
export const apiUploadMaterial = (form: FormData) => post<{ id: number; status: string }>('/materials', form);
export const apiPendingMaterials = () => req<Material[]>('/materials/pending');
export const apiReviewMaterial = (id: number, decision: string, reason = '') => {
  const fd = new FormData();
  fd.set('decision', decision);
  fd.set('reason', reason);
  return req<{ ok: boolean }>(`/materials/${id}/review`, { method: 'POST', body: fd });
};
export const apiReportMaterial = (id: number, reason: string, detail = '') => {
  const fd = new FormData();
  fd.set('reason', reason);
  fd.set('detail', detail);
  return req<{ ok: boolean }>(`/materials/${id}/report`, { method: 'POST', body: fd });
};
export const apiMaterialUrl = (id: number) => `${BASE}/materials/${id}/download`;

// ---------- social ----------
export const apiAskDoubt = (subject_name: string, chapter_title: string, text: string) =>
  post<{ id: number }>('/doubts', { subject_name, chapter_title, text });
export const apiDoubts = () => req<Doubt[]>('/doubts');
export const apiReplyDoubt = (id: number, body: string) => post<{ ok: boolean }>(`/doubts/${id}/reply`, { body });
export const apiResolveDoubt = (id: number) => post<{ ok: boolean }>(`/doubts/${id}/resolve`);
export const apiBookmarks = () => req<{ id: number; lesson_id: number | null; course_id: number | null }[]>('/bookmarks');
export const apiAddBookmark = (lessonId?: number, courseId?: number) => {
  const p = new URLSearchParams();
  if (lessonId) p.set('lesson_id', String(lessonId));
  if (courseId) p.set('course_id', String(courseId));
  return post<{ ok: boolean }>(`/bookmarks?${p.toString()}`);
};
export const apiRemoveBookmark = (id: number) => req<{ ok: boolean }>(`/bookmarks/${id}`, { method: 'DELETE' });
export const apiNotes = (lessonId?: number) =>
  req<{ id: number; lesson_id: number; body: string; created_at: string }[]>(
    `/notes${lessonId ? `?lesson_id=${lessonId}` : ''}`);
export const apiAddNote = (lessonId: number, body: string) => post<{ id: number }>('/notes', { lesson_id: lessonId, body });
export const apiDeleteNote = (id: number) => req<{ ok: boolean }>(`/notes/${id}`, { method: 'DELETE' });
export const apiNotifications = () => req<Notification[]>('/notifications');
export const apiReadAll = () => post<{ ok: boolean }>('/notifications/read-all');

// ---------- dashboards ----------
export const apiProgressSummary = () => req<ProgressSummary>('/progress/summary');
export const apiTeacherStudents = () => req<TeacherStudent[]>('/teacher/students');
export const apiTeacherOverview = () => req<{ my_courses: { id: number; title_en: string; students: number }[]; pending_material_reviews: number; pending_doubts: number; total_students: number }>('/teacher/overview');
export const apiParentChildren = () => req<ParentChild[]>('/parent/children');
export const apiSchoolStats = () => req<{ students: number; teachers: number; lessons_completed_total: number }>('/school/stats');

// ---------- admin (approval workflow) ----------
export interface AdminUser {
  id: number; email: string; name: string; role: string; role_status: RoleStatus;
  class_grade: number | null; board: string | null; xp: number;
}
export const apiAdminUsers = (limit = 100) => req<AdminUser[]>(`/admin/users?limit=${limit}`);
/** Approve = grant (or restore) privileges; suspend = withdraw them. Both are
 * platform-admin-only and idempotent server-side. */
export const apiApproveUser = (id: number) =>
  post<{ ok: boolean; id: number; role_status: RoleStatus }>(`/admin/users/${id}/approve`);
export const apiSuspendUser = (id: number) =>
  post<{ ok: boolean; id: number; role_status: RoleStatus }>(`/admin/users/${id}/suspend`);
export const apiSearch = (q: string) => req<Record<string, { id: number; title_en?: string; title?: string; prompt_en?: string }[]>>(`/search?q=${encodeURIComponent(q)}`);
