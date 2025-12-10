# backend/app/retriever.py
import json
import numpy as np
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Header

from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from .auth import decode_token, get_user_by_id

router = APIRouter(prefix="/qa", tags=["qa"])

APP_DIR = Path(__file__).resolve().parent
STORAGE_DIR = APP_DIR / "storage"

# embed model
EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")

# free HF generation model
GEN_MODEL_NAME = "google/flan-t5-base"
GEN_TOKENIZER = AutoTokenizer.from_pretrained(GEN_MODEL_NAME)
GEN_MODEL = AutoModelForSeq2SeqLM.from_pretrained(GEN_MODEL_NAME)


# ============================================================
# JSON SANITIZER — prevents int64 / float32 errors
# ============================================================
def to_serializable(obj):
    import numpy as np
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="ignore")
    if isinstance(obj, (list, dict, str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


# ============================================================
# Chat history (per user)
def history_path_for_user(user_id: str) -> Path:
    user_dir = STORAGE_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "chat_history.json"



def load_history(user_id: str):
    p = history_path_for_user(user_id)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except:
        return []


def save_history(user_id: str, history):
    p = history_path_for_user(user_id)

    # sanitize before saving
    clean_history = []
    for msg in history:
        sanitized = {k: to_serializable(v) for k, v in msg.items()}
        clean_history.append(sanitized)

    p.write_text(json.dumps(clean_history, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


# ============================================================
# Load embeddings + metadata
# ============================================================
def load_user_index(user_id: str):
    user_dir = STORAGE_DIR / user_id
    emb_path = user_dir / "embeddings.npy"
    meta_path = user_dir / "meta.json"

    if not emb_path.exists() or not meta_path.exists():
        raise HTTPException(400, "No indexed documents found.")

    vectors = np.load(emb_path)

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except:
        meta = json.loads(meta_path.read_text(errors="ignore"))

    return vectors, meta


# ============================================================
# SEARCH
# ============================================================
# ============================================================
# SEARCH (supports normal RAG + AGENT RAG)
# ============================================================
def search(query: str, k: int, vectors, meta, doc_filter=None):

    q_vec = EMBED_MODEL.encode(query, convert_to_numpy=True, normalize_embeddings=True)
    sims = np.dot(vectors, q_vec)

    topk_idx = sims.argsort()[::-1]

    results = []
    for i in topk_idx:
        m = meta[i]

        # -------------------------------
        # NEW AGENT-AWARE FILTERING
        # Allows docId formats like:
        #   "fileId"
        #   "agentId:fileId"
        # -------------------------------
        if doc_filter:
            md = m.get("docId", "")
            # agent chunks are saved as "agentId:realDocId"
            if md and str(md).startswith(f"{doc_filter}:"):
                pass  # allow this chunk
            else:
                continue  # skip chunks not belonging to this agent

        # -------------------------------
        # Normal chunk acceptance
        # -------------------------------
        results.append({
            "score": float(sims[i]),
            "text": m["text"],
            "filename": m.get("filename", ""),
            "docId": m.get("docId", ""),
            "chunk_id": to_serializable(i),
        })

        if len(results) >= k:
            break

    return results


# ============================================================
# Retrieve endpoint
# ============================================================
@router.post("/retrieve")
async def retrieve(request: Request, authorization: str = Header(None)):

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")

    token = authorization.split()[1]
    payload = decode_token(token)
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(404, "User not found")

    body = await request.json()
    query = body.get("query")
    k = int(body.get("k", 5))
    docId = body.get("docId")

    if not query:
        raise HTTPException(400, "Query is required")

    vectors, meta = load_user_index(user["id"])
    results = search(query, k, vectors, meta, doc_filter=docId)

    return {"results": results}


# ============================================================
# Chat history endpoints
# ============================================================
@router.get("/history")
async def get_history(authorization: str = Header(None)):
    token = authorization.split()[1]
    payload = decode_token(token)
    history = load_history(payload["sub"])
    return {"history": history}


@router.post("/history")
async def post_history(request: Request, authorization: str = Header(None)):

    token = authorization.split()[1]
    payload = decode_token(token)

    body = await request.json()
    action = body.get("action", "append")
    messages = body.get("messages", [])

    history = load_history(payload["sub"])

    if action == "replace":
        history = messages
    else:
        history.extend(messages)

    save_history(payload["sub"], history)

    return {"history": history}


# ============================================================
# GENERATE Answer + Save to History
# ============================================================
# inside backend/app/retriever.py — replace the generate endpoint with this

@router.post("/generate")
async def generate_answer(request: Request, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")

    token = authorization.split()[1]
    payload = decode_token(token)
    user_id = payload["sub"]

    try:
        body = await request.json()
    except:
        body = {}

    query = body.get("query")
    k = int(body.get("k", 5))
    max_new_tokens = min(int(body.get("max_new_tokens", 64)), 256)
    docId = body.get("docId")  # optional: restrict retrieval to one doc
    save_memory = body.get("save_memory", True)  # default: auto-save enabled

    if not query:
        raise HTTPException(400, "Missing query")

    # load index and retrieve context
    vectors, meta = load_user_index(user_id)
    ctx = search(query, k, vectors, meta, doc_filter=docId)
    context_text = "\n\n".join([c["text"] for c in ctx])

    prompt = (
        f"Context:\n{context_text}\n\n"
        f"Question: {query}\n"
        "Answer using ONLY the context above."
    )

    # generate answer
    try:
        inputs = GEN_TOKENIZER(prompt, return_tensors="pt", truncation=True)
        outputs = GEN_MODEL.generate(**inputs, max_new_tokens=max_new_tokens)
        answer = GEN_TOKENIZER.decode(outputs[0], skip_special_tokens=True)
    except Exception as e:
        raise HTTPException(500, f"Model generation error: {e}")

    # -------------------------
    # AUTO-MEMORY / SELF-LEARNING
    # -------------------------
    # We will save a synthetic Q/A "document" into the user's index unless:
    #  - save_memory == False
    #  - question appears highly similar to existing vectors (duplication)
    memory_saved = False
    memory_doc_id = None

    if save_memory:
        try:
            import time
            ts = int(time.time())
            synthetic_doc_id = f"synthetic-{ts}"

            # Create a short synthetic text: Q + A
            synthetic_text = f"Q: {query}\nA: {answer}"

            # Dedup check: compute embedding for the question (or for synthetic_text)
            q_vec = EMBED_MODEL.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]

            # If vectors exist, check similarity to avoid duplicates:
            emb_path = (STORAGE_DIR / user_id) / "embeddings.npy"
            if emb_path.exists():
                existing = np.load(emb_path)
                if existing.size:
                    sims = np.dot(existing, q_vec)
                    max_sim = float(np.max(sims))
                else:
                    max_sim = 0.0
            else:
                max_sim = 0.0

            # similarity threshold (0.0 - 1.0). Tune as needed.
            SIMILARITY_THRESHOLD = 0.95

            if max_sim < SIMILARITY_THRESHOLD:
                # append to index using your existing helper (it supports doc_id & filename)
                # NOTE: build_and_save_index will chunk/encode and append
                added_chunks = build_and_save_index(user_id, synthetic_text, doc_id=synthetic_doc_id, filename="__synthetic__")
                memory_saved = True
                memory_doc_id = synthetic_doc_id
            else:
                # skip saving because similar content already exists
                memory_saved = False
                memory_doc_id = None
        except Exception as e:
            # don't crash generation if memory save fails — log and continue
            print("Memory save error:", e)
            memory_saved = False
            memory_doc_id = None

    # -------------------------
    # Save Q/A to chat history (unchanged behavior)
    # -------------------------
    import time
    ts = int(time.time())
    user_msg = {"role": "user", "text": query, "ts": ts}
    bot_msg = {"role": "assistant", "text": answer, "ts": ts + 1, "sources": ctx}

    history = load_history(user_id)
    history.append(user_msg)
    history.append(bot_msg)
    # ensure all types in history are JSON-serializable (convert numpy ints if any)
    def _sanitize(obj):
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(x) for x in obj]
        # convert numpy scalar types to python native
        if hasattr(obj, "item"):
            try:
                return obj.item()
            except:
                return obj
        return obj

    history = _sanitize(history)
    save_history(user_id, history)

    return {
        "answer": answer,
        "sources": ctx,
        "history": history,
        "memory_saved": memory_saved,
        "memory_doc_id": memory_doc_id
    }
