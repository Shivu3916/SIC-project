"""
Flask application factory.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from config import Config
from app.models.database import init_db


def create_app() -> Flask:
    """Create and configure the Flask application."""
    template_dir = Path(__file__).parent / "app" / "templates"
    static_dir = Path(__file__).parent / "app" / "static"

    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir),
    )

    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
    app.config["DEBUG"] = Config.DEBUG

    # Ensure storage directories exist
    Path(Config.UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    Path(Config.FAISS_INDEX_DIR).mkdir(parents=True, exist_ok=True)

    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG if Config.DEBUG else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Warn about missing config
    for warning in Config.validate():
        logging.getLogger(__name__).warning("CONFIG WARNING: %s", warning)

    # Initialise database
    init_db()

    # Register blueprints
    from app.routes.projects import projects_bp
    from app.routes.sessions import sessions_bp
    from app.routes.speech import speech_bp

    app.register_blueprint(projects_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(speech_bp)

    # Frontend routes
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/viva/<int:session_id>")
    def viva(session_id: int):
        return render_template("viva.html", session_id=session_id)

    @app.route("/report/<int:session_id>")
    def report(session_id: int):
        return render_template("report.html", session_id=session_id)

    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found."}), 404
        return render_template("index.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": f"File too large. Maximum size: {Config.MAX_UPLOAD_SIZE_MB}MB"}), 413

    @app.errorhandler(500)
    def server_error(e):
        logging.getLogger(__name__).error("Unhandled 500 error: %s", e)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error."}), 500
        return render_template("index.html"), 500

    return app
