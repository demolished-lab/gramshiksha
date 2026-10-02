export type Lang = 'en' | 'hi' | 'mr';
export type Role = 'student' | 'teacher' | 'parent' | 'school_admin' | 'platform_admin';
/** Approval state — a self-registered teacher is `pending` until a platform
 * admin approves it; `suspended` is an approval that was withdrawn. */
export type RoleStatus = 'pending' | 'active' | 'suspended';

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: Role;
  role_status?: RoleStatus;
  name: string;
  lang_pref: Lang;
  class_grade: number | null;
  board: string | null;
  xp: number;
  streak_days: number;
}

/** One medium (instruction language) that actually has books for a
 * (board, class) — rendered as an explore chip. */
export interface AvailabilityMedium {
  lang: string;
  label: string;
  books: number;
  subjects: number;
}

/** A subject that actually has rows — books in some medium and/or lessons.
 * `name_hi`/`name_mr` are null when no translation row exists for this
 * (board, class); `subject_id` likewise (book-only subject, no Subject row). */
export interface AvailabilitySubject {
  name: string;
  name_hi: string | null;
  name_mr: string | null;
  subject_id: number | null;
  books_by_lang: Record<string, number>;
  courses: number;
  lessons: number;
  course_ids: number[];
}

export interface Availability {
  board: string;
  class_grade: number;
  mediums: AvailabilityMedium[];
  subjects: AvailabilitySubject[];
}

export interface Me {
  id: number;
  email: string;
  name: string;
  role: Role;
  role_status?: RoleStatus;
  lang_pref: Lang;
  class_grade: number | null;
  board: string | null;
  school_id: number | null;
  xp: number;
  streak_days: number;
  profile_pic: string | null;
}

export interface Subject {
  id: number;
  name_en: string;
  name_hi: string;
  name_mr: string;
}

export interface Course {
  id: number;
  slug: string;
  title_en: string;
  title_hi: string;
  title_mr: string;
  desc_en: string;
  desc_hi: string;
  desc_mr: string;
  board: string;
  class_grade: number;
  subject_id: number;
  lang: string;
  difficulty: string;
  duration_min: number;
  rating: number;
  ratings_count: number;
  students_count: number;
  is_free: boolean;
  thumb_color: string;
  teacher_id: number | null;
  progress_pct?: number;
  chapters?: Chapter[];
}

export interface Chapter {
  id: number;
  order: number;
  title_en: string;
  title_hi: string;
  title_mr: string;
  lessons: LessonRef[];
}

export interface LessonRef {
  id: number;
  order: number;
  type: string;
  title_en: string;
  title_hi: string;
  title_mr: string;
  duration_min: number;
  estimate_mb: number;
}

export interface LessonDetail {
  id: number;
  type: string;
  title: string;
  body: string;
  video_url: string | null;
  video_url_low: string | null;
  audio_url: string | null;
  duration_min: number;
  estimate_mb: number;
  course_id: number | null;
  course_title: string | null;
  chapter_id: number | null;
  chapter_title: string | null;
  completed: boolean;
  questions: Question[];
}

export interface Question {
  id: number;
  type: 'mcq' | 'truefalse' | 'multi' | 'fill';
  prompt: string;
  options: string[];
  difficulty: string;
  topic: string;
}

export interface QuizDetail {
  id: number;
  title: string;
  time_limit_min: number;
  questions: Question[];
}

export interface QuizResult {
  score: number;
  max_score: number;
  percentage: number;
  time_taken_s: number;
  per_question: {
    question_id: number;
    correct: boolean;
    correct_answer: number | number[];
    explanation: string;
  }[];
}

export interface TodayPlan {
  date: string;
  items: { kind: string; slot: number; label: string; minutes?: number; topic?: string; question_ids?: number[]; lesson_id?: number }[];
  study_minutes_today: number;
  xp: number;
  streak_days: number;
}

export interface WeakTopics {
  weak: { subject: string; topic: string; attempted: number; correct: number; accuracy_pct: number }[];
  message: string;
}

export interface Material {
  id: number;
  title: string;
  description: string;
  type: string;
  class_grade: number;
  board: string;
  subject_name: string;
  chapter_title: string;
  lang: string;
  status: string;
  visibility: string;
  source_of_content: string;
  file_size: number;
  downloads: number;
  views: number;
  mine: boolean;
  created_at: string;
}

export interface Textbook {
  id: number;
  title: string;
  board: string;
  class_grade: number;
  subject_name: string;
  lang: string;
  source_url: string;
  publisher: string;
  has_deep_link: boolean;
  cover_url: string | null;
  /** 'Part 1'/'Part 2' for multi-part subjects; null for whole books. */
  part_label: string | null;
  clicks: number;
}

/** POST /library/locate — Smart Book Finder's one honest answer.
 * `eta_seconds`/`elapsed_s` are both reported so the UI can show what a scan
 * *should* take and what it actually took, never an optimistic fake. */
export interface LocateResult {
  result: 'found' | 'queued';
  source?: 'library' | 'official';
  books?: Textbook[];
  scanned_langs?: string[];
  position?: number;
  pending?: boolean;
  eta_seconds: number;
  elapsed_s: number;
}

/** GET /library/requests — one queued ask and where it stands. */
export interface BookAsk {
  id: number;
  query: string;
  class_grade: number | null;
  status: 'pending' | 'found' | 'declined';
  textbook_id: number | null;
  created_at: string;
  found_at: string | null;
}

export interface Doubt {
  id: number;
  text: string;
  subject_name: string;
  chapter_title: string;
  status: 'pending' | 'answered' | 'resolved';
  created_at: string;
  student_name: string;
  replies: { teacher_id: number; body: string; created_at: string }[];
}

export interface Notification {
  id: number;
  type: string;
  payload: Record<string, string | number>;
  read: boolean;
  created_at: string;
}

export interface ProgressSummary {
  lessons_completed: number;
  quizzes_taken: number;
  quiz_avg_pct: number | null;
  week_minutes: number;
  week_lessons: number;
  week_quizzes: number;
  xp: number;
  streak_days: number;
  badges: { code: string; title_en: string; awarded_at: string }[];
  certificates: { cert_id: string; course_id: number; issued_at: string }[];
}

export interface ParentChild {
  id: number;
  name: string;
  class_grade: number | null;
  board: string | null;
  lessons_completed: number;
  week_minutes: number;
  quiz_avg_pct: number | null;
  weak_subjects: string[];
  streak_days: number;
  xp: number;
  badges: number;
  certificates: number;
}

export interface TeacherStudent {
  id: number;
  name: string;
  class_grade: number | null;
  board: string | null;
  lessons_completed: number;
  quizzes: number;
  quiz_avg_pct: number | null;
  weak_topics: { topic: string; subject: string; accuracy_pct: number }[];
  pending_doubts: number;
  streak_days: number;
  xp: number;
}
