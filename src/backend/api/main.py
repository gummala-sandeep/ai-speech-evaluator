"""
api.py — FastAPI Coordination Layer for SkillEcho v2.0
Multi-role platform: Auth, Student evaluations, Admin management,
and the existing AI inference pipeline (Whisper + Sentence-Transformers).
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from src.backend.services.audio import calculate_filler_stats, extract_signal_features
from src.backend.db.models import (
    AudioFeature,
    AudioFile,
    EvaluationResult,
    FillerWordStats,
    ReferenceConcept,
    SemanticSimilarity,
    SessionLocal,
    Transcript,
    User,
    get_db,
    init_db,
    _hash_password,
)
from src.backend.services.scoring import evaluate_understanding
from src.backend.services.nlp import (
    compute_semantic_similarity,
    compute_cross_encoder_similarity,
    verify_topic_guardrail,
)
from src.backend.services.speech import transcribe_audio

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "student"


class LoginRequest(BaseModel):
    email: str
    password: str


class ConceptCreateRequest(BaseModel):
    concept_title: str
    concept_text: str


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SkillEcho — Voice-Based Concept Understanding Analyser",
    description="Multi-role platform: Auth + AI voice evaluation + Admin management.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

UPLOAD_DIR: str = os.path.join(os.getcwd(), "data", "uploaded_audio")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_or_create_default_user(db) -> User:
    user: User | None = db.query(User).filter(User.email == "system@skillecho.local").first()
    if user is None:
        user = User(
            name="System User",
            email="system@skillecho.local",
            role="student",
            password_hash=_hash_password("system-no-login"),
            created_at=datetime.utcnow(),
        )
        db.add(user)
        db.flush()
        logger.info("Created default system user id=%d", user.user_id)
    return user


def _mark_audio_failed(audio_id: int, reason: str) -> None:
    try:
        with get_db() as db:
            record: AudioFile | None = db.query(AudioFile).filter(AudioFile.audio_id == audio_id).first()
            if record is not None:
                record.status = "failed"
                db.commit()
    except Exception as exc:
        logger.error("Could not mark audio_id=%d as failed: %s", audio_id, exc)


# ===========================================================================
# UTILITY
# ===========================================================================

@app.get("/health", tags=["Utility"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "SkillEcho API", "version": "2.0.0"}


# ===========================================================================
# AUTH ENDPOINTS
# ===========================================================================

@app.post("/auth/register", tags=["Auth"])
def register(req: RegisterRequest) -> JSONResponse:
    """Register a new student or admin account."""
    if req.role not in ("student", "admin"):
        raise HTTPException(status_code=400, detail="role must be 'student' or 'admin'")
    if not req.name.strip() or not req.email.strip():
        raise HTTPException(status_code=400, detail="name and email are required")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    email_clean = req.email.lower().strip()
    created_id: int
    created_name: str
    created_role: str

    with get_db() as db:
        if db.query(User).filter(User.email == email_clean).first():
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        user = User(
            name=req.name.strip(),
            email=email_clean,
            role=req.role,
            password_hash=_hash_password(req.password),
            created_at=datetime.utcnow(),
        )
        db.add(user)
        db.flush()
        created_id = int(user.user_id)
        created_name = str(user.name)
        created_role = str(user.role)
        db.commit()

    logger.info("Registered user id=%d role=%s", created_id, created_role)
    return JSONResponse(status_code=201, content={"user_id": created_id, "name": created_name, "role": created_role})


@app.post("/auth/login", tags=["Auth"])
def login(req: LoginRequest) -> JSONResponse:
    """Validate credentials and return user profile."""
    email_clean = req.email.lower().strip()
    stored_hash = ""
    user_id = 0
    name = ""
    role = ""

    with get_db() as db:
        user: User | None = db.query(User).filter(User.email == email_clean).first()
        if user is not None:
            stored_hash = str(user.password_hash) if user.password_hash else ""
            user_id = int(user.user_id)
            name = str(user.name)
            role = str(user.role)

    if not user_id or stored_hash != _hash_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    logger.info("Login: user_id=%d role=%s", user_id, role)
    return JSONResponse(content={"user_id": user_id, "name": name, "role": role})


# ===========================================================================
# CONCEPTS ENDPOINT
# ===========================================================================

@app.get("/concepts", tags=["Concepts"])
def list_concepts() -> JSONResponse:
    with get_db() as db:
        concepts: list[ReferenceConcept] = db.query(ReferenceConcept).all()
        payload = [
            {
                "ref_concept_id": int(c.ref_concept_id),
                "concept_title": str(c.concept_title),
                "concept_text": str(c.concept_text),
                "reference_pdf_path": str(c.reference_pdf_path) if c.reference_pdf_path else None
            }
            for c in concepts
        ]
    return JSONResponse(content={"concepts": payload})


@app.get("/concepts/{concept_id}/pdf", tags=["Concepts"])
def get_concept_pdf(concept_id: int):
    """Retrieve the reference PDF for a specific concept."""
    with get_db() as db:
        concept: ReferenceConcept | None = (
            db.query(ReferenceConcept)
            .filter(ReferenceConcept.ref_concept_id == concept_id)
            .first()
        )
        if concept is None or not concept.reference_pdf_path:
            raise HTTPException(status_code=404, detail="PDF not found for this concept")
        
        if not os.path.exists(concept.reference_pdf_path):
            raise HTTPException(status_code=404, detail="PDF file does not exist on the server")
            
        return FileResponse(
            concept.reference_pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(concept.reference_pdf_path)
        )


# ===========================================================================
# STUDENT HISTORY ENDPOINT
# ===========================================================================

@app.get("/users/{user_id}/history", tags=["Users"])
def get_user_history(user_id: int) -> JSONResponse:
    """Return rich evaluation history for a user — includes transcript & signal metrics."""
    with get_db() as db:
        rows = (
            db.query(
                EvaluationResult,
                ReferenceConcept.concept_title,
                Transcript.transcript_text,
                AudioFeature.rms_energy,
                AudioFeature.pause_ratio,
                FillerWordStats.filler_ratio,
                SemanticSimilarity.similarity_score,
                SemanticSimilarity.cross_encoder_score,
                SemanticSimilarity.topic_match,
            )
            .join(AudioFile, EvaluationResult.audio_id == AudioFile.audio_id)
            .join(ReferenceConcept, EvaluationResult.ref_concept_id == ReferenceConcept.ref_concept_id)
            .outerjoin(Transcript, Transcript.audio_id == AudioFile.audio_id)
            .outerjoin(AudioFeature, AudioFeature.audio_id == AudioFile.audio_id)
            .outerjoin(FillerWordStats, FillerWordStats.transcript_id == Transcript.transcript_id)
            .outerjoin(SemanticSimilarity, SemanticSimilarity.transcript_id == Transcript.transcript_id)
            .filter(AudioFile.user_id == user_id)
            .order_by(EvaluationResult.created_at.desc())
            .all()
        )
        payload = [
            {
                "result_id": int(row.EvaluationResult.result_id),
                "concept_title": str(row.concept_title),
                "overall_score": float(row.EvaluationResult.overall_score),
                "understanding_level": str(row.EvaluationResult.understanding_level),
                "created_at": row.EvaluationResult.created_at.strftime("%Y-%m-%d %H:%M"),
                "transcript_text": str(row.transcript_text or ""),
                "rms_energy": float(row.rms_energy or 0.0),
                "pause_ratio": float(row.pause_ratio or 0.0),
                "filler_ratio": float(row.filler_ratio or 0.0),
                "similarity_score": float(row.similarity_score) if row.similarity_score is not None else 0.0,
                "cross_encoder_score": float(row.cross_encoder_score) if row.cross_encoder_score is not None else 0.0,
                "topic_match": bool(row.topic_match) if row.topic_match is not None else True,
            }
            for row in rows
        ]
    return JSONResponse(content={"history": payload})


# ===========================================================================
# ADMIN ENDPOINTS
# ===========================================================================

@app.post("/admin/concepts", tags=["Admin"])
async def add_concept(
    concept_title: str = Form(...),
    concept_text: str = Form(...),
    reference_pdf: UploadFile | None = File(None)
) -> JSONResponse:
    """Add a new reference concept to the library with optional reference PDF."""
    if not concept_title.strip() or not concept_text.strip():
        raise HTTPException(status_code=400, detail="concept_title and concept_text cannot be empty")

    reference_pdf_path = None
    if reference_pdf and reference_pdf.filename:
        # Secure filename by using uuid prefix
        safe_pdf_name = f"{uuid.uuid4().hex}_{reference_pdf.filename}"
        pdf_dest_path = os.path.join(os.getcwd(), "data", "reference_materials", safe_pdf_name)
        pdf_bytes = await reference_pdf.read()
        with open(pdf_dest_path, "wb") as fh:
            fh.write(pdf_bytes)
        reference_pdf_path = pdf_dest_path

    with get_db() as db:
        concept = ReferenceConcept(
            concept_title=concept_title.strip(),
            concept_text=concept_text.strip(),
            reference_pdf_path=reference_pdf_path,
            created_at=datetime.utcnow(),
        )
        db.add(concept)
        db.flush()
        new_id = int(concept.ref_concept_id)
        new_title = str(concept.concept_title)
        new_pdf_path = concept.reference_pdf_path
        db.commit()

    logger.info("Admin added concept id=%d title=%r pdf=%s", new_id, new_title, new_pdf_path)
    return JSONResponse(status_code=201, content={"ref_concept_id": new_id, "concept_title": new_title, "reference_pdf_path": new_pdf_path})


@app.put("/admin/concepts/{concept_id}", tags=["Admin"])
async def update_concept(
    concept_id: int,
    concept_title: str = Form(...),
    concept_text: str = Form(...),
    reference_pdf: UploadFile | None = File(None),
    clear_pdf: bool = Form(False)
) -> JSONResponse:
    """Update an existing concept and its reference PDF."""
    if not concept_title.strip() or not concept_text.strip():
        raise HTTPException(status_code=400, detail="concept_title and concept_text cannot be empty")
        
    with get_db() as db:
        concept = db.query(ReferenceConcept).filter(ReferenceConcept.ref_concept_id == concept_id).first()
        if not concept:
            raise HTTPException(status_code=404, detail="Concept not found")
            
        concept.concept_title = concept_title.strip()
        concept.concept_text = concept_text.strip()
        
        # Handle clear PDF
        if clear_pdf:
            if concept.reference_pdf_path and os.path.exists(concept.reference_pdf_path):
                try:
                    os.remove(concept.reference_pdf_path)
                except Exception as e:
                    logger.warning("Failed to delete old PDF file %s: %s", concept.reference_pdf_path, e)
            concept.reference_pdf_path = None
            
        # Handle new PDF upload
        if reference_pdf and reference_pdf.filename:
            # Delete old PDF first if it exists
            if concept.reference_pdf_path and os.path.exists(concept.reference_pdf_path):
                try:
                    os.remove(concept.reference_pdf_path)
                except Exception as e:
                    logger.warning("Failed to delete old PDF file %s: %s", concept.reference_pdf_path, e)
            
            safe_pdf_name = f"{uuid.uuid4().hex}_{reference_pdf.filename}"
            pdf_dest_path = os.path.join(os.getcwd(), "data", "reference_materials", safe_pdf_name)
            pdf_bytes = await reference_pdf.read()
            with open(pdf_dest_path, "wb") as fh:
                fh.write(pdf_bytes)
            concept.reference_pdf_path = pdf_dest_path
            
        db.commit()
        updated_id = int(concept.ref_concept_id)
        updated_title = str(concept.concept_title)
        updated_pdf_path = concept.reference_pdf_path
        
    logger.info("Admin updated concept id=%d title=%r pdf=%s", updated_id, updated_title, updated_pdf_path)
    return JSONResponse(content={"ref_concept_id": updated_id, "concept_title": updated_title, "reference_pdf_path": updated_pdf_path})


@app.delete("/admin/concepts/{concept_id}", tags=["Admin"])
def delete_concept(concept_id: int) -> JSONResponse:
    """Delete a reference concept and its associated files and database records."""
    with get_db() as db:
        concept = db.query(ReferenceConcept).filter(ReferenceConcept.ref_concept_id == concept_id).first()
        if not concept:
            raise HTTPException(status_code=404, detail="Concept not found")
        
        # If there's an attached PDF, try to delete it
        if concept.reference_pdf_path and os.path.exists(concept.reference_pdf_path):
            try:
                os.remove(concept.reference_pdf_path)
            except Exception as e:
                logger.warning("Failed to delete PDF file %s: %s", concept.reference_pdf_path, e)
                
        db.delete(concept)
        db.commit()
    logger.info("Admin deleted concept id=%d", concept_id)
    return JSONResponse(content={"message": "Concept deleted successfully", "ref_concept_id": concept_id})



@app.get("/admin/results", tags=["Admin"])
def get_all_results() -> JSONResponse:
    """Return rich evaluation results across all users — includes transcript & signal metrics."""
    with get_db() as db:
        rows = (
            db.query(
                EvaluationResult,
                User.name,
                User.email,
                ReferenceConcept.concept_title,
                Transcript.transcript_text,
                AudioFeature.rms_energy,
                AudioFeature.pause_ratio,
                FillerWordStats.filler_ratio,
                SemanticSimilarity.similarity_score,
                SemanticSimilarity.cross_encoder_score,
                SemanticSimilarity.topic_match,
            )
            .join(AudioFile, EvaluationResult.audio_id == AudioFile.audio_id)
            .join(User, AudioFile.user_id == User.user_id)
            .join(ReferenceConcept, EvaluationResult.ref_concept_id == ReferenceConcept.ref_concept_id)
            .outerjoin(Transcript, Transcript.audio_id == AudioFile.audio_id)
            .outerjoin(AudioFeature, AudioFeature.audio_id == AudioFile.audio_id)
            .outerjoin(FillerWordStats, FillerWordStats.transcript_id == Transcript.transcript_id)
            .outerjoin(SemanticSimilarity, SemanticSimilarity.transcript_id == Transcript.transcript_id)
            .order_by(EvaluationResult.created_at.desc())
            .all()
        )
        payload = [
            {
                "result_id": int(row.EvaluationResult.result_id),
                "student_name": str(row.name),
                "student_email": str(row.email),
                "concept_title": str(row.concept_title),
                "overall_score": float(row.EvaluationResult.overall_score),
                "understanding_level": str(row.EvaluationResult.understanding_level),
                "created_at": row.EvaluationResult.created_at.strftime("%Y-%m-%d %H:%M"),
                "transcript_text": str(row.transcript_text or ""),
                "rms_energy": float(row.rms_energy or 0.0),
                "pause_ratio": float(row.pause_ratio or 0.0),
                "filler_ratio": float(row.filler_ratio or 0.0),
                "similarity_score": float(row.similarity_score) if row.similarity_score is not None else 0.0,
                "cross_encoder_score": float(row.cross_encoder_score) if row.cross_encoder_score is not None else 0.0,
                "topic_match": bool(row.topic_match) if row.topic_match is not None else True,
            }
            for row in rows
        ]
    return JSONResponse(content={"results": payload})


@app.get("/admin/users", tags=["Admin"])
def get_all_users() -> JSONResponse:
    """Return all registered users in the system."""
    with get_db() as db:
        users = db.query(User).order_by(User.created_at.desc()).all()
        payload = [
            {
                "user_id": int(u.user_id),
                "name": str(u.name),
                "email": str(u.email),
                "role": str(u.role),
                "created_at": u.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for u in users
        ]
    return JSONResponse(content={"users": payload})



# ===========================================================================
# EVALUATE ENDPOINT  (AI inference pipeline — unchanged logic, user_id added)
# ===========================================================================

@app.post("/evaluate", tags=["Evaluation"])
async def evaluate(
    audio_file: UploadFile = File(..., description="WAV audio of the student's explanation"),
    ref_concept_id: int = Form(..., description="Primary key of the ReferenceConcept"),
    user_id: int = Form(0, description="Logged-in user_id (0 = system default user)"),
) -> JSONResponse:
    """
    Full 10-step AI pipeline:
    transcription → signal analysis → filler stats → semantic similarity
    → scoring → DB persistence → JSON response.
    """
    # ── Step 1: Validate concept ─────────────────────────────────────────
    reference_text: str = ""
    concept_title: str = ""
    reference_pdf_path: str | None = None

    with get_db() as db:
        rc: ReferenceConcept | None = (
            db.query(ReferenceConcept)
            .filter(ReferenceConcept.ref_concept_id == ref_concept_id)
            .first()
        )
        if rc is None:
            raise HTTPException(status_code=404, detail=f"ReferenceConcept id={ref_concept_id} not found")
        reference_text = str(rc.concept_text)
        concept_title = str(rc.concept_title)
        reference_pdf_path = str(rc.reference_pdf_path) if rc.reference_pdf_path else None

    # ── Step 2: Save audio ───────────────────────────────────────────────
    safe_name = f"{uuid.uuid4().hex}_{audio_file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    raw_bytes: bytes = await audio_file.read()
    with open(file_path, "wb") as fh:
        fh.write(raw_bytes)
    logger.info("Audio saved: %s (%d bytes)", file_path, len(raw_bytes))

    # ── Step 3: Resolve user & create AudioFile record ──────────────────
    with get_db() as db:
        if user_id > 0:
            resolved_user: User | None = db.query(User).filter(User.user_id == user_id).first()
            if resolved_user is None:
                resolved_user = _get_or_create_default_user(db)
            resolved_uid = int(resolved_user.user_id)
        else:
            resolved_user = _get_or_create_default_user(db)
            resolved_uid = int(resolved_user.user_id)

        db_audio = AudioFile(
            user_id=resolved_uid,
            file_name=audio_file.filename or safe_name,
            file_path=file_path,
            status="processing",
            uploaded_at=datetime.utcnow(),
        )
        db.add(db_audio)
        db.flush()
        audio_id: int = int(db_audio.audio_id)
        db.commit()

    # ── Step 4: Transcription ────────────────────────────────────────────
    try:
        transcript_text: str = transcribe_audio(file_path)
    except Exception as exc:
        _mark_audio_failed(audio_id, str(exc))
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")

    import gc
    gc.collect()

    logger.info("Transcript word count: %d", len(transcript_text.split()))

    # ── Topic Guardrail Check ──────────────────────────────────────────
    topic_match, overlap_count, topic_threshold = verify_topic_guardrail(transcript_text, reference_text)

    # ── Step 5: Signal features ──────────────────────────────────────────
    try:
        signal_features: dict[str, float] = extract_signal_features(file_path)
    except Exception as exc:
        _mark_audio_failed(audio_id, str(exc))
        raise HTTPException(status_code=500, detail=f"Signal feature extraction failed: {exc}")

    import gc
    gc.collect()

    duration_sec = signal_features["duration_sec"]
    rms_energy = signal_features["rms_energy"]
    zero_crossing_rate = signal_features["zero_crossing_rate"]
    pause_ratio = signal_features["pause_ratio"]

    # ── Step 6: Filler words ─────────────────────────────────────────────
    filler_stats: dict = calculate_filler_stats(transcript_text)
    filler_word_count = filler_stats["filler_word_count"]
    total_words = filler_stats["total_words"]
    filler_ratio = filler_stats["filler_ratio"]

    if not topic_match:
        # Topic Guardrail Mismatch - skip heavy semantic models
        similarity_score = 0.0
        cross_encoder_score = 0.0
        overall_score, understanding_level, colour_hex = evaluate_understanding(
            similarity=0.0,
            cross_similarity=0.0,
            filler_ratio=filler_ratio,
            pause_ratio=pause_ratio,
            rms_energy=rms_energy,
            topic_match=False
        )

        with get_db() as db:
            af_record: AudioFile | None = db.query(AudioFile).filter(AudioFile.audio_id == audio_id).first()
            if af_record is not None:
                af_record.duration_sec = duration_sec
                af_record.status = "completed"

            db_transcript = Transcript(
                audio_id=audio_id,
                transcript_text=transcript_text,
                created_at=datetime.utcnow(),
            )
            db.add(db_transcript)
            db.flush()
            transcript_id: int = int(db_transcript.transcript_id)

            db.add(FillerWordStats(
                transcript_id=transcript_id,
                filler_word_count=filler_word_count,
                total_words=total_words,
                filler_ratio=filler_ratio,
                created_at=datetime.utcnow(),
            ))
            db.add(AudioFeature(
                audio_id=audio_id,
                pause_ratio=pause_ratio,
                rms_energy=rms_energy,
                zero_crossing_rate=zero_crossing_rate,
                duration_sec=duration_sec,
                created_at=datetime.utcnow(),
            ))
            db.add(SemanticSimilarity(
                transcript_id=transcript_id,
                ref_concept_id=ref_concept_id,
                similarity_score=similarity_score,
                cross_encoder_score=cross_encoder_score,
                topic_match=False,
                created_at=datetime.utcnow(),
            ))
            notes = f"Topic Guardrail Mismatched: Core vocabulary overlap count {overlap_count} < {topic_threshold}"
            db.add(EvaluationResult(
                audio_id=audio_id,
                ref_concept_id=ref_concept_id,
                overall_score=float(overall_score),
                understanding_level=understanding_level,
                created_at=datetime.utcnow(),
                notes=notes,
            ))
            db.commit()

        logger.info("Evaluation done (Topic Mismatch) — audio_id=%d score=%d level=%r", audio_id, overall_score, understanding_level)

        return JSONResponse(content={
            "status": "Topic Mismatch",
            "audio_id": audio_id,
            "transcript_id": transcript_id,
            "concept": {"ref_concept_id": ref_concept_id, "concept_title": concept_title, "concept_text": reference_text, "reference_pdf_path": reference_pdf_path},
            "transcript": transcript_text,
            "signal_features": {
                "duration_sec": round(duration_sec, 4),
                "rms_energy": round(rms_energy, 8),
                "zero_crossing_rate": round(zero_crossing_rate, 8),
                "pause_ratio": round(pause_ratio, 6),
            },
            "filler_stats": {
                "filler_word_count": filler_word_count,
                "total_words": total_words,
                "filler_ratio": round(filler_ratio, 6),
                "filler_breakdown": filler_stats.get("filler_breakdown", {}),
            },
            "semantic_similarity": round(similarity_score, 6),
            "cross_encoder_score": round(cross_encoder_score, 6),
            "topic_match": False,
            "evaluation": {
                "overall_score": overall_score,
                "understanding_level": understanding_level,
                "colour_hex": colour_hex,
            },
        })

    # ── Step 7: Semantic similarity (Bi-Encoder) ─────────────────────────
    try:
        similarity_score: float = compute_semantic_similarity(transcript_text, reference_text)
    except Exception as exc:
        _mark_audio_failed(audio_id, str(exc))
        raise HTTPException(status_code=500, detail=f"Semantic evaluation failed: {exc}")

    # ── Step 7b: Cross-Encoder similarity ─────────────────────────────────
    try:
        cross_encoder_score: float = compute_cross_encoder_similarity(transcript_text, reference_text)
    except Exception as exc:
        _mark_audio_failed(audio_id, str(exc))
        raise HTTPException(status_code=500, detail=f"Cross-Encoder similarity evaluation failed: {exc}")

    # ── Step 8: Scoring ──────────────────────────────────────────────────
    overall_score, understanding_level, colour_hex = evaluate_understanding(
        similarity=similarity_score,
        cross_similarity=cross_encoder_score,
        filler_ratio=filler_ratio,
        pause_ratio=pause_ratio,
        rms_energy=rms_energy,
        topic_match=True,
    )

    # ── Step 9: Persist all artefacts ────────────────────────────────────
    with get_db() as db:
        af_record: AudioFile | None = db.query(AudioFile).filter(AudioFile.audio_id == audio_id).first()
        if af_record is not None:
            af_record.duration_sec = duration_sec
            af_record.status = "completed"

        db_transcript = Transcript(
            audio_id=audio_id,
            transcript_text=transcript_text,
            created_at=datetime.utcnow(),
        )
        db.add(db_transcript)
        db.flush()
        transcript_id: int = int(db_transcript.transcript_id)

        db.add(FillerWordStats(
            transcript_id=transcript_id,
            filler_word_count=filler_word_count,
            total_words=total_words,
            filler_ratio=filler_ratio,
            created_at=datetime.utcnow(),
        ))
        db.add(AudioFeature(
            audio_id=audio_id,
            pause_ratio=pause_ratio,
            rms_energy=rms_energy,
            zero_crossing_rate=zero_crossing_rate,
            duration_sec=duration_sec,
            created_at=datetime.utcnow(),
        ))
        db.add(SemanticSimilarity(
            transcript_id=transcript_id,
            ref_concept_id=ref_concept_id,
            similarity_score=similarity_score,
            cross_encoder_score=cross_encoder_score,
            topic_match=True,
            created_at=datetime.utcnow(),
        ))
        notes = (
            f"Concept: '{concept_title}' | "
            f"Evaluated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC | "
            f"Fillers: {filler_stats.get('filler_breakdown', {})}"
        )
        db.add(EvaluationResult(
            audio_id=audio_id,
            ref_concept_id=ref_concept_id,
            overall_score=float(overall_score),
            understanding_level=understanding_level,
            created_at=datetime.utcnow(),
            notes=notes,
        ))
        db.commit()

    logger.info("Evaluation done — audio_id=%d score=%d level=%r", audio_id, overall_score, understanding_level)

    # ── Step 10: Response ────────────────────────────────────────────────
    return JSONResponse(content={
        "status": "success",
        "audio_id": audio_id,
        "transcript_id": transcript_id,
        "concept": {"ref_concept_id": ref_concept_id, "concept_title": concept_title, "concept_text": reference_text, "reference_pdf_path": reference_pdf_path},
        "transcript": transcript_text,
        "signal_features": {
            "duration_sec": round(duration_sec, 4),
            "rms_energy": round(rms_energy, 8),
            "zero_crossing_rate": round(zero_crossing_rate, 8),
            "pause_ratio": round(pause_ratio, 6),
        },
        "filler_stats": {
            "filler_word_count": filler_word_count,
            "total_words": total_words,
            "filler_ratio": round(filler_ratio, 6),
            "filler_breakdown": filler_stats.get("filler_breakdown", {}),
        },
        "semantic_similarity": round(similarity_score, 6),
        "cross_encoder_score": round(cross_encoder_score, 6),
        "topic_match": True,
        "evaluation": {
            "overall_score": overall_score,
            "understanding_level": understanding_level,
            "colour_hex": colour_hex,
        },
    })


# ---------------------------------------------------------------------------
# Dev entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
