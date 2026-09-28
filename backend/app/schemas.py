from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str


class UserRead(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: str
    lang_pref: str

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    role: str = "student"  # students self-register; teachers flagged for admin review
    lang_pref: str = "hi"


class LessonCreate(BaseModel):
    """Everything a teacher supplies to author a lesson.

    The earlier shape (slug/subject/level) described columns the Lesson model
    never had; a lesson now hangs off a chapter like everywhere else in the app.
    """
    chapter_id: int
    type: str = "text"  # text | video | audio | mixed
    title_en: str = Field(min_length=1, max_length=200)
    title_hi: str = Field(min_length=1, max_length=200)
    title_mr: str = Field(min_length=1, max_length=200)
    body_en: str = Field(default="", max_length=20000)
    body_hi: str = Field(default="", max_length=20000)
    body_mr: str = Field(default="", max_length=20000)
    duration_min: int = Field(default=10, ge=1, le=240)
    video_url: Optional[str] = None
    video_url_low: Optional[str] = None
    audio_url: Optional[str] = None
    published: bool = True


class LessonRead(LessonCreate):
    id: int
    order: int

    class Config:
        from_attributes = True


class QuestionIn(BaseModel):
    """Authoring shape for a lesson question; the router validates `correct`
    against `type` and the option lists before anything reaches the database."""
    type: str = "mcq"  # mcq | truefalse | multi | fill
    prompt_en: str = Field(min_length=1, max_length=1000)
    prompt_hi: str = Field(min_length=1, max_length=1000)
    prompt_mr: str = Field(min_length=1, max_length=1000)
    options_en: list[str] = Field(default_factory=list, max_length=6)
    options_hi: list[str] = Field(default_factory=list, max_length=6)
    options_mr: list[str] = Field(default_factory=list, max_length=6)
    correct: str = "0"  # "0" | "[0,2]" (multi) | answer text (fill)
    explanation_en: str = ""
    explanation_hi: str = ""
    explanation_mr: str = ""
    difficulty: str = "easy"  # easy | medium | hard
    topic: str = "general"
    subject_name: str = "general"  # feeds weak-topic stats


class QuestionOut(BaseModel):
    id: int
    type: str
    prompt_en: str
    prompt_hi: str
    prompt_mr: str
    options_en: list[str]
    options_hi: list[str]
    options_mr: list[str]
    difficulty: str
    topic: str
    subject_name: str
    correct: Optional[str] = None  # hidden unless grading
    explanation_en: Optional[str] = None
    explanation_hi: Optional[str] = None
    explanation_mr: Optional[str] = None

    class Config:
        from_attributes = True


class AttemptAnswer(BaseModel):
    question_id: int
    answer: Any = None  # int index | list[int] | free text, judged per question type


class AttemptIn(BaseModel):
    answers: list[AttemptAnswer] = Field(min_length=1)
    minutes: int = Field(default=10, ge=0, le=240)


class AttemptOut(BaseModel):
    score: float  # percentage
    total: int
    correct: int
    per_question: list[dict]


class ProgressOut(BaseModel):
    lesson_id: int
    completed: bool
    score: Optional[float]
    updated_at: datetime

    class Config:
        from_attributes = True


class BatchIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
