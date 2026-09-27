# GramShiksha — Architecture

## 1. High-level

```
┌─────────────────────────────────────────────────────────────┐
│  React 18 + Vite + TS SPA (mobile-first, PWA)               │
│  landing · student · teacher · parent · school · admin      │
│  service worker: shell cache-first / API network-first      │
│  localStorage: token, lang, data-saver, lesson cache,       │
│  downloads index, offline sync queue                        │
└────────────────────────┬────────────────────────────────────┘
                         │ /api/* (JSON; files via multipart)
┌────────────────────────▼────────────────────────────────────┐
│  FastAPI (Python 3.10+)                                     │
│  routers: auth, catalog, lessons, quiz, practice, materials,│
│  textbooks, doubts, bookmarks, notifications, gamification, │
│  parent, school, admin, search, downloads-sync              │
│  security: JWT + role deps; validation via Pydantic         │
└────────────────────────┬────────────────────────────────────┘
                         │ SQLModel / SQLAlchemy
┌────────────────────────▼────────────────────────────────────┐
│  SQLite (dev, zero-config)  │  Postgres (Neon/Supabase free)│
└─────────────────────────────────────────────────────────────┘
```

## 2. Data model (core tables)

```
User(role: student|teacher|parent|school_admin|platform_admin,
     class_grade, board, lang_pref, school_id, xp, streak_days, last_active_date,
     parent_of → self-fk for parent-child link)
School(name, medium)
Board(name)                     # Maharashtra SSC, Maharashtra HSC, CBSE
Subject(name_en/hi/mr, class_grade)
Course(subject, board, class_grade, lang, teacher_id, title_en/hi/mr, desc, thumb,
       difficulty, duration_min, rating, ratings_count, students_count, is_free)
Chapter(course, order, title_en/hi/mr)
Lesson(chapter, order, type: video|text|audio|mixed, title/body ×3 lang,
       video_url, audio_url, video_url_low, duration_min, estimate_mb)
Question(lesson|chapter|course|topic, type: mcq|truefalse|multi|fill,
         prompt ×3, options ×3 (JSON), correct (JSON), explanation ×3, difficulty, topic)
Quiz(chapter|lesson, title, time_limit_min)
QuizQuestion(quiz, question, order)
QuizAttempt(user, quiz, answers JSON, score, max_score, time_taken_s, created)
PracticeAttempt(user, question, chosen JSON, correct bool, topic, created)
Progress(user, lesson, completed, score, updated)   # lesson-level completion
TopicStats(user, subject, topic, attempted, correct) # weak-topic detection
Material(title, desc, type, class_grade, board, subject, chapter, lang,
         uploader, uploader_role, visibility: private|school|public,
         status: pending|approved|needs_changes|rejected, reviewer, review_reason,
         source_of_content, file_path, downloads, views)
Textbook(board, class_grade, subject, lang, title, source_url)  # official links only
Doubt(student, subject, chapter, text, image_path, status: pending|answered|resolved)
DoubtReply(doubt, teacher, body)
Bookmark(user, lesson|course|question)
Note(user, lesson, body)
Notification(user, type, payload JSON, read)
BadgeDef(code, title ×3, desc ×3) / UserBadge(user, badge, awarded_at)
Certificate(user, course, cert_id, issued_at)
Enrollment(user, course, progress_pct)
```

## 3. Key flows

**Weak topics (rule-based, explainable):** every practice/quiz answer updates
`TopicStats(user, topic)`. `accuracy = correct/attempted`; `attempted ≥ 5 and
accuracy < 0.5` ⇒ weak. API returns weak topics with recommended easy questions.

**Learning path / Today's Learning:** deterministic generator:
1. continue first incomplete lesson of enrolled courses,
2. practice set (10 Q) from weakest topic, else next chapter's topic,
3. revision = weakest topic's revision quiz.
Ordered plan with per-item estimate; progress tracked per day.

**Material approval:** student upload ⇒ `pending`; teacher/admin review ⇒
approved/needs_changes/rejected + reason; only `approved` appears in public library;
visibility scopes: private (own students) / school / public.

**Offline sync:** client queues completed lessons/quiz attempts in localStorage while
offline; on reconnect POSTs `/sync` batch; server upserts idempotently.

**Gamification:** server awards XP on events (lesson+10, quiz attempt+5, perfect+20,
course+100); streak = consecutive active days; badges on milestones (first_lesson,
first_quiz, streak_7, streak_30, perfect_score, course_complete, practice_master).

## 4. Security

- bcrypt password hashing; JWT (7d expiry); role dependencies per route group.
- Uploads: extension + content-type whitelist (pdf, png, jpg, webp, mp3, m4a), 10 MB cap,
  random filenames under `uploads/`, never executed; private until approved.
- Input validation via Pydantic schemas everywhere; parameterized queries via SQLModel.
- CORS restricted to frontend origins; secrets via env.

## 5. Performance for rural reality

- Initial JS ≤ ~60 KB gzip; React only, no heavy UI kit.
- Pagination on all list endpoints; `limit/offset`.
- Data Saver mode: text-only rendering, poster-only video (tap to load), lazy images,
  no autoplay, no animations; estimated per-item data usage where known.
- Service worker precaches shell; lesson text cached after first read; downloads
  stored client-side (IndexedDB-ready via localStorage index in v1).

## 6. Roles → surfaces

| Role | Surface |
|---|---|
| student | dashboard, today's learning, courses, lesson player, practice, quizzes, materials, textbooks, doubts, bookmarks/notes, downloads, progress, profile |
| teacher | my courses, create course/chapter/lesson/quiz, upload material, review student material, answer doubts, student monitor |
| parent | child summary: progress, study time, quiz avg, weak subjects, achievements |
| school_admin | students/teachers/announcements/school stats |
| platform_admin | users, content approvals, reports, notifications, all dashboards |
