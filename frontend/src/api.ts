import type {
  Availability, BookAsk, Doubt, LessonDetail, Lang, LocateResult, LoginResponse, Material, Me, Notification,
  ParentChild, ProgressSummary, Question, QuizDetail, QuizResult, ReadingPick, RoleStatus,
  TeacherStudent, Textbook, TodayPlan, WeakTopics, Course,
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

/** Designated logins: the teacher page only yields teacher sessions, the
 * student page only student sessions (server returns 403 on role mismatch).
 * Parents and admins keep using the generic apiLogin. */
const apiRoleLogin = async (
  path: '/auth/token/teacher' | '/auth/token/student',
  email: string, password: string,
): Promise<LoginResponse> => {
  const res = await fetch(`${BASE}${path}`, {
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
export const apiTeacherLogin = (email: string, password: string) =>
  apiRoleLogin('/auth/token/teacher', email, password);
export const apiStudentLogin = (email: string, password: string) =>
  apiRoleLogin('/auth/token/student', email, password);

// ---------- catalog ----------
export const apiBoards = () => req<{ id: number; name: string }[]>('/meta/boards');
export const apiSubjects = (classGrade: number, board: string) =>
  req<{ id: number; name_en: string; name_hi: string; name_mr: string }[]>(
    `/meta/subjects?class_grade=${classGrade}&board=${encodeURIComponent(board)}`);
/** What actually exists for (board, class): mediums, subjects, book and
 * lesson counts. Every filter in the app is rendered from this. */
export const apiAvailability = (board: string, classGrade: number) =>
  req<Availability>(
    `/catalog/availability?board=${encodeURIComponent(board)}&class_grade=${classGrade}`);
export interface CourseQuery {
  class_grade?: number | null; board?: string | null; subject_id?: number | null;
  lang?: string | null; difficulty?: string | null; free_only?: boolean;
  stream?: string | null;
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
export const apiTextbooks = (classGrade: number, board: string, lang?: string | null, subjectName?: string | null, stream?: string | null) => {
  const p = new URLSearchParams({ class_grade: String(classGrade), board });
  if (lang) p.set('lang', lang);
  if (subjectName) p.set('subject_name', subjectName);
  if (stream) p.set('stream', stream);
  return req<Textbook[]>(`/textbooks?${p.toString()}`);
};
export const apiTextbookPortals = () =>
  req<{ name: string; url: string; boards: string[]; langs: string[] }[]>('/textbooks/portals');
/** Where a book opens. The backend fetches the official PDF itself and
 * streams it back from our own origin — the viewer is a plain same-origin
 * iframe, so nothing visibly redirects to eBalbharati. `mode` switches the
 * response only: 'dl' saves the file, 'ext' is the opt-in "open on the
 * publisher's site" escape hatch. `chapter` pages one NCERT chapter edition
 * (CBSE books with a verified code); the reader discovers the last chapter
 * live, so a 404 just means "no further chapters". */
export const apiTextbookOpenUrl = (id: number, mode?: 'dl' | 'ext', chapter?: number) => {
  const p = new URLSearchParams();
  if (mode) p.set(mode, '1');
  if (chapter) p.set('chapter', String(chapter));
  const q = p.toString();
  return `${BASE}/textbooks/${id}/open${q ? `?${q}` : ''}`;
};

// ---------- library (Smart Book Finder) ----------
/** Tier order server-side: this class's library (ms) → live official portal
 * scan (seconds) → request queue. Never throws the book away: a miss comes
 * back as `result: 'queued'` with a queue position, not an error. */
export const apiLocate = (q: string, classGrade: number | null, board: string, lang: string, stream?: string | null) =>
  post<LocateResult>('/library/locate', { q, class_grade: classGrade, board, lang, stream: stream || '' });
/** The signed-in learner's own asks (401 when anonymous — callers ignore). */
export const apiMyRequests = () => req<BookAsk[]>('/library/requests');

// ---------- library (Monthly Reading List) ----------
/** Public book-club list: this month and the two before it, newest first.
 * `mine=1` is the signed-in teacher's own picks (401 otherwise).
 * `stream` narrows to one 11-12 stream (common picks stay included). */
export const apiReadingList = (mine = false, stream?: string | null) =>
  req<ReadingPick[]>(`/library/reading${mine ? '?mine=1' : ''}${!mine && stream ? `?stream=${encodeURIComponent(stream)}` : ''}`);
/** Approved teachers only (401 anonymous, 403 student/pending). Posting the
 * same title again in the same month rewrites it instead of duplicating. */
export const apiSavePick = (payload: Partial<ReadingPick>) =>
  post<ReadingPick>('/library/reading', payload);
/** Withdraw a pick: the owner's, or an admin's. */
export const apiDeletePick = (id: number) =>
  req<{ deleted: number }>(`/library/reading/${id}`, { method: 'DELETE' });

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
export const apiMaterials = (opts: { class_grade?: number; board?: string; subject_name?: string; type?: string; lang?: string; mine?: boolean; stream?: string }) => {
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
export const apiDoubts = (stream?: string | null) =>
  req<Doubt[]>(`/doubts${stream ? `?stream=${encodeURIComponent(stream)}` : ''}`);
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
export const apiProgressWeekly = () => req<{ date: string; minutes: number }[]>('/progress/weekly');
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

// ---------- growth (referrals, money config) ----------
export const apiGrowthConfig = () => req<{
  site_url: string; referral_enabled: boolean;
  ads: { client: string; slot: string } | null;
  donate: { upi: string | null; url: string | null } | null;
  affiliates: { name: string; url: string }[];
  sponsor: { text: string; url: string } | null;
  premium_url: string | null;
}>('/growth/config');
export const apiGrowthMe = () => req<{ referral_code: string; referrals: number }>('/growth/me');
export const apiLeaderboard = () => req<{ name: string; referrals: number }[]>('/growth/leaderboard');
