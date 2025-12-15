# backend/app/agents.py

import io
import json
import sqlite3
import time
import logging
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Header,
    BackgroundTasks,
)
from fastapi.responses import JSONResponse

from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import numpy as np

from .auth import decode_token, get_user_by_id
from .utils import decrypt_json
from .drive import build_drive_service_from_creds, extract_text_from_bytes
from .rag_utils import (
    build_and_save_index_to_dir,
    load_index_from_dir,
    chunk_text_strategy,
)

# -------------------------------------------------
# Router & Globals
# -------------------------------------------------

router = APIRouter(prefix="/agents", tags=["agents"])

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "users.db"
STORAGE_BASE = APP_DIR / "storage"
STORAGE_BASE.mkdir(parents=True, exist_ok=True)

# Models
EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
GEN_MODEL_NAME = "google/flan-t5-base"
GEN_TOKENIZER = AutoTokenizer.from_pretrained(GEN_MODEL_NAME)
GEN_MODEL = AutoModelForSeq2SeqLM.from_pretrained(GEN_MODEL_NAME)

AUTO_RETRAIN_THRESHOLD = 0.55  # hybrid mode threshold

# -------------------------------------------------
# Database Init
# -------------------------------------------------

def init_agents_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            config TEXT,
            created_at INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            file_id TEXT,
            filename TEXT,
            saved_path TEXT,
            added_at INTEGER
        )
    """)
    conn.commit()
    conn.close()

init_agents_db()

# -------------------------------------------------
# Helpers
# -------------------------------------------------

def require_auth(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(404, "User not found")
    return user


def agent_dir(user_id: str, agent_id: str) -> Path:
    p = STORAGE_BASE / str(user_id) / "agents" / str(agent_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def agent_history_path(user_id: str, agent_id: str) -> Path:
    p = APP_DIR / "data" / "users" / str(user_id) / "agents" / str(agent_id)
    p.mkdir(parents=True, exist_ok=True)
    return p / "chat_history.json"

# -------------------------------------------------
# Background Retraining Logic
# -------------------------------------------------

def retrain_agent(
    user_id: str,
    agent_id: str,
    query: Optional[str] = None,
    ctx_items: Optional[list] = None,
    better_answer: Optional[str] = None,
):
    """
    Hybrid retraining:
    - If better_answer provided → add synthetic doc
    - Else → re-chunk and re-index all agent docs
    """
    try:
        a_dir = agent_dir(user_id, str(agent_id))
        docs_dir = a_dir / "docs"
        if not docs_dir.exists():
            return

        # Load agent config
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT config FROM agents WHERE id = ? AND user_id = ?",
            (agent_id, int(user_id)),
        )
        row = cur.fetchone()
        conn.close()

        cfg = {}
        try:
            cfg = json.loads(row[0]) if row and row[0] else {}
        except:
            cfg = {}

        strategy = cfg.get("chunk_strategy", "fixed")
        chunk_size = int(cfg.get("chunk_size", 800))
        overlap = int(cfg.get("overlap", 200))

        # ----------------------------
        # Case 1: explicit correction
        # ----------------------------
        if better_answer:
            synthetic = f"Q: {query}\nA: {better_answer}"
            build_and_save_index_to_dir(
                user_id,
                synthetic,
                a_dir,
                doc_id=f"synthetic:{int(time.time())}",
                filename="__user_feedback__",
            )
            return

        # ----------------------------
        # Case 2: reindex all docs
        # ----------------------------
        # Clear old index
        emb = a_dir / "embeddings.npy"
        meta = a_dir / "meta.json"
        if emb.exists(): emb.unlink()
        if meta.exists(): meta.unlink()

        for f in docs_dir.iterdir():
            if not f.is_file():
                continue
            try:
                content = f.read_bytes()
                name = f.name.split("-", 1)[1] if "-" in f.name else f.name
                text = extract_text_from_bytes(content, name, "")
                chunks = chunk_text_strategy(text, strategy, chunk_size, overlap)
                if chunks:
                    build_and_save_index_to_dir(
                        user_id,
                        "\n".join(chunks),
                        a_dir,
                        doc_id=f"reindex:{f.name}",
                        filename=name,
                    )
            except Exception as e:
                logging.exception("Retrain failed on %s: %s", f, e)

    except Exception as e:
        logging.exception("Retrain agent failed: %s", e)

# -------------------------------------------------
# CRUD
# -------------------------------------------------

@router.post("/create")
async def create_agent(request: Request, authorization: str = Header(None)):
    user = require_auth(authorization)
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Agent name required")

    description = body.get("description", "")
    config = body.get("config", {})

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO agents (user_id, name, description, config, created_at) VALUES (?, ?, ?, ?, ?)",
        (int(user["id"]), name, description, json.dumps(config), int(time.time())),
    )
    agent_id = cur.lastrowid
    conn.commit()
    conn.close()

    agent_dir(user["id"], str(agent_id))
    return {"status": "ok", "agent": {"id": agent_id, "name": name, "config": config}}


@router.get("/list")
def list_agents(authorization: str = Header(None)):
    user = require_auth(authorization)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, description, config, created_at FROM agents WHERE user_id = ?",
        (int(user["id"]),),
    )
    rows = cur.fetchall()
    conn.close()

    agents = []
    for r in rows:
        try:
            cfg = json.loads(r[3]) if r[3] else {}
        except:
            cfg = {}
        agents.append({
            "id": r[0],
            "name": r[1],
            "description": r[2],
            "config": cfg,
            "created_at": r[4],
        })
    return {"agents": agents}

# -------------------------------------------------
# Upload Documents (with chunking strategy)
# -------------------------------------------------

@router.post("/{agent_id}/upload")
async def upload_files_to_agent(
    agent_id: int,
    request: Request,
    authorization: str = Header(None),
):
    user = require_auth(authorization)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT config FROM agents WHERE id = ? AND user_id = ?",
        (agent_id, int(user["id"])),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Agent not found")

    try:
        cfg = json.loads(row[0]) if row[0] else {}
    except:
        cfg = {}

    strategy = cfg.get("chunk_strategy", "fixed")
    chunk_size = int(cfg.get("chunk_size", 800))
    overlap = int(cfg.get("overlap", 200))

    body = await request.json()
    file_ids = body.get("fileIds", [])
    if not file_ids:
        raise HTTPException(400, "fileIds required")

    service = build_drive_service_from_creds(decrypt_json(user["creds"]))
    a_dir = agent_dir(user["id"], str(agent_id))
    docs_dir = a_dir / "docs"
    docs_dir.mkdir(exist_ok=True)

    uploaded = []

    from googleapiclient.http import MediaIoBaseDownload

    for fid in file_ids:
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, service.files().get_media(fileId=fid))
        done = False
        while not done:
            _, done = downloader.next_chunk()

        content = fh.getvalue()
        meta = service.files().get(fileId=fid, fields="name,mimeType").execute()
        fname = meta.get("name") or fid

        fpath = docs_dir / f"{fid}-{fname}"
        fpath.write_bytes(content)

        text = extract_text_from_bytes(content, fname, meta.get("mimeType", ""))
        chunks = chunk_text_strategy(text, strategy, chunk_size, overlap)

        added = build_and_save_index_to_dir(
            user["id"],
            "\n".join(chunks),
            a_dir,
            doc_id=f"{agent_id}:{fid}",
            filename=fname,
        )

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO agent_docs (agent_id, file_id, filename, saved_path, added_at) VALUES (?, ?, ?, ?, ?)",
            (agent_id, fid, fname, str(fpath), int(time.time())),
        )
        conn.commit()
        conn.close()

        uploaded.append({"id": fid, "filename": fname, "chunks_added": added})

    return {"status": "ok", "uploaded": uploaded}

# -------------------------------------------------
# Agent QA (hybrid learning)
# -------------------------------------------------

@router.post("/{agent_id}/qa/generate")
async def agent_generate(
    agent_id: int,
    request: Request,
    authorization: str = Header(None),
    background: BackgroundTasks = None,
):
    user = require_auth(authorization)
    body = await request.json()
    query = body.get("query")
    if not query:
        raise HTTPException(400, "query required")

    k = int(body.get("k", 5))
    max_new_tokens = min(int(body.get("max_new_tokens", 128)), 256)

    a_dir = agent_dir(user["id"], str(agent_id))
    vectors, meta = load_index_from_dir(a_dir)

    q_vec = EMBED_MODEL.encode(query, convert_to_numpy=True, normalize_embeddings=True)
    sims = np.dot(vectors, q_vec)
    idx = sims.argsort()[::-1][:k]

    ctx = []
    sim_vals = []
    for i in idx:
        sim_vals.append(float(sims[i]))
        ctx.append(meta[i])

    avg_sim = sum(sim_vals) / len(sim_vals) if sim_vals else 0.0

    prompt = f"Context:\n{''.join(c['text'] for c in ctx)}\n\nQuestion: {query}\nAnswer:"
    inputs = GEN_TOKENIZER(prompt, return_tensors="pt", truncation=True)
    outputs = GEN_MODEL.generate(**inputs, max_new_tokens=max_new_tokens)
    answer = GEN_TOKENIZER.decode(outputs[0], skip_special_tokens=True)

    # hybrid retrain
    if avg_sim < AUTO_RETRAIN_THRESHOLD and background:
        background.add_task(retrain_agent, user["id"], agent_id, query, ctx, None)

    # save history
    hist_path = agent_history_path(user["id"], str(agent_id))
    try:
        history = json.loads(hist_path.read_text()) if hist_path.exists() else []
    except:
        history = []

    ts = int(time.time())
    history.extend([
        {"role": "user", "text": query, "ts": ts},
        {"role": "assistant", "text": answer, "ts": ts + 1, "avg_sim": avg_sim},
    ])
    hist_path.write_text(json.dumps(history, indent=2))

    return {"answer": answer, "avg_sim": avg_sim, "history": history}

# -------------------------------------------------
# Feedback (👍 / 👎)
# -------------------------------------------------

@router.post("/{agent_id}/feedback")
async def agent_feedback(
    agent_id: int,
    request: Request,
    authorization: str = Header(None),
    background: BackgroundTasks = None,
):
    user = require_auth(authorization)
    body = await request.json()

    correct = bool(body.get("correct"))
    query = body.get("query")
    better = body.get("better_answer")

    if not query:
        raise HTTPException(400, "query required")

    if not correct and better:
        background.add_task(retrain_agent, user["id"], agent_id, query, None, better)
        return {"status": "ok", "retrain": "scheduled"}

    if correct:
        synthetic = f"Q: {query}\nA: {body.get('answer','')}"
        build_and_save_index_to_dir(
            user["id"],
            synthetic,
            agent_dir(user["id"], str(agent_id)),
            doc_id=f"reinforce:{int(time.time())}",
            filename="__reinforce__",
        )
        return {"status": "ok", "reinforced": True}

    return {"status": "ok"}
