"""SQLAlchemy ORM models (SQLite locally, PostgreSQL in the cloud)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SCHEMA_VERSION = 1


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SchemaInfo(Base):
    __tablename__ = "schema_info"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer)


class Learner(Base):
    """Anonymous learner. `code` is a random identifier, not an account or credential."""
    __tablename__ = "learners"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DiagnosisSession(Base):
    __tablename__ = "diagnosis_sessions"
    __table_args__ = (UniqueConstraint("learner_id", "request_hash", name="uq_session_request"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(80))
    topic: Mapped[str] = mapped_column(String(80))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32))
    concept_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    misconception_category: Mapped[str | None] = mapped_column(String(48), nullable=True)
    misconception_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    result: Mapped[dict] = mapped_column(JSON)   # full DiagnosisResult (analysis, evidence, lesson, ...)
    provider: Mapped[str] = mapped_column(String(32), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    mission_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    questions: Mapped[list["PracticeQuestion"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class PracticeQuestion(Base):
    __tablename__ = "practice_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("diagnosis_sessions.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(12))            # practice | transfer
    question: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str] = mapped_column(String(80))  # verified by sympy
    hints: Mapped[list] = mapped_column(JSON, default=list)
    hints_revealed: Mapped[int] = mapped_column(Integer, default=0)
    difficulty: Mapped[str] = mapped_column(String(10))
    concept_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session: Mapped[DiagnosisSession] = relationship(back_populates="questions")
    attempt: Mapped["PracticeAttempt | None"] = relationship(back_populates="question", uselist=False,
                                                              cascade="all, delete-orphan")


class PracticeAttempt(Base):
    __tablename__ = "practice_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("practice_questions.id"), unique=True)  # one scored attempt
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    answer: Mapped[str] = mapped_column(Text)
    correct: Mapped[bool] = mapped_column(Boolean)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    feedback: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    question: Mapped[PracticeQuestion] = relationship(back_populates="attempt")


class ConceptMastery(Base):
    __tablename__ = "concept_mastery"
    __table_args__ = (UniqueConstraint("learner_id", "concept_id", name="uq_learner_concept"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    concept_id: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    weighted_credit: Mapped[float] = mapped_column(Float, default=0.0)
    weighted_total: Mapped[float] = mapped_column(Float, default=0.0)
    mastery: Mapped[float] = mapped_column(Float, default=0.5)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MasteryHistory(Base):
    __tablename__ = "mastery_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    concept_id: Mapped[str] = mapped_column(String(64))
    mastery: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16))
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Activity(Base):
    __tablename__ = "activity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    detail: Mapped[str] = mapped_column(String(300))
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
