# backend/app/rag_utils.py
import json
import os
import numpy as np
from pathlib import Path
from typing import Optional
from sentence_transformers import SentenceTransformer

APP_DIR = Path(__file__).resolve().parent
STORAGE_DIR = APP_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")

def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

# ------------------------------
# Robust chunker
# ------------------------------
def chunk_text_strategy(text: str, strategy: str, chunk_size: int, overlap: int):
    text = text.replace("\r\n", "\n").strip()

    # FIXED SIZE CHUNKING
    if strategy == "fixed":
        return chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    # SENTENCE-BASED
    if strategy == "sentence":
        import re
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    # PARAGRAPH-BASED
    if strategy == "paragraph":
        paragraphs = text.split("\n\n")
        return [p.strip() for p in paragraphs if p.strip()]

    # SEMANTIC CHUNKING (simple clustering)
    if strategy == "semantic":
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        sentences = text.split(". ")
        embeds = model.encode(sentences)
        chunks = []
        current = sentences[0]

        for i in range(1, len(sentences)):
            sim = np.dot(embeds[i], embeds[i-1])
            if sim > 0.6:
                current += ". " + sentences[i]
            else:
                chunks.append(current)
                current = sentences[i]

        chunks.append(current)
        return [c.strip() for c in chunks if c.strip()]

    # FALLBACK
    return chunk_text(text, chunk_size=chunk_size, overlap=overlap)


def _safe_json_load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(path.read_text(errors="ignore"))


# ============================================================
#  GLOBAL USER INDEX (your original working RAG)
# ============================================================
def build_and_save_index(user_id, full_text, doc_id=None, filename=None):
    """
    Saves into: storage/<user_id>/embeddings.npy + meta.json
    """
    user_dir = STORAGE_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    emb_path = user_dir / "embeddings.npy"
    meta_path = user_dir / "meta.json"

    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    vectors = EMBED_MODEL.encode(chunks, convert_to_numpy=True, normalize_embeddings=True)

    # append or create
    if emb_path.exists():
        existing = np.load(emb_path)
        combined = np.vstack([existing, vectors]) if existing.size else vectors
    else:
        combined = vectors

    np.save(emb_path, combined)

    metas_new = [{
        "text": c,
        "docId": doc_id or "",
        "filename": filename or ""
    } for c in chunks]

    if meta_path.exists():
        prev = json.loads(meta_path.read_text(encoding="utf-8"))
        metas = prev + metas_new
    else:
        metas = metas_new

    meta_path.write_text(json.dumps(metas, ensure_ascii=False, indent=2), encoding="utf-8")

    return len(chunks)


# ============================================================
#  AGENT-SPECIFIC INDEX SUPPORT (NEW)
# ============================================================
def build_and_save_index_to_dir(user_id, full_text, target_dir: Path, doc_id: str = None, filename: str = None):
    """
    Build embeddings from `full_text` and append them into an index stored inside `target_dir`.
    This creates (or appends to) target_dir/embeddings.npy and target_dir/meta.json.

    Args:
      user_id: for bookkeeping (not used to pick location — target_dir is authoritative)
      full_text: raw extracted text to chunk
      target_dir: Path object where embeddings.npy + meta.json live (will be created)
      doc_id: optional doc id (we store this in metadata)
      filename: original filename for metadata
    Returns:
      number_of_chunks_added (int)
    """
    _ensure_dir(target_dir)

    emb_path = target_dir / "embeddings.npy"
    meta_path = target_dir / "meta.json"

    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    # embed chunks
    vectors = EMBED_MODEL.encode(chunks, convert_to_numpy=True, normalize_embeddings=True)

    # append or create embeddings file
    if emb_path.exists():
        existing = np.load(emb_path)
        combined = np.vstack([existing, vectors]) if existing.size else vectors
    else:
        combined = vectors

    np.save(emb_path, combined)

    # build metadata list
    metas_new = []
    for c in chunks:
        metas_new.append({
            "text": c,
            "docId": doc_id or "",
            "filename": filename or ""
        })

    if meta_path.exists():
        try:
            prev = json.loads(meta_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            prev = []
        metas = prev + metas_new
    else:
        metas = metas_new

    meta_path.write_text(json.dumps(metas, ensure_ascii=False, indent=2), encoding="utf-8")

    return len(chunks)


# ============================================================
#  LOAD INDEX FROM ANY DIRECTORY (GLOBAL OR AGENT)
# ============================================================
def load_index_from_dir(target_dir: Path):
    emb_path = target_dir / "embeddings.npy"
    meta_path = target_dir / "meta.json"

    if not emb_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"Index not found in: {target_dir}")

    vectors = np.load(emb_path)
    with open(meta_path, "r", encoding="utf-8", errors="ignore") as f:
        meta = json.load(f)

    return vectors, meta

# compatibility wrapper for old code
def chunk_text(text, chunk_size=800, overlap=200):
    # default to fixed strategy behavior
    return chunk_text_strategy(text, "fixed", chunk_size, overlap)
