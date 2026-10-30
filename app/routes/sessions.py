"""
Viva session routes: create, question flow, answer submission, feedback, report.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from flask import Blueprint, jsonify, request

from app.llm.examiner import evaluate_answer, generate_final_report, generate_question
from app.models.database import Project, Question, SessionLocal, VivaSession
from app.rag.vector_store import ProjectVectorStore
from config import Config

logger = logging.getLogger(__name__)

sessions_bp = Blueprint("sessions", __name__, url_prefix="/api/sessions")


def _get_rubric_weights() -> dict:
    return {
        "technical_correctness": Config.WEIGHT_TECHNICAL_CORRECTNESS,
        "depth_of_reasoning": Config.WEIGHT_DEPTH_OF_REASONING,
        "project_specific": Config.WEIGHT_PROJECT_SPECIFIC,
        "completeness": Config.WEIGHT_COMPLETENESS,
    }


def _retrieve_context(project_id: int, query: str, top_k: int = 5) -> list[dict]:
    store = ProjectVectorStore(project_id)
    return store.retrieve(query, top_k=top_k)


@sessions_bp.route("", methods=["POST"])
def create_session():
    """Start a new viva session for a project."""
    data = request.get_json(force=True, silent=True) or {}
    project_id = data.get("project_id")
    difficulty = data.get("difficulty", "medium")
    total_questions = min(max(int(data.get("total_questions", 10)), 3), 30)
    voice_mode = bool(data.get("voice_mode", False))

    if not project_id:
        return jsonify({"error": "project_id is required."}), 400

    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"

    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            return jsonify({"error": "Project not found."}), 404
        if project.processing_status != "ready":
            return jsonify({
                "error": f"Project is not ready (status: {project.processing_status}). "
                         "Please wait for processing to complete."
            }), 400

        session = VivaSession(
            project_id=project_id,
            difficulty=difficulty,
            total_questions=total_questions,
            voice_mode=voice_mode,
            status="active",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return jsonify({"session": session.to_dict()}), 201
    finally:
        db.close()


@sessions_bp.route("/<int:session_id>", methods=["GET"])
def get_session(session_id: int):
    db = SessionLocal()
    try:
        session = db.get(VivaSession, session_id)
        if not session:
            return jsonify({"error": "Session not found."}), 404
        return jsonify({"session": session.to_dict()})
    finally:
        db.close()


@sessions_bp.route("/<int:session_id>/question", methods=["GET"])
def get_current_question(session_id: int):
    """
    Get the current question. If none exists yet (or the last was answered),
    generate a new one and persist it.
    """
    db = SessionLocal()
    try:
        session = db.get(VivaSession, session_id)
        if not session:
            return jsonify({"error": "Session not found."}), 404

        if session.status != "active":
            return jsonify({"error": "Session is not active.", "status": session.status}), 400

        # Check if exam is complete
        answered_count = sum(1 for q in session.questions if q.student_answer)
        if answered_count >= session.total_questions:
            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)
            db.commit()
            return jsonify({
                "exam_complete": True,
                "session_id": session_id,
                "message": "All questions answered. Retrieve the final report.",
            })

        # Return existing unanswered question
        unanswered = [q for q in session.questions if not q.student_answer]
        if unanswered:
            return jsonify({"question": unanswered[0].to_dict(), "exam_complete": False})

        # Generate new question
        project = db.get(Project, session.project_id)
        if not project:
            return jsonify({"error": "Project not found."}), 404

        history = [q.to_dict() for q in session.questions]
        topics_covered = session.topics_covered_list
        misconceptions = session.misconceptions_list

        # Determine adaptive difficulty
        recent_scores = [q.score for q in session.questions[-3:] if q.score is not None]
        current_difficulty = session.difficulty
        if recent_scores:
            avg_recent = sum(recent_scores) / len(recent_scores)
            if avg_recent >= 80 and current_difficulty != "hard":
                current_difficulty = "hard"
            elif avg_recent <= 40 and current_difficulty != "easy":
                current_difficulty = "easy"

        # Retrieve context for question generation
        context_query = f"Project overview: {project.title} architecture technologies implementation"
        evidence = _retrieve_context(project.id, context_query, top_k=6)

        try:
            q_data = generate_question(
                project_title=project.title,
                evidence_chunks=evidence,
                session_history=history,
                difficulty=current_difficulty,
                topics_covered=topics_covered,
                misconceptions=misconceptions,
                rubric_weights=_get_rubric_weights(),
            )
        except Exception as exc:
            logger.error("Question generation failed: %s", exc)
            error_msg = str(exc)
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                return jsonify({"error": "AI service unavailable – check GROQ_API_KEY."}), 503
            return jsonify({"error": f"Failed to generate question: {exc}"}), 503

        # Persist question
        question = Question(
            session_id=session_id,
            question_index=len(session.questions),
            question_text=q_data.get("question_text", ""),
            topic=q_data.get("topic", "General"),
            difficulty=q_data.get("difficulty", current_difficulty),
            expected_concepts=str(q_data.get("expected_concepts", [])),
        )
        question.feedback = {"evidence_refs": q_data.get("evidence_refs", [])}
        db.add(question)

        # Track topic
        new_topics = topics_covered + [q_data.get("topic", "")]
        session.topics_covered_list = new_topics
        db.commit()
        db.refresh(question)

        return jsonify({"question": question.to_dict(), "exam_complete": False})
    finally:
        db.close()


@sessions_bp.route("/<int:session_id>/answer", methods=["POST"])
def submit_answer(session_id: int):
    """Submit a text answer for the current question."""
    data = request.get_json(force=True, silent=True) or {}
    question_id = data.get("question_id")
    student_answer = (data.get("answer") or "").strip()

    if not question_id:
        return jsonify({"error": "question_id is required."}), 400

    db = SessionLocal()
    try:
        session = db.get(VivaSession, session_id)
        if not session or session.status != "active":
            return jsonify({"error": "Session not found or not active."}), 400

        question = db.get(Question, question_id)
        if not question or question.session_id != session_id:
            return jsonify({"error": "Question not found in this session."}), 404

        if question.student_answer:
            return jsonify({"error": "Question already answered."}), 400

        project = db.get(Project, session.project_id)
        if not project:
            return jsonify({"error": "Project not found."}), 404

        # Retrieve relevant context for evaluation
        evidence = _retrieve_context(
            project.id,
            query=f"{question.question_text} {student_answer}",
            top_k=5,
        )

        import ast
        try:
            expected = ast.literal_eval(question.expected_concepts) if question.expected_concepts else []
        except Exception:
            expected = []

        try:
            feedback = evaluate_answer(
                question_text=question.question_text,
                student_answer=student_answer,
                expected_concepts=expected,
                evidence_chunks=evidence,
                project_title=project.title,
                difficulty=question.difficulty,
                rubric_weights=_get_rubric_weights(),
            )
        except Exception as exc:
            logger.error("Answer evaluation failed: %s", exc)
            error_msg = str(exc)
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                return jsonify({"error": "AI service unavailable – check GROQ_API_KEY."}), 503
            return jsonify({"error": f"Evaluation failed: {exc}"}), 503

        # Update question record
        question.student_answer = student_answer
        question.score = feedback.get("score", 0)
        question.correctness = feedback.get("correctness", "")
        question.feedback = feedback
        question.answered_at = datetime.now(timezone.utc)

        # Track misconceptions
        if feedback.get("misconceptions"):
            existing = session.misconceptions_list
            for m in feedback["misconceptions"]:
                if m and len(m) > 5:
                    existing.append({"topic": question.topic, "misconception": m})
            session.misconceptions_list = existing[-20:]  # keep last 20

        # Recalculate overall score
        answered = [q for q in session.questions if q.score is not None]
        if answered:
            session.overall_score = sum(q.score for q in answered) / len(answered)

        db.commit()

        return jsonify({
            "feedback": feedback,
            "question_index": question.question_index,
            "score": question.score,
            "session_score": round(session.overall_score, 1),
            "questions_answered": len(answered),
            "total_questions": session.total_questions,
        })
    finally:
        db.close()


@sessions_bp.route("/<int:session_id>/history", methods=["GET"])
def get_history(session_id: int):
    """Get all question/answer history for a session."""
    db = SessionLocal()
    try:
        session = db.get(VivaSession, session_id)
        if not session:
            return jsonify({"error": "Session not found."}), 404
        questions = [q.to_dict() for q in session.questions]
        return jsonify({
            "session": session.to_dict(),
            "questions": questions,
        })
    finally:
        db.close()


@sessions_bp.route("/<int:session_id>/report", methods=["GET"])
def get_report(session_id: int):
    """Generate and return the final performance report."""
    db = SessionLocal()
    try:
        session = db.get(VivaSession, session_id)
        if not session:
            return jsonify({"error": "Session not found."}), 404

        project = db.get(Project, session.project_id)
        if not project:
            return jsonify({"error": "Project not found."}), 404

        answered_questions = [q.to_dict() for q in session.questions if q.student_answer]

        if not answered_questions:
            return jsonify({"error": "No questions have been answered yet."}), 400

        # Mark session complete if not already
        if session.status == "active":
            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)
            db.commit()

        try:
            report = generate_final_report(
                project_title=project.title,
                session_data=session.to_dict(),
                questions=answered_questions,
            )
        except Exception as exc:
            logger.error("Report generation failed: %s", exc)
            report = {
                "overall_score": round(session.overall_score, 1),
                "error": f"Full report generation failed: {exc}",
            }

        return jsonify({
            "report": report,
            "session": session.to_dict(),
            "questions": answered_questions,
        })
    finally:
        db.close()


@sessions_bp.route("/<int:session_id>", methods=["DELETE"])
def delete_session(session_id: int):
    db = SessionLocal()
    try:
        session = db.get(VivaSession, session_id)
        if not session:
            return jsonify({"error": "Session not found."}), 404
        db.delete(session)
        db.commit()
        return jsonify({"message": "Session deleted."})
    finally:
        db.close()
