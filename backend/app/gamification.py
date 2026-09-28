"""Gamification: XP, daily streaks, badges. Server-awarded, idempotent badges."""
from datetime import date, datetime, timezone

from sqlmodel import Session, select

from .models import BadgeDef, DailyActivity, Lesson, Notification, User, UserBadge, utcnow

XP_RULES = {
    "lesson_complete": 10,
    "quiz_attempt": 5,
    "quiz_perfect": 20,
    "practice_answer": 1,
    "course_complete": 100,
    "doubt_asked": 2,
}

BADGES = [
    ("first_lesson", "First Lesson", "पहला पाठ", "पहिला धडा", "Completed your first lesson", "आपने पहला पाठ पूरा किया", "तुम्ही पहिला धडा पूर्ण केला"),
    ("first_quiz", "First Quiz", "पहली क्विज़", "पहिली क्विझ", "Attempted your first quiz", "आपने पहली क्विज़ दी", "तुम्ही पहिली क्विझ दिली"),
    ("streak_7", "7 Day Streak", "7 दिन की लय", "7 दिवसांची लय", "7 days of continuous learning", "लगातार 7 दिन सीखा", "सातत्याने 7 दिवस शिकला"),
    ("streak_30", "30 Day Streak", "30 दिन की लय", "30 दिवसांची लय", "30 days of continuous learning", "लगातार 30 दिन सीखा", "सातत्याने 30 दिवस शिकला"),
    ("perfect_score", "Perfect Score", "पूर्ण अंक", "पूर्ण गुण", "Scored 100% in a quiz", "क्विज़ में 100% अंक", "क्विझमध्ये 100% गुण"),
    ("course_complete", "Course Completed", "कोर्स पूर्ण", "कोर्स पूर्ण", "Completed a full course", "पूरा कोर्स पूरा किया", "संपूर्ण कोर्स पूर्ण केला"),
    ("practice_master", "Practice Master", "अभ्यास गुरु", "सराव गुरु", "100 practice questions attempted", "100 अभ्यास प्रश्न हल किए", "100 सराव प्रश्न सोडवले"),
]


def seed_badges(session: Session) -> None:
    for code, te, thi, tmr, de, dhi, dmr in BADGES:
        if not session.exec(select(BadgeDef).where(BadgeDef.code == code)).first():
            session.add(BadgeDef(code=code, title_en=te, title_hi=thi, title_mr=tmr,
                                 desc_en=de, desc_hi=dhi, desc_mr=dmr))
    session.commit()


def award_xp(session: Session, user: User, kind: str, amount: int | None = None) -> None:
    user.xp += amount if amount is not None else XP_RULES.get(kind, 0)


def touch_streak(session: Session, user: User) -> None:
    """Update daily streak + DailyActivity. Call once per meaningful action."""
    today = date.today().isoformat()
    if user.last_active_date == today:
        _log_activity(session, user, today)
        return
    if user.last_active_date:
        last = date.fromisoformat(user.last_active_date)
        gap = (date.today() - last).days
        user.streak_days = user.streak_days + 1 if gap == 1 else 1
    else:
        user.streak_days = 1
    user.last_active_date = today
    _log_activity(session, user, today)
    if user.streak_days >= 7:
        _award_badge(session, user, "streak_7")
    if user.streak_days >= 30:
        _award_badge(session, user, "streak_30")


def _log_activity(session: Session, user: User, today: str) -> None:
    from sqlmodel import Session as _S  # noqa

    row = session.exec(
        select(DailyActivity).where(DailyActivity.user_id == user.id, DailyActivity.date == today)
    ).first()
    if not row:
        session.add(DailyActivity(user_id=user.id, date=today, minutes=0))


def log_study_time(session: Session, user: User, minutes: int) -> None:
    today = date.today().isoformat()
    row = session.exec(
        select(DailyActivity).where(DailyActivity.user_id == user.id, DailyActivity.date == today)
    ).first()
    if row:
        row.minutes += minutes
    else:
        session.add(DailyActivity(user_id=user.id, date=today, minutes=max(0, minutes)))


def _award_badge(session: Session, user: User, code: str) -> None:
    exists = session.exec(
        select(UserBadge).where(UserBadge.user_id == user.id, UserBadge.badge_code == code)
    ).first()
    if not exists:
        session.add(UserBadge(user_id=user.id, badge_code=code))
        session.add(Notification(user_id=user.id, type="badge", payload=f'{{"badge": "{code}"}}'))


def on_lesson_complete(session: Session, user: User) -> None:
    award_xp(session, user, "lesson_complete")
    touch_streak(session, user)
    _award_badge(session, user, "first_lesson")


def on_quiz(session: Session, user: User, score_pct: float) -> None:
    award_xp(session, user, "quiz_attempt")
    touch_streak(session, user)
    _award_badge(session, user, "first_quiz")
    if score_pct >= 100.0:
        award_xp(session, user, "quiz_perfect")
        _award_badge(session, user, "perfect_score")


def on_practice(session: Session, user: User) -> None:
    award_xp(session, user, "practice_answer")
    touch_streak(session, user)
    # practice_master check via PracticeAttempt aggregate (COUNT, not full load)
    from sqlmodel import func
    from .models import PracticeAttempt
    n = session.exec(
        select(func.count()).select_from(PracticeAttempt).where(PracticeAttempt.user_id == user.id)
    ).one()
    if n >= 100:
        _award_badge(session, user, "practice_master")


def on_course_complete(session: Session, user: User) -> None:
    award_xp(session, user, "course_complete")
    _award_badge(session, user, "course_complete")
