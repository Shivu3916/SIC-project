"""
RAG vector store management using FAISS + sentence-transformers.
Each project gets its own isolated FAISS index to prevent cross-contamination.
"""
from __future__ import annotations

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Optional

import faiss
import numpy as np

from app.rag.document_parser import ParsedChunk
from config import Config

logger = logging.getLogger(__name__)

# Lazy-loaded singleton embedding model
_embed_model = None


def get_embed_model():
    """Return the (cached) sentence-transformer model."""
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model: %s", Config.EMBEDDING_MODEL)
        _embed_model = SentenceTransformer(Config.EMBEDDING_MODEL)
    return _embed_model


def _embed(texts: list[str]) -> np.ndarray:
    """Embed a list of strings, returning float32 numpy array."""
    model = get_embed_model()
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.astype(np.float32)


class ProjectVectorStore:
    """
    Isolated FAISS index for a single project.
    Stores embeddings alongside chunk metadata so retrieval returns full context.
    """

    def __init__(self, project_id: int):
        self.project_id = project_id
        self.index_dir = Path(Config.FAISS_INDEX_DIR) / f"project_{project_id}"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "index.faiss"
        self.meta_path = self.index_dir / "chunks.pkl"
        self._index: Optional[faiss.Index] = None
        self._chunks: list[dict] = []  # serialisable chunk dicts

    @property
    def index_base_path(self) -> str:
        return str(self.index_dir)

    def build(self, chunks: list[ParsedChunk]) -> None:
        """Embed chunks and build/overwrite the FAISS index."""
        if not chunks:
            raise ValueError("No chunks provided to build index.")

        texts = [c.text for c in chunks]
        logger.info("Embedding %d chunks for project %d …", len(texts), self.project_id)
        embeddings = _embed(texts)

        dim = embeddings.shape[1]
        self._index = faiss.IndexFlatL2(dim)
        self._index.add(embeddings)

        self._chunks = [c.to_dict() for c in chunks]

        # Persist
        faiss.write_index(self._index, str(self.index_path))
        with open(self.meta_path, "wb") as f:
            pickle.dump(self._chunks, f)

        logger.info("Index built: %d vectors, dim=%d", self._index.ntotal, dim)

    def load(self) -> bool:
        """Load an existing index from disk. Returns True on success."""
        if not self.index_path.exists() or not self.meta_path.exists():
            return False
        try:
            self._index = faiss.read_index(str(self.index_path))
            with open(self.meta_path, "rb") as f:
                self._chunks = pickle.load(f)
            return True
        except Exception as exc:
            logger.error("Failed to load index for project %d: %s", self.project_id, exc)
            return False

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Retrieve the top-k most relevant chunks for a query.
        Loads from disk if not already loaded.
        """
        if self._index is None:
            if not self.load():
                return []

        query_vec = _embed([query])
        distances, indices = self._index.search(query_vec, min(top_k, self._index.ntotal))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            chunk = dict(self._chunks[idx])
            chunk["relevance_score"] = float(1 / (1 + dist))  # similarity proxy
            results.append(chunk)

        return results

    def delete(self) -> None:
        """Remove all index files for this project."""
        import shutil
        if self.index_dir.exists():
            shutil.rmtree(self.index_dir)
            logger.info("Deleted index dir for project %d", self.project_id)

    @property
    def vector_count(self) -> int:
        if self._index is not None:
            return self._index.ntotal
        if self.index_path.exists():
            self.load()
            return self._index.ntotal if self._index else 0
        return 0
