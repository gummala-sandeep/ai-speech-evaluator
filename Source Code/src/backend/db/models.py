"""
models.py — SQLAlchemy Database Architecture for SkillEcho
Defines all ORM models (User, AudioFile, Transcript, FillerWordStats, SemanticSimilarity,
AudioFeature, EvaluationResult, ReferenceConcept, Session, Report),
the database engine, session factory, dependency-injection helper, and initial seed data.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
from datetime import datetime
from typing import Generator

# Load environment variables from .env if present
if os.path.exists(".env"):
    with open(".env", "r") as _env_file:
        for _line in _env_file:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    text,
    Boolean,
)
from sqlalchemy.orm import DeclarativeBase, Session as DBSession, relationship, sessionmaker

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///database.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

# Enable WAL mode for better concurrent read performance on SQLite and enforce FK constraints
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    if engine.dialect.name == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


SessionLocal: sessionmaker[DBSession] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    __allow_unmapped__ = True


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    user_id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name: str = Column(String(255), nullable=False)
    email: str = Column(String(255), nullable=False, unique=True)
    role: str = Column(String(100), nullable=False, default="student")
    password_hash: str = Column(String(255), nullable=True)  # SHA-256 hex digest
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    audio_files: list[AudioFile] = relationship(
        "AudioFile", back_populates="user", cascade="all, delete-orphan"
    )
    sessions: list[Session] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.user_id} email={self.email!r}>"


class AudioFile(Base):
    __tablename__ = "audio_files"

    audio_id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: int = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    file_name: str = Column(String(512), nullable=False)
    file_path: str = Column(String(1024), nullable=False)
    duration_sec: float = Column(Float, nullable=True)
    uploaded_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)
    status: str = Column(String(50), nullable=False, default="pending")

    # Relationships
    user: User = relationship("User", back_populates="audio_files")
    
    # 1:1 Relationships (uselist=False)
    transcript: Transcript = relationship(
        "Transcript", back_populates="audio_file", uselist=False, cascade="all, delete-orphan"
    )
    audio_feature: AudioFeature = relationship(
        "AudioFeature", back_populates="audio_file", uselist=False, cascade="all, delete-orphan"
    )
    
    # 1:N Relationship
    evaluation_results: list[EvaluationResult] = relationship(
        "EvaluationResult", back_populates="audio_file", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AudioFile id={self.audio_id} name={self.file_name!r} status={self.status!r}>"


class Transcript(Base):
    __tablename__ = "transcripts"

    transcript_id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    audio_id: int = Column(
        Integer, ForeignKey("audio_files.audio_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    transcript_text: str = Column(Text, nullable=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    audio_file: AudioFile = relationship("AudioFile", back_populates="transcript")
    
    # 1:1 Relationships (uselist=False)
    filler_word_stats: FillerWordStats = relationship(
        "FillerWordStats", back_populates="transcript", uselist=False, cascade="all, delete-orphan"
    )
    semantic_similarity: SemanticSimilarity = relationship(
        "SemanticSimilarity", back_populates="transcript", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Transcript id={self.transcript_id} audio_id={self.audio_id}>"


class FillerWordStats(Base):
    __tablename__ = "filler_word_stats"

    filler_id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transcript_id: int = Column(
        Integer, ForeignKey("transcripts.transcript_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    filler_word_count: int = Column(Integer, nullable=False, default=0)
    total_words: int = Column(Integer, nullable=False, default=0)
    filler_ratio: float = Column(Float, nullable=False, default=0.0)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    transcript: Transcript = relationship("Transcript", back_populates="filler_word_stats")

    def __repr__(self) -> str:
        return f"<FillerWordStats id={self.filler_id} ratio={self.filler_ratio:.4f}>"


class ReferenceConcept(Base):
    __tablename__ = "reference_concepts"

    ref_concept_id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    concept_title: str = Column(String(512), nullable=False)
    concept_text: str = Column(Text, nullable=False)
    reference_pdf_path: str = Column(String(1024), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    semantic_similarities: list[SemanticSimilarity] = relationship(
        "SemanticSimilarity", back_populates="reference_concept"
    )
    evaluation_results: list[EvaluationResult] = relationship(
        "EvaluationResult", back_populates="reference_concept"
    )

    def __repr__(self) -> str:
        return f"<ReferenceConcept id={self.ref_concept_id} title={self.concept_title!r}>"


class SemanticSimilarity(Base):
    __tablename__ = "semantic_similarities"

    similarity_id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transcript_id: int = Column(
        Integer, ForeignKey("transcripts.transcript_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    ref_concept_id: int = Column(
        Integer, ForeignKey("reference_concepts.ref_concept_id", ondelete="CASCADE"), nullable=False
    )
    similarity_score: float = Column(Float, nullable=False)
    cross_encoder_score: float | None = Column(Float, nullable=True)
    topic_match: bool | None = Column(Boolean, nullable=True, default=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    transcript: Transcript = relationship("Transcript", back_populates="semantic_similarity")
    reference_concept: ReferenceConcept = relationship("ReferenceConcept", back_populates="semantic_similarities")

    def __repr__(self) -> str:
        return f"<SemanticSimilarity id={self.similarity_id} score={self.similarity_score:.4f} cross_score={self.cross_encoder_score} topic_match={self.topic_match}>"


class AudioFeature(Base):
    __tablename__ = "audio_features"

    feature_id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    audio_id: int = Column(
        Integer, ForeignKey("audio_files.audio_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    pause_ratio: float = Column(Float, nullable=False, default=0.0)
    rms_energy: float = Column(Float, nullable=False, default=0.0)
    zero_crossing_rate: float = Column(Float, nullable=False, default=0.0)
    duration_sec: float = Column(Float, nullable=False, default=0.0)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    audio_file: AudioFile = relationship("AudioFile", back_populates="audio_feature")

    def __repr__(self) -> str:
        return f"<AudioFeature id={self.feature_id} audio_id={self.audio_id} rms={self.rms_energy:.6f}>"


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    result_id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    audio_id: int = Column(
        Integer, ForeignKey("audio_files.audio_id", ondelete="CASCADE"), nullable=False
    )
    ref_concept_id: int = Column(
        Integer, ForeignKey("reference_concepts.ref_concept_id", ondelete="CASCADE"), nullable=False
    )
    overall_score: float = Column(Float, nullable=False)
    understanding_level: str = Column(String(50), nullable=False)  # "Strong Understanding" etc
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes: str = Column(Text, nullable=True)

    # Relationships
    audio_file: AudioFile = relationship("AudioFile", back_populates="evaluation_results")
    reference_concept: ReferenceConcept = relationship("ReferenceConcept", back_populates="evaluation_results")
    
    # 1:1 Relationship (uselist=False)
    report: Report = relationship(
        "Report", back_populates="evaluation_result", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EvaluationResult id={self.result_id} score={self.overall_score} level={self.understanding_level!r}>"


class Session(Base):
    __tablename__ = "sessions"

    session_id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: int = Column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    started_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at: datetime = Column(DateTime, nullable=True)
    status: str = Column(String(50), nullable=False, default="active")

    # Relationships
    user: User = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session id={self.session_id} user_id={self.user_id} status={self.status!r}>"


class Report(Base):
    __tablename__ = "reports"

    report_id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    result_id: int = Column(
        Integer, ForeignKey("evaluation_results.result_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    pdf_path: str = Column(String(1024), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    evaluation_result: EvaluationResult = relationship("EvaluationResult", back_populates="report")

    def __repr__(self) -> str:
        return f"<Report id={self.report_id} result_id={self.result_id}>"


# ---------------------------------------------------------------------------
# Database initialisation & seed data
# ---------------------------------------------------------------------------

INITIAL_CONCEPTS: list[dict] = [
    {
        "concept_title": "Machine Learning",
        "concept_text": (
            "Machine Learning is a subset of artificial intelligence that allows systems to learn "
            "patterns from data and improve performance without being explicitly programmed."
        ),
    },
    {
        "concept_title": "Deep Learning",
        "concept_text": (
            "Deep Learning is a branch of machine learning that uses multi-layered neural networks "
            "to model and understand complex patterns in large datasets, enabling tasks such as "
            "image recognition, speech processing, and natural language understanding."
        ),
    },
    {
        "concept_title": "Natural Language Processing",
        "concept_text": (
            "Natural Language Processing (NLP) is a field of artificial intelligence focused on "
            "enabling computers to understand, interpret, and generate human language in a way "
            "that is both meaningful and contextually appropriate."
        ),
    },
    {
        "concept_title": "Reinforcement Learning",
        "concept_text": (
            "Reinforcement Learning is a type of machine learning where an agent learns to make "
            "decisions by interacting with an environment, receiving rewards for correct actions "
            "and penalties for incorrect ones, optimizing a long-term cumulative reward signal."
        ),
    },
    {
        "concept_title": "Neural Networks",
        "concept_text": (
            "Neural Networks are computational models inspired by the human brain, consisting of "
            "interconnected layers of nodes (neurons) that process information using weighted "
            "connections, enabling the system to learn complex, non-linear relationships from data."
        ),
    },
]


def init_db() -> None:
    """Create all tables, run safe migrations, and call seeding."""
    # Ensure reference_materials/ directory exists on the server
    os.makedirs(os.path.join(os.getcwd(), "data", "reference_materials"), exist_ok=True)

    Base.metadata.create_all(bind=engine)

    # Safe migration: add password_hash and reference_pdf_path columns to existing databases
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
            conn.commit()
        except Exception:
            pass  # Column already exists — no action needed
            
        try:
            conn.execute(text("ALTER TABLE reference_concepts ADD COLUMN reference_pdf_path VARCHAR(1024)"))
            conn.commit()
        except Exception:
            pass  # Column already exists — no action needed

        try:
            conn.execute(text("ALTER TABLE semantic_similarities ADD COLUMN cross_encoder_score FLOAT"))
            conn.commit()
        except Exception:
            pass  # Column already exists

        try:
            conn.execute(text("ALTER TABLE semantic_similarities ADD COLUMN topic_match BOOLEAN"))
            conn.commit()
        except Exception:
            pass  # Column already exists

    seed_db()


def _hash_password(raw: str) -> str:
    """Hash raw password using SHA-256 (matches api.py helper)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def seed_db() -> None:
    """Populates the database with initial concepts and default system user if empty."""
    db = SessionLocal()
    try:
        # Check if reference_concepts is empty and seed if necessary
        existing_concepts = db.execute(
            text("SELECT COUNT(*) FROM reference_concepts")
        ).scalar_one()

        if existing_concepts == 0:
            for concept_data in INITIAL_CONCEPTS:
                concept = ReferenceConcept(
                    concept_title=concept_data["concept_title"],
                    concept_text=concept_data["concept_text"],
                    reference_pdf_path=None,
                    created_at=datetime.utcnow(),
                )
                db.add(concept)
        
        # Check if users table is empty and seed default user (cloud-safe SQLAlchemy query)
        existing_users = db.query(User).count()
        if existing_users == 0:
            default_user = User(
                name="System User",
                email="system@skillecho.local",
                role="student",
                password_hash=_hash_password("system-no-login"),
                created_at=datetime.utcnow(),
            )
            db.add(default_user)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Dependency helper
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def get_db() -> Generator[DBSession, None, None]:
    """Yield a transactional database session and guarantee cleanup."""
    db: DBSession = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Bootstrap on import
# ---------------------------------------------------------------------------

init_db()
