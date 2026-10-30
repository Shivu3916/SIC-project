"""
SQLAlchemy database models for the Viva Simulator.
Uses SQLAlchemy 2.x Mapped[] annotations for full Python 3.14 compatibility.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from config import Config


class Base(DeclarativeBase):
    pass


class Project(Base):
    """Uploaded project document(s) with processing status."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    technologies: Mapped[str] = mapped_column(Text, default="[]")
    processing_status: Mapped[str] = mapped_column(String(50), default="pending")
    processing_message: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    faiss_index_path: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    sessions: Mapped[List["VivaSession"]] = relationship(
        "VivaSession", back_populates="project", cascade="all, delete-orphan"
    )

    @property
    def technologies_list(self) -> list[str]:
        try:
            return json.loads(self.technologies)
        except Exception:
            return []

    @technologies_list.setter
    def technologies_list(self, value: list[str]) -> None:
        self.technologies = json.dumps(value)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size_bytes": self.file_size_bytes,
            "technologies": self.technologies_list,
            "processing_status": self.processing_status,
            "processing_message": self.processing_message,
            "chunk_count": self.chunk_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class VivaSession(Base):
    """One examination session for a given project."""

    __tablename__ = "viva_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    total_questions: Mapped[int] = mapped_column(Integer, default=10)
    current_question_index: Mapped[int] = mapped_column(Integer, default=0)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    voice_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    topics_covered: Mapped[str] = mapped_column(Text, default="[]")
    misconceptions: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="sessions")
    questions: Mapped[List["Question"]] = relationship(
        "Question",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Question.question_index",
    )

    @property
    def topics_covered_list(self) -> list[str]:
        try:
            return json.loads(self.topics_covered)
        except Exception:
            return []

    @topics_covered_list.setter
    def topics_covered_list(self, value: list[str]) -> None:
        self.topics_covered = json.dumps(value)

    @property
    def misconceptions_list(self) -> list[dict]:
        try:
            return json.loads(self.misconceptions)
        except Exception:
            return []

    @misconceptions_list.setter
    def misconceptions_list(self, value: list[dict]) -> None:
        self.misconceptions = json.dumps(value)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "difficulty": self.difficulty,
            "total_questions": self.total_questions,
            "current_question_index": self.current_question_index,
            "overall_score": round(self.overall_score, 2),
            "status": self.status,
            "voice_mode": self.voice_mode,
            "topics_covered": self.topics_covered_list,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Question(Base):
    """Individual question within a session."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("viva_sessions.id"), nullable=False)
    question_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(255), default="")
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    expected_concepts: Mapped[str] = mapped_column(Text, default="[]")
    evidence_chunks: Mapped[str] = mapped_column(Text, default="[]")
    student_answer: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    correctness: Mapped[str] = mapped_column(String(50), default="")
    feedback_json: Mapped[str] = mapped_column(Text, default="{}")
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    session: Mapped["VivaSession"] = relationship("VivaSession", back_populates="questions")

    @property
    def feedback(self) -> dict:
        try:
            return json.loads(self.feedback_json)
        except Exception:
            return {}

    @feedback.setter
    def feedback(self, value: dict) -> None:
        self.feedback_json = json.dumps(value)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "question_index": self.question_index,
            "question_text": self.question_text,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "student_answer": self.student_answer,
            "score": self.score,
            "correctness": self.correctness,
            "feedback": self.feedback,
            "answered_at": self.answered_at.isoformat() if self.answered_at else None,
        }


# ─── Engine & Session factory ───────────────────────────────────────────────

engine = create_engine(
    Config.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency-injection style DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
