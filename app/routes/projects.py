"""
Project routes: upload, status, list, delete.
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, current_app

from app.models.database import Project, SessionLocal
from app.rag.document_parser import parse_document
from app.rag.vector_store import ProjectVectorStore
from config import Config

logger = logging.getLogger(__name__)

projects_bp = Blueprint("projects", __name__, url_prefix="/api/projects")

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _safe_filename(filename: str) -> str:
    """Remove dangerous characters from filename."""
    name = Path(filename).name
    # Keep only alphanumeric, dot, hyphen, underscore
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    return safe[:200]


def _process_project_async(project_id: int, file_path: str) -> None:
    """Background thread: parse document, build FAISS index, update DB."""
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            return

        project.processing_status = "processing"
        project.processing_message = "Parsing document…"
        db.commit()

        result = parse_document(
            file_path,
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
        )

        if result.error:
            project.processing_status = "failed"
            project.processing_message = result.error
            db.commit()
            return

        if not result.chunks:
            project.processing_status = "failed"
            project.processing_message = (
                "No text could be extracted from the document. "
                + (result.warning or "Please check the file format.")
            )
            db.commit()
            return

        # Update technologies
        project.technologies_list = result.technologies

        # Build vector index
        project.processing_message = "Building search index…"
        db.commit()

        store = ProjectVectorStore(project_id)
        store.build(result.chunks)

        project.chunk_count = len(result.chunks)
        project.faiss_index_path = store.index_base_path
        project.processing_status = "ready"
        project.processing_message = (
            result.warning
            or f"Ready. {len(result.chunks)} chunks indexed."
        )
        db.commit()

    except Exception as exc:
        logger.exception("Background processing failed for project %d: %s", project_id, exc)
        try:
            project = db.get(Project, project_id)
            if project:
                project.processing_status = "failed"
                project.processing_message = f"Processing error: {exc}"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@projects_bp.route("", methods=["POST"])
def upload_project():
    """Upload and process a project document."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    file = request.files["file"]
    title = request.form.get("title", "").strip()

    if not file.filename:
        return jsonify({"error": "No file selected."}), 400

    if not _allowed_file(file.filename):
        return jsonify({
            "error": f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400

    # Check file size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > Config.MAX_CONTENT_LENGTH:
        return jsonify({
            "error": f"File too large. Maximum size: {Config.MAX_UPLOAD_SIZE_MB}MB"
        }), 413

    safe_name = _safe_filename(file.filename)
    ext = safe_name.rsplit(".", 1)[-1].lower()

    # Save with a UUID prefix to avoid collisions
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    upload_dir = Path(Config.UPLOAD_FOLDER)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / unique_name
    file.save(str(file_path))

    if not title:
        title = Path(safe_name).stem.replace("_", " ").replace("-", " ").title()

    db = SessionLocal()
    try:
        project = Project(
            title=title,
            filename=safe_name,
            file_path=str(file_path),
            file_type=ext,
            file_size_bytes=size,
            processing_status="pending",
            processing_message="Queued for processing…",
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        project_id = project.id
        project_dict = project.to_dict()
    finally:
        db.close()

    # Kick off background processing
    thread = threading.Thread(
        target=_process_project_async,
        args=(project_id, str(file_path)),
        daemon=True,
    )
    thread.start()

    return jsonify({"project": project_dict, "message": "Upload successful, processing started."}), 201


@projects_bp.route("", methods=["GET"])
def list_projects():
    """List all uploaded projects."""
    db = SessionLocal()
    try:
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
        return jsonify({"projects": [p.to_dict() for p in projects]})
    finally:
        db.close()


@projects_bp.route("/<int:project_id>", methods=["GET"])
def get_project(project_id: int):
    """Get a single project's details."""
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            return jsonify({"error": "Project not found."}), 404
        return jsonify({"project": project.to_dict()})
    finally:
        db.close()


@projects_bp.route("/<int:project_id>/status", methods=["GET"])
def project_status(project_id: int):
    """Poll processing status (used by frontend SSE-style polling)."""
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            return jsonify({"error": "Project not found."}), 404
        return jsonify({
            "status": project.processing_status,
            "message": project.processing_message,
            "chunk_count": project.chunk_count,
            "technologies": project.technologies_list,
        })
    finally:
        db.close()


@projects_bp.route("/<int:project_id>", methods=["DELETE"])
def delete_project(project_id: int):
    """Delete a project, its file, FAISS index, and all sessions."""
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            return jsonify({"error": "Project not found."}), 404

        # Delete uploaded file
        try:
            if os.path.exists(project.file_path):
                os.unlink(project.file_path)
        except Exception as exc:
            logger.warning("Could not delete file %s: %s", project.file_path, exc)

        # Delete FAISS index
        try:
            store = ProjectVectorStore(project_id)
            store.delete()
        except Exception as exc:
            logger.warning("Could not delete FAISS index: %s", exc)

        db.delete(project)
        db.commit()
        return jsonify({"message": "Project deleted successfully."})
    finally:
        db.close()
