import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..gamification import log_study_time, on_course_complete, on_lesson_complete, on_practice, on_quiz
from ..models import (Chapter, Course, Enrollment, Lesson, PracticeAttempt, Progress,
                      Question, Quiz, QuizAttempt, QuizQuestion, TopicStats, User, utcnow)
from ..security import get_current_user, optional_user, require_student

router = APIRouter(prefix="/learn", tags=["learn"])


def _pick(lang: str, en: str, hi: str, mr: str) -> str:
    return {"en": en, "hi": hi, "mr": mr}.get(lang, en)


# ---------- Lessons ----------

@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: int, lang: str = "en", session: Session = Depends(get_session),
               user: User = Depends(get_current_user)):
    lesson = session.get(Lesson, lesson_id)
    if not lesson or not lesson.published:
        raise HTTPException(404, "Lesson not found")
    chapter = session.get(Chapter, lesson.chapter_id)
    course = session.get(Course, chapter.course_id) if chapter else None
    questions = session.exec(select(Question).where(Question.lesson_id == lesson_id)).all()
    prog = session.exec(select(Progress).where(
        Progress.user_id == user.id, Progress.lesson_id == lesson_id)).first()
    return {
        "id": lesson.id, "type": lesson.type,
        "title": _pick(lang, lesson.title_en, lesson.title_hi, lesson.title_mr),
        "body": _pick(lang, lesson.body_en, lesson.body_hi, lesson.body_mr),
        "video_url": lesson.video_url, "video_url_low": lesson.video_url_low,
        "audio_url": lesson.audio_url, "duration_min": lesson.duration_min,
        "estimate_mb": lesson.estimate_mb,
        "course_id": course.id if course else None,
        "course_title": _pick(lang, course.title_en, course.title_hi, course.title_mr) if course else None,
        "chapter_id": chapter.id if chapter else None,
        "chapter_title": _pick(lang, chapter.title_en, chapter.title_hi, chapter.title_mr) if chapter else None,
        "completed": bool(prog and prog.completed),
        "questions": [_question_out(q, lang, hide_answer=True) for q in questions],
    }


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: int, minutes: int = Query(10, le=120),
                    user: User = Depends(require_student),
                    session: Session = Depends(get_session)):
    lesson = session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    prog = session.exec(select(Progress).where(
        Progress.user_id == user.id, Progress.lesson_id == lesson_id)).first()
    first_time = prog is None or not prog.completed
    if not prog:
        prog = Progress(user_id=user.id, lesson_id=lesson_id)
    prog.completed = True
    prog.updated_at = utcnow()
    session.add(prog)
    if first_time:
        on_lesson_complete(session, user)
        log_study_time(session, user, minutes)
        _update_course_progress(session, user, lesson)
    session.add(user)
    session.commit()
    return {"ok": True, "xp": user.xp, "streak_days": user.streak_days}


def _update_course_progress(session: Session, user: User, lesson: Lesson) -> None:
    chapter = session.get(Chapter, lesson.chapter_id)
    if not chapter:
        return
    course = session.get(Course, chapter.course_id)
    if not course:
        return
    all_lessons = session.exec(
        select(Lesson.id).join(Chapter, Chapter.id == Lesson.chapter_id).where(
            Chapter.course_id == course.id)).all()
    done = session.exec(
        select(Progress.lesson_id).where(Progress.user_id == user.id,
                                         Progress.completed == True)).all()  # noqa: E712
    pct = round(100.0 * len(set(done) & set(all_lessons)) / max(1, len(all_lessons)), 1)
    enr = session.exec(select(Enrollment).where(
        Enrollment.user_id == user.id, Enrollment.course_id == course.id)).first()
    if not enr:
        enr = Enrollment(user_id=user.id, course_id=course.id)
    enr.progress_pct = pct
    session.add(enr)
    if pct >= 100.0:
        on_course_complete(session, user)
        from ..models import Certificate
        import uuid
        exists = session.exec(select(Certificate).where(
            Certificate.user_id == user.id, Certificate.course_id == course.id)).first()
        if not exists:
            session.add(Certificate(user_id=user.id, course_id=course.id,
                                    cert_id=f"GS-{uuid.uuid4().hex[:10].upper()}"))


# ---------- Quiz engine ----------

class QuizSubmit(BaseModel):
    answers: list[dict] = Field(min_length=1)  # [{question_id, answer}]
    time_taken_s: int = Field(default=0, ge=0, le=4 * 3600)


@router.get("/quizzes-by-chapter/{chapter_id}")
def get_quiz_by_chapter(chapter_id: int, lang: str = "en", session: Session = Depends(get_session),
                       user: User = Depends(get_current_user)):
    quiz = session.exec(select(Quiz).where(Quiz.chapter_id == chapter_id)).first()
    if not quiz:
        raise HTTPException(404, "No quiz for this chapter")
    return get_quiz(quiz.id, lang, session, user)


@router.get("/quizzes/{quiz_id}")
def get_quiz(quiz_id: int, lang: str = "en", session: Session = Depends(get_session),
             user: User = Depends(get_current_user)):
    quiz = session.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    rows = session.exec(select(QuizQuestion).where(
        QuizQuestion.quiz_id == quiz_id).order_by(QuizQuestion.order)).all()
    qs = []
    for rq in rows:
        q = session.get(Question, rq.question_id)
        if q:
            qs.append(_question_out(q, lang, hide_answer=True))
    return {"id": quiz.id, "title": _pick(lang, quiz.title_en, quiz.title_hi, quiz.title_mr),
            "time_limit_min": quiz.time_limit_min, "questions": qs}


@router.post("/quizzes/{quiz_id}/submit")
def submit_quiz(quiz_id: int, payload: QuizSubmit, lang: str = "en",
                user: User = Depends(require_student),
                session: Session = Depends(get_session)):
    quiz = session.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    rows = session.exec(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)).all()
    questions = [session.get(Question, r.question_id) for r in rows]
    questions = [q for q in questions if q]

    by_id = {a.get("question_id"): a.get("answer") for a in payload.answers}
    score = 0.0
    max_score = float(len(questions))
    per_question = []
    for q in questions:
        ans = by_id.get(q.id)
        ok, correct_payload = _grade(q, ans)
        if ok:
            score += 1
        per_question.append({
            "question_id": q.id, "correct": ok, "correct_answer": correct_payload,
            "explanation": _pick(lang, q.explanation_en, q.explanation_hi, q.explanation_mr),
        })
        # practice-style topic stats from quizzes too
        _record_topic(session, user, q, ok)
    score_pct = round(100.0 * score / max(1, max_score), 2)
    session.add(QuizAttempt(user_id=user.id, quiz_id=quiz_id,
                            answers=json.dumps(payload.answers, ensure_ascii=False),
                            score=score, max_score=max_score,
                            time_taken_s=payload.time_taken_s))
    on_quiz(session, user, score_pct)
    session.add(user)
    session.commit()
    return {"score": score, "max_score": max_score, "percentage": score_pct,
            "time_taken_s": payload.time_taken_s, "per_question": per_question}


# ---------- Practice engine ----------

@router.get("/practice/questions")
def practice_questions(class_grade: Optional[int] = Query(None, ge=1, le=12),
                       board: Optional[str] = None,
                       subject_name: Optional[str] = None, topic: Optional[str] = None,
                       difficulty: Optional[str] = None, limit: int = Query(10, le=50),
                       lang: str = "en", session: Session = Depends(get_session),
                       user: Optional[User] = Depends(optional_user)):
    # Free content: anyone may read questions (answers stay hidden server-side
    # and grading still needs a signed-in student).
    q = select(Question).where(Question.difficulty.isnot(None))
    if subject_name:
        q = q.where(Question.subject_name == subject_name)
    if topic:
        q = q.where(Question.topic == topic)
    if difficulty:
        q = q.where(Question.difficulty == difficulty)
    rows = session.exec(q.limit(limit)).all()
    return [_question_out(r, lang, hide_answer=True) for r in rows]


class PracticeSubmit(BaseModel):
    question_id: int
    answer: object = None
    minutes: int = Field(default=0, ge=0, le=120)


@router.post("/practice/answer")
def practice_answer(payload: PracticeSubmit, lang: str = "en",
                    user: User = Depends(require_student),
                    session: Session = Depends(get_session)):
    q = session.get(Question, payload.question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    ok, correct_payload = _grade(q, payload.answer)
    session.add(PracticeAttempt(user_id=user.id, question_id=q.id,
                                chosen=json.dumps(payload.answer, ensure_ascii=False, default=str),
                                correct=ok, topic=q.topic, subject_name=q.subject_name))
    _record_topic(session, user, q, ok)
    on_practice(session, user)
    if payload.minutes:
        log_study_time(session, user, payload.minutes)
    session.add(user)
    session.commit()
    return {"correct": ok, "correct_answer": correct_payload,
            "explanation": _pick(lang, q.explanation_en, q.explanation_hi, q.explanation_mr)}


# ---------- Weak topics ----------

@router.get("/weak-topics")
def weak_topics(user: User = Depends(require_student), session: Session = Depends(get_session)):
    rows = session.exec(select(TopicStats).where(TopicStats.user_id == user.id)).all()
    weak = []
    for r in rows:
        if r.attempted >= 5 and (r.correct / r.attempted) < 0.5:
            weak.append({"subject": r.subject_name, "topic": r.topic,
                         "attempted": r.attempted, "correct": r.correct,
                         "accuracy_pct": round(100.0 * r.correct / r.attempted, 1)})
    return {"weak": weak,
            "message": "Revise these topics before attempting the next test" if weak else ""}


# ---------- Learning path + Today ----------

@router.get("/path")
def learning_path(lang: str = "en", user: User = Depends(require_student),
                  session: Session = Depends(get_session)):
    enrollments = session.exec(select(Enrollment).where(Enrollment.user_id == user.id)).all()
    continue_item, recommended, revision = None, None, None

    for e in enrollments:
        course = session.get(Course, e.course_id)
        if not course:
            continue
        chapters = session.exec(select(Chapter).where(
            Chapter.course_id == course.id).order_by(Chapter.order)).all()
        for ch in chapters:
            lessons = session.exec(select(Lesson).where(
                Lesson.chapter_id == ch.id).order_by(Lesson.order)).all()
            for les in lessons:
                prog = session.exec(select(Progress).where(
                    Progress.user_id == user.id, Progress.lesson_id == les.id)).first()
                if not prog or not prog.completed:
                    continue_item = {
                        "kind": "lesson", "lesson_id": les.id,
                        "label": f"{_pick(lang, course.title_en, course.title_hi, course.title_mr)} → "
                                 f"{_pick(lang, ch.title_en, ch.title_hi, ch.title_mr)} → "
                                 f"{_pick(lang, les.title_en, les.title_hi, les.title_mr)}",
                        "minutes": les.duration_min}
                    break
            if continue_item:
                break
        if continue_item:
            break

    weak_rows = session.exec(select(TopicStats).where(TopicStats.user_id == user.id)).all()
    weak = [r for r in weak_rows if r.attempted >= 3 and (r.correct / r.attempted) < 0.6]
    if weak:
        w = sorted(weak, key=lambda r: r.correct / r.attempted)[0]
        revision = {"kind": "revision", "subject": w.subject_name, "topic": w.topic,
                    "accuracy_pct": round(100 * w.correct / w.attempted, 1)}
        q = select(Question).where(Question.topic == w.topic, Question.difficulty == "easy")
        qrows = session.exec(q.limit(10)).all()
        recommended = {"kind": "practice", "topic": w.topic,
                       "count": len(qrows),
                       "question_ids": [x.id for x in qrows]}
    return {"continue": continue_item, "recommended_practice": recommended, "revision": revision}


@router.get("/today")
def today(lang: str = "en", user: User = Depends(require_student),
          session: Session = Depends(get_session)):
    path = learning_path(lang, user, session)
    from datetime import date
    today_iso = date.today().isoformat()
    items = []
    if path["continue"]:
        items.append({**path["continue"], "slot": 1})
    if path["recommended_practice"]:
        items.append({"kind": "practice_quiz", "slot": 2,
                      "label": f"Practice quiz — {path['recommended_practice']['topic']} — 10 questions",
                      "topic": path["recommended_practice"]["topic"],
                      "question_ids": path["recommended_practice"]["question_ids"][:10]})
    if path["revision"]:
        items.append({"kind": "revision", "slot": 3,
                      "label": f"Revision — {path['revision']['topic']} — 10 min",
                      "topic": path["revision"]["topic"]})
    from ..models import DailyActivity
    act = session.exec(select(DailyActivity).where(
        DailyActivity.user_id == user.id, DailyActivity.date == today_iso)).first()
    return {"date": today_iso, "items": items,
            "study_minutes_today": act.minutes if act else 0,
            "xp": user.xp, "streak_days": user.streak_days}


# ---------- Offline sync ----------

class SyncItem(BaseModel):
    kind: str  # lesson_complete | quiz_attempt | practice_answer
    lesson_id: Optional[int] = None
    quiz_id: Optional[int] = None
    question_id: Optional[int] = None
    payload: dict = {}


@router.post("/sync")
def sync(items: list[SyncItem], user: User = Depends(require_student),
         session: Session = Depends(get_session)):
    results = []
    for item in items:
        try:
            if item.kind == "lesson_complete" and item.lesson_id:
                complete_lesson(item.lesson_id, item.payload.get("minutes", 10), user, session)
                results.append({"ok": True})
            elif item.kind == "practice_answer" and item.question_id:
                practice_answer(PracticeSubmit(question_id=item.question_id,
                                               answer=item.payload.get("answer"),
                                               minutes=item.payload.get("minutes", 0)),
                                "en", user, session)
                results.append({"ok": True})
            else:
                results.append({"ok": False, "error": "unsupported"})
        except HTTPException as e:
            results.append({"ok": False, "error": e.detail})
    return {"synced": results}


# ---------- helpers ----------

def _question_out(q: Question, lang: str, hide_answer: bool) -> dict:
    return {
        "id": q.id, "type": q.type,
        "prompt": _pick(lang, q.prompt_en, q.prompt_hi, q.prompt_mr),
        "options": json.loads(_pick(lang, q.options_en, q.options_hi, q.options_mr) or "[]"),
        "difficulty": q.difficulty, "topic": q.topic,
        # correct answer & explanation only come from grading endpoints
        "correct": None if hide_answer else q.correct,
        "explanation": None if hide_answer else _pick(lang, q.explanation_en, q.explanation_hi, q.explanation_mr),
    }


def _grade(q: Question, ans) -> tuple[bool, object]:
    correct_raw = q.correct
    if q.type == "mcq" or q.type == "truefalse":
        correct_payload = int(correct_raw)
        try:
            return int(ans) == correct_payload, correct_payload
        except (TypeError, ValueError):
            return False, correct_payload
    if q.type == "multi":
        correct_set = set(json.loads(correct_raw))
        try:
            chosen = set(int(x) for x in (ans or []))
        except (TypeError, ValueError):
            return False, sorted(correct_set)
        return chosen == correct_set, sorted(correct_set)
    if q.type == "fill":
        correct_val = correct_raw.strip().lower()
        given = str(ans or "").strip().lower()
        return given == correct_val, correct_raw
    return False, correct_raw


def _record_topic(session: Session, user: User, q: Question, ok: bool) -> None:
    row = session.exec(select(TopicStats).where(
        TopicStats.user_id == user.id, TopicStats.topic == q.topic,
        TopicStats.subject_name == q.subject_name)).first()
    if not row:
        row = TopicStats(user_id=user.id, subject_name=q.subject_name, topic=q.topic)
    row.attempted += 1
    row.correct += int(ok)
    session.add(row)
