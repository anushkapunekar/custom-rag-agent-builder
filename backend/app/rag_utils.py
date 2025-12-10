# backend/app/rag_utils.py
import json
import numpy as np
from pathlib import Path
from typing import Optional
from sentence_transformers import SentenceTransformer

APP_DIR = Path(__file__).resolve().parent
STORAGE_DIR = APP_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")


# ------------------------------
# Robust chunker
# ------------------------------
def chunk_text(text: str, chunk_size: int = 800, overlap: int = 200):
    t = text.replace("\r\n", "\n")
    chunks = []
    n = len(t)
    i = 0

    while i < n:
        end = min(i + chunk_size, n)
        piece = t[i:end]

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


def _safe_json_load(path: Path):
    """
    Loads JSON even if UTF-8 errors exist.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(path.read_text(errors="ignore"))


# ============================================================
#  BUILD & SAVE INDEX (MULTI-DOCUMENT SAFE VERSION)
# ============================================================
def build_and_save_index(user_id: str, text: str, doc_id: str, filename: str):
    """
    Creates chunks & embeddings for ONE document and appends them to index.
    Adds metadata with doc_id, filename, chunk_id.
    """
    user_dir = STORAGE_DIR / str(user_id)
    user_dir.mkdir(exist_ok=True)

    emb_path = user_dir / "embeddings.npy"
    meta_path = user_dir / "meta.json"

    # -------------------------
    # 1. Chunk text
    # -------------------------
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No text chunks created for this document.")

    # -------------------------
    # 2. Create embeddings
    # -------------------------
    vectors = EMBED_MODEL.encode(
        chunks,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    # -------------------------
    # 3. Append embeddings safely
    # -------------------------
    if emb_path.exists():
        existing_vectors = np.load(emb_path)
        if existing_vectors.size == 0:
            combined = vectors
        else:
            combined = np.vstack([existing_vectors, vectors])
    else:
        combined = vectors

    np.save(emb_path, combined)

    # -------------------------
    # 4. Append metadata safely
    # -------------------------
    if meta_path.exists():
        prev_meta = _safe_json_load(meta_path)
    else:
        prev_meta = []

    start_index = len(prev_meta)  # global chunk offset

    metas_new = []
    for i, chunk in enumerate(chunks):
        metas_new.append({
            "text": chunk,
            "docId": doc_id,
            "filename": filename,
            "chunk_id": start_index + i
        })

    meta_path.write_text(
        json.dumps(prev_meta + metas_new, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return len(chunks)
