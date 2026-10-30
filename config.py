"""
Application configuration loaded from environment variables via python-dotenv.
All secrets stay server-side; never expose them to frontend code.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY: str = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-prod")
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # Groq
    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
    GROQ_LLM_MODEL: str = os.environ.get("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
    GROQ_WHISPER_MODEL: str = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

    # Storage
    UPLOAD_FOLDER: str = os.path.abspath(os.environ.get("UPLOAD_FOLDER", "uploads"))
    FAISS_INDEX_DIR: str = os.path.abspath(os.environ.get("FAISS_INDEX_DIR", "faiss_indexes"))
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///viva_simulator.db")

    # File limits
    MAX_UPLOAD_SIZE_MB: int = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "50"))
    MAX_CONTENT_LENGTH: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    ALLOWED_EXTENSIONS: set = {"pdf", "docx", "txt", "md"}

    # Embedding
    EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # RAG chunking
    CHUNK_SIZE: int = int(os.environ.get("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP: int = int(os.environ.get("CHUNK_OVERLAP", "150"))

    # Evaluation weights (must sum to 100)
    WEIGHT_TECHNICAL_CORRECTNESS: int = int(os.environ.get("WEIGHT_TECHNICAL_CORRECTNESS", "40"))
    WEIGHT_DEPTH_OF_REASONING: int = int(os.environ.get("WEIGHT_DEPTH_OF_REASONING", "30"))
    WEIGHT_PROJECT_SPECIFIC: int = int(os.environ.get("WEIGHT_PROJECT_SPECIFIC", "20"))
    WEIGHT_COMPLETENESS: int = int(os.environ.get("WEIGHT_COMPLETENESS", "10"))

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of configuration warnings."""
        warnings = []
        if not cls.GROQ_API_KEY:
            warnings.append("GROQ_API_KEY not set – AI features will be unavailable.")
        total = (
            cls.WEIGHT_TECHNICAL_CORRECTNESS
            + cls.WEIGHT_DEPTH_OF_REASONING
            + cls.WEIGHT_PROJECT_SPECIFIC
            + cls.WEIGHT_COMPLETENESS
        )
        if total != 100:
            warnings.append(f"Evaluation weights sum to {total}, not 100.")
        return warnings
