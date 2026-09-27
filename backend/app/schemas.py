from datetime import datetime
from typing import Optional

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
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    title_en: str
    title_hi: str
    subject: str = "general"
    level: int = Field(default=1, ge=1, le=5)
    body_en: str = ""
    body_hi: str = ""
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    published: bool = True


class LessonRead(LessonCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionIn(BaseModel):
    prompt_en: str
    prompt_hi: str
    options_en: list[str] = Field(min_length=2, max_length=6)
    options_hi: list[str] = Field(min_length=2, max_length=6)
    correct_index: int = Field(ge=0, le=5)
    explanation_en: str = ""
    explanation_hi: str = ""


class QuestionOut(BaseModel):
    id: int
    prompt_en: str
    prompt_hi: str
    options_en: str
    options_hi: str
    correct_index: int | None = None  # hidden unless grading
    explanation_en: str | None = None
    explanation_hi: str | None = None

    class Config:
        from_attributes = True


class AttemptIn(BaseModel):
    lesson_id: int
    answers: list[int]  # parallel to question order


class AttemptOut(BaseModel):
    score: float
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
