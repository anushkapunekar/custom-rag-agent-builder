# backend/app/maintenance.py
import json
import numpy as np
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException

from .auth import decode_token, get_user_by_id
from .utils import ensure_user_dir
from .rag_utils import chunk_text, EMBED_MODEL

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

APP_DIR = Path(__file__).resolve().parent
STORAGE_DIR = APP_DIR / "storage"


def cosine_sim(a, b):
    return float(np.dot(a, b))


def load_all_user_docs(user_id: str):
    """
    Load raw text from all uploaded documents.
    """
    user_dir = ensure_user_dir(user_id)
    docs_dir = user_dir / "docs"

    texts = []

    if docs_dir.exists():
        for p in docs_dir.iterdir():
            if p.is_file():
                try:
                    raw = p.read_bytes().decode("utf-8", errors="ignore")
                    texts.append((p.name, raw))
                except:
                    pass

    return texts


@router.post("/rebuild_index")
def rebuild_index(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")

    token = authorization.split()[1]
    payload = decode_token(token)
    user_id = payload["sub"]

    user_dir = STORAGE_DIR / user_id
    meta_path = user_dir / "meta.json"
    emb_path = user_dir / "embeddings.npy"

    # ----------------------------------------------------
    # 1. Load raw docs (the real uploaded documents)
    # ----------------------------------------------------
    raw_docs = load_all_user_docs(user_id)

    # ----------------------------------------------------
    # 2. Load synthetic memories from old meta.json
    # ----------------------------------------------------
    synthetic_blocks = []
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except:
            meta = json.loads(meta_path.read_text(errors="ignore"))

        for m in meta:
            if m.get("filename") == "__synthetic__":
                synthetic_blocks.append(("__synthetic__", m["text"]))

    # ----------------------------------------------------
    # 3. Re-chunk everything
    # ----------------------------------------------------
    new_chunks = []
    meta_output = []

    # Real documents
    for filename, text in raw_docs:
        chunks = chunk_text(text)
        for c in chunks:
            new_chunks.append(c)
            meta_output.append({
                "text": c,
                "filename": filename,
                "docId": filename
            })

    # Synthetic memories
    for _, text in synthetic_blocks:
        chunks = chunk_text(text, chunk_size=500)
        for c in chunks:
            new_chunks.append(c)
            meta_output.append({
                "text": c,
                "filename": "__synthetic__",
                "docId": "__synthetic__"
            })

    if not new_chunks:
        raise HTTPException(400, "No data found to rebuild index.")

    # ----------------------------------------------------
    # 4. Embed everything
    # ----------------------------------------------------
    vectors = EMBED_MODEL.encode(new_chunks, convert_to_numpy=True, normalize_embeddings=True)

    # ----------------------------------------------------
    # 5. Deduplicate using cosine similarity
    # ----------------------------------------------------
    unique_vectors = []
    unique_meta = []
    threshold = 0.97  # tune if needed

    for i, v in enumerate(vectors):
        if len(unique_vectors) == 0:
            unique_vectors.append(v)
            unique_meta.append(meta_output[i])
            continue

        sims = np.dot(np.array(unique_vectors), v)
        if float(np.max(sims)) < threshold:
            unique_vectors.append(v)
            unique_meta.append(meta_output[i])

    unique_vectors = np.array(unique_vectors)

    # ----------------------------------------------------
    # 6. Write fresh index
    # ----------------------------------------------------
    np.save(emb_path, unique_vectors)
    meta_path.write_text(json.dumps(unique_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "status": "ok",
        "total_chunks": len(new_chunks),
        "unique_chunks": len(unique_vectors),
        "synthetic_items": len(synthetic_blocks),
        "message": "Index successfully rebuilt and deduplicated."
    }
