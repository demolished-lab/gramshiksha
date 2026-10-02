"""GramShiksha data models — Class 1-12, boards, courses, quizzes, practice,
materials with approval workflow, doubts, gamification, multi-role users."""
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


BOARDS = ["Maharashtra SSC", "Maharashtra HSC", "CBSE"]
LANGS = ["en", "hi", "mr"]
ROLES = ["student", "teacher", "parent", "school_admin", "platform_admin"]
MATERIAL_TYPES = ["notes", "chapter_notes", "revision_notes", "question_paper", "practice_paper",
                  "worksheet", "sample_paper", "important_questions", "diagram", "formula_sheet",
                  "project", "reference", "audio"]
MATERIAL_STATUSES = ["pending", "approved", "needs_changes", "rejected"]
QUESTION_TYPES = ["mcq", "truefalse", "multi", "fill"]
DIFFICULTIES = ["easy", "medium", "hard"]
REPORT_REASONS = ["incorrect", "duplicate", "poor_quality", "copyright", "inappropriate",
                  "wrong_class_subject", "other"]


class School(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    medium: str = "marathi"
    village: str = ""


class Board(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)  # Maharashtra SSC | Maharashtra HSC | CBSE


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str
    hashed_password: str
    role: str = "student"
    # active | pending | suspended. Self-registered teachers start pending and
    # hold no privileges until a platform admin approves them; suspend
    # withdraws an approval again (see security.require_roles).
    role_status: str = "active"
    lang_pref: str = "hi"  # en | hi | mr
    class_grade: Optional[int] = Field(default=None)  # 1..12
    board: Optional[str] = Field(default=None)
    school_id: Optional[int] = Field(default=None, foreign_key="school.id")
    parent_of_id: Optional[int] = Field(default=None, foreign_key="user.id")  # child id (on parent user)
    xp: int = 0
    streak_days: int = 0
    last_active_date: Optional[str] = Field(default=None)  # ISO date
    profile_pic: Optional[str] = None
    # Referral loop: who invited this account (nullable FK to user.id).
    # The public code is derived, "GS%06d" % id — no extra column needed.
    referred_by: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)

    courses_taught: list["Course"] = Relationship(back_populates="teacher")


class Subject(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name_en: str
    name_hi: str
    name_mr: str
    class_grade: int = Field(index=True)
    board: str = Field(default="CBSE", index=True)


class Course(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    subject_id: int = Field(foreign_key="subject.id", index=True)
    board: str = Field(index=True)
    class_grade: int = Field(index=True)
    lang: str = "en"  # primary teaching language
    title_en: str
    title_hi: str
    title_mr: str
    desc_en: str = ""
    desc_hi: str = ""
    desc_mr: str = ""
    teacher_id: Optional[int] = Field(default=None, foreign_key="user.id")
    difficulty: str = "easy"
    duration_min: int = 120
    rating: float = 4.5
    ratings_count: int = 0
    students_count: int = 0
    is_free: bool = True
    thumb_color: str = "#2563EB"
    published: bool = True
    created_at: datetime = Field(default_factory=utcnow)

    teacher: Optional[User] = Relationship(back_populates="courses_taught")
    chapters: list["Chapter"] = Relationship(back_populates="course")


class Chapter(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    order: int = 1
    title_en: str
    title_hi: str
    title_mr: str

    course: Optional[Course] = Relationship(back_populates="chapters")
    lessons: list["Lesson"] = Relationship(back_populates="chapter")


class Lesson(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chapter_id: int = Field(foreign_key="chapter.id", index=True)
    order: int = 1
    type: str = "text"  # text | video | audio | mixed
    title_en: str
    title_hi: str
    title_mr: str
    body_en: str = ""
    body_hi: str = ""
    body_mr: str = ""
    video_url: Optional[str] = None
    video_url_low: Optional[str] = None
    audio_url: Optional[str] = None
    duration_min: int = 10
    estimate_mb: float = 0.1  # estimated data usage for data-saver UI
    published: bool = True

    chapter: Optional[Chapter] = Relationship(back_populates="lessons")
    progress: list["Progress"] = Relationship(back_populates="lesson")
    bookmarks: list["Bookmark"] = Relationship(back_populates="lesson")
    notes: list["Note"] = Relationship(back_populates="lesson")


class Question(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lesson_id: Optional[int] = Field(default=None, foreign_key="lesson.id", index=True)
    chapter_id: Optional[int] = Field(default=None, foreign_key="chapter.id", index=True)
    type: str = "mcq"  # mcq | truefalse | multi | fill
    prompt_en: str
    prompt_hi: str
    prompt_mr: str
    options_en: str = ""   # JSON list; empty for fill
    options_hi: str = ""
    options_mr: str = ""
    correct: str = "0"     # JSON: "0" | "[0,2]" for multi | "text" for fill
    explanation_en: str = ""
    explanation_hi: str = ""
    explanation_mr: str = ""
    difficulty: str = "easy"
    topic: str = Field(default="general", index=True)
    subject_name: str = "general"  # denormalized for weak-topic stats


class Quiz(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title_en: str
    title_hi: str
    title_mr: str
    chapter_id: Optional[int] = Field(default=None, foreign_key="chapter.id", index=True)
    lesson_id: Optional[int] = Field(default=None, foreign_key="lesson.id", index=True)
    time_limit_min: int = 15

    questions: list["QuizQuestion"] = Relationship(back_populates="quiz")


class QuizQuestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quiz_id: int = Field(foreign_key="quiz.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    order: int = 1

    quiz: Optional[Quiz] = Relationship(back_populates="questions")
    question: Optional[Question] = Relationship()


class QuizAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    quiz_id: int = Field(foreign_key="quiz.id", index=True)
    answers: str = "[]"      # JSON list of answer payloads
    score: float = 0.0
    max_score: float = 0.0
    time_taken_s: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class PracticeAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    chosen: str = ""         # JSON payload
    correct: bool = False
    topic: str = Field(default="general", index=True)
    subject_name: str = "general"
    created_at: datetime = Field(default_factory=utcnow)


class TopicStats(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    subject_name: str = Field(index=True)
    topic: str = Field(index=True)
    attempted: int = 0
    correct: int = 0

    # computed: accuracy = correct/attempted; weak if attempted>=5 and accuracy<0.5


class Progress(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    lesson_id: int = Field(foreign_key="lesson.id", index=True)
    completed: bool = False
    score: Optional[float] = None
    updated_at: datetime = Field(default_factory=utcnow)

    lesson: Optional[Lesson] = Relationship(back_populates="progress")


class Enrollment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    progress_pct: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)


class Batch(SQLModel, table=True):
    """A teacher-owned class group, created via POST /progress/batches."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    teacher_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Material(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str = ""
    type: str = "notes"          # MATERIAL_TYPES
    class_grade: int = Field(index=True)
    board: str = Field(index=True)
    subject_name: str = Field(index=True)
    chapter_title: str = ""
    lang: str = "en"
    uploader_id: int = Field(foreign_key="user.id", index=True)
    uploader_role: str = "teacher"
    visibility: str = "public"   # private | school | public
    status: str = "approved"     # pending | approved | needs_changes | rejected
    review_reason: str = ""
    reviewer_id: Optional[int] = Field(default=None, foreign_key="user.id")
    source_of_content: str = "Created by teacher"
    file_path: str = ""          # uploads/<random>.<ext>
    file_size: int = 0
    downloads: int = 0
    views: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class MaterialReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    material_id: int = Field(foreign_key="material.id", index=True)
    reporter_id: int = Field(foreign_key="user.id")
    reason: str = "other"
    detail: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Textbook(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    board: str = Field(index=True)
    class_grade: int = Field(index=True)
    subject_name: str = Field(index=True)
    lang: str = Field(index=True)
    # "Part 1"/"Part 2" for multi-part subjects (e.g. परिसर अभ्यास भाग-१/२);
    # set only by the crawler/apply — a partless book leaves it empty.
    part_label: str = ""
    title: str
    source_url: str  # official portal link only (ePathshala / eBalbharati)
    publisher: str = "NCERT"
    # Deep link to the actual PDF + cover, filled by scripts/crawl_ebalbharati.py.
    # Never hand-written: only URLs verified live (HTTP 200, application/pdf).
    deep_url: str = ""
    cover_url: str = ""
    clicks: int = 0  # opened via /textbooks/{id}/open
    last_checked: Optional[str] = Field(default=None)  # ISO datetime of last HEAD check
    last_ok: bool = True  # False → /open falls back to source_url


class Doubt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="user.id", index=True)
    subject_name: str = "general"
    chapter_title: str = ""
    text: str
    image_path: Optional[str] = None
    status: str = "pending"  # pending | answered | resolved
    created_at: datetime = Field(default_factory=utcnow)


class DoubtReply(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    doubt_id: int = Field(foreign_key="doubt.id", index=True)
    teacher_id: int = Field(foreign_key="user.id")
    body: str
    created_at: datetime = Field(default_factory=utcnow)


class Bookmark(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    lesson_id: Optional[int] = Field(default=None, foreign_key="lesson.id")
    course_id: Optional[int] = Field(default=None, foreign_key="course.id")
    question_id: Optional[int] = Field(default=None, foreign_key="question.id")

    lesson: Optional[Lesson] = Relationship(back_populates="bookmarks")


class Note(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    lesson_id: int = Field(foreign_key="lesson.id", index=True)
    body: str
    created_at: datetime = Field(default_factory=utcnow)

    lesson: Optional[Lesson] = Relationship(back_populates="notes")


class Notification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    type: str = "info"
    payload: str = "{}"  # JSON: title/body per lang or structured
    read: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class BadgeDef(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True)
    title_en: str
    title_hi: str
    title_mr: str
    desc_en: str = ""
    desc_hi: str = ""
    desc_mr: str = ""


class UserBadge(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    badge_code: str = Field(index=True)
    awarded_at: datetime = Field(default_factory=utcnow)


class Certificate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    course_id: int = Field(foreign_key="course.id")
    cert_id: str = Field(unique=True)
    issued_at: datetime = Field(default_factory=utcnow)


class DailyActivity(SQLModel, table=True):
    """Study time + activity per day for streaks, Today's Learning and parent view."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    date: str = Field(index=True)  # ISO date
    minutes: int = 0
    lessons_completed: int = 0
    quizzes_taken: int = 0


class PasswordResetCode(SQLModel, table=True):
    """One-time codes for /auth/reset-request + /auth/reset-confirm.

    Stored in the DB rather than process memory so codes survive restarts and
    work across multiple workers. Only a SHA-256 hash is kept — a leaked DB
    dump can't be replayed into account takeovers. `expires_at` is an ISO-8601
    UTC string to stay timezone-safe on both SQLite and Postgres."""
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    code_hash: str
    expires_at: str  # ISO-8601 UTC
    used_at: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
