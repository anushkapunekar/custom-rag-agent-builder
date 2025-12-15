# backend/app/rag_utils.py

import json
import numpy as np
from pathlib import Path
from typing import List
from sentence_transformers import SentenceTransformer

APP_DIR = Path(__file__).resolve().parent
STORAGE_DIR = APP_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

# ============================================================
# EMBEDDING MODEL (used everywhere)
# ============================================================
EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")


# ============================================================
# BASIC FIXED CHUNKER (DO NOT REMOVE — used by maintenance.py)
# ============================================================
def chunk_text(text: str, chunk_size: int = 800, overlap: int = 200) -> List[str]:
    """
    Fixed-size sliding window chunker.
    This is your ORIGINAL chunker and must stay.
    """
    if not text:
        return []

    t = text.replace("\r\n", "\n")
    chunks = []
    n = len(t)
    i = 0

    while i < n:
        end = min(i + chunk_size, n)
        piece = t[i:end]

        # try to break at whitespace
        if end < n:
            last_space = piece.rfind(" ")
            if last_space > chunk_size * 0.5:
                piece = piece[:last_space]
                end = i + len(piece)

        cleaned = piece.strip()
        if cleaned:
            chunks.append(cleaned)

        i = max(end - overlap, end)

    return chunks


# ============================================================
# 🔥 NEW: STRATEGY-BASED CHUNKER (AGENT CONFIG)
# ============================================================
def chunk_text_strategy(
    text: str,
    strategy: str = "fixed",
    chunk_size: int = 800,
    overlap: int = 200
) -> List[str]:
    """
    Flexible chunking strategies used by agents.

    Supported:
      - fixed      → original sliding window
      - sentences  → sentence-aware aggregation
      - smart      → sentence-aware + merge small chunks

    Returns list of chunk strings.
    """
    if not text:
        return []

    strategy = (strategy or "fixed").lower()

    # -----------------------------
    # FIXED (default)
    # -----------------------------
    if strategy == "fixed":
        return chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    # -----------------------------
    # SENTENCE-BASED
    # -----------------------------
    import re

    sentences = re.split(
        r'(?<=[\.\!\?])\s+',
        text.replace("\r\n", "\n")
    )

    chunks = []
    current = ""

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        if len(current) + len(sent) + 1 <= chunk_size:
            current = f"{current} {sent}".strip()
        else:
            if current:
                chunks.append(current)
            # fallback to fixed chunking if sentence is huge
            if len(sent) > chunk_size:
                chunks.extend(chunk_text(sent, chunk_size, overlap))
                current = ""
            else:
                current = sent

    if current:
        chunks.append(current)

    # -----------------------------
    # SMART (merge small chunks)
    # -----------------------------
    if strategy == "smart":
        merged = []
        buffer = ""

        for c in chunks:
            if not buffer:
                buffer = c
            elif len(buffer) + len(c) + 1 <= chunk_size:
                buffer = buffer + "\n" + c
            else:
                merged.append(buffer)
                buffer = c

        if buffer:
            merged.append(buffer)

        return merged

    return chunks


# ============================================================
# GLOBAL USER INDEX (CUSTOM RAG)
# ============================================================
def build_and_save_index(user_id, full_text, doc_id=None, filename=None):
    """
    Saves embeddings into:
      storage/<user_id>/embeddings.npy
      storage/<user_id>/meta.json
    """
    user_dir = STORAGE_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    emb_path = user_dir / "embeddings.npy"
    meta_path = user_dir / "meta.json"

    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    vectors = EMBED_MODEL.encode(
        chunks,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    if emb_path.exists():
        existing = np.load(emb_path)
        vectors = np.vstack([existing, vectors]) if existing.size else vectors

    np.save(emb_path, vectors)

    metas_new = [
        {
            "text": c,
            "docId": doc_id or "",
            "filename": filename or ""
        }
        for c in chunks
    ]

    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8", errors="ignore"))
        meta.extend(metas_new)
    else:
        meta = metas_new

    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return len(chunks)


# ============================================================
# AGENT-SPECIFIC INDEX (PER AGENT)
# ============================================================
def build_and_save_index_to_dir(
    user_id,
    full_text,
    target_dir: Path,
    doc_id: str = None,
    filename: str = None
):
    """
    Saves embeddings inside agent directory:
      storage/<user>/agents/<agent>/embeddings.npy
      storage/<user>/agents/<agent>/meta.json
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    emb_path = target_dir / "embeddings.npy"
    meta_path = target_dir / "meta.json"

    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    vectors = EMBED_MODEL.encode(
        chunks,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    if emb_path.exists():
        existing = np.load(emb_path)
        vectors = np.vstack([existing, vectors]) if existing.size else vectors

    np.save(emb_path, vectors)

    metas_new = [
        {
            "text": c,
            "docId": doc_id or "",
            "filename": filename or ""
        }
        for c in chunks
    ]

    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8", errors="ignore"))
        meta.extend(metas_new)
    else:
        meta = metas_new

    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return len(chunks)


# ============================================================
# LOAD INDEX FROM ANY DIRECTORY
# ============================================================
def load_index_from_dir(target_dir: Path):
    emb_path = target_dir / "embeddings.npy"
    meta_path = target_dir / "meta.json"

    if not emb_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"Index not found in: {target_dir}")

    vectors = np.load(emb_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8", errors="ignore"))

    return vectors, meta
