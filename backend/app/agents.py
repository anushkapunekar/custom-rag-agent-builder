# backend/app/agents.py
import io
import json
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from .auth import decode_token, get_user_by_id
from .utils import ensure_user_dir, decrypt_json
from .rag_utils import (
    build_and_save_index_to_dir,
    load_index_from_dir,
    chunk_text_strategy   # NEW
)

from .drive import build_drive_service_from_creds, extract_text_from_bytes

from sentence_transformers import SentenceTransformer
import numpy as np
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

router = APIRouter(prefix="/agents", tags=["agents"])

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "users.db"
STORAGE_BASE = APP_DIR / "storage"
STORAGE_BASE.mkdir(exist_ok=True, parents=True)

# models for on-the-fly generation in agent endpoint
EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
GEN_MODEL_NAME = "google/flan-t5-base"
GEN_TOKENIZER = AutoTokenizer.from_pretrained(GEN_MODEL_NAME)
GEN_MODEL = AutoModelForSeq2SeqLM.from_pretrained(GEN_MODEL_NAME)


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


@router.post("/create")
async def create_agent(request: Request, authorization: str = Header(None)):
    user = require_auth(authorization)

    try:
        body = await request.json()
    except:
        body = {}

    name = (body.get("name") or "").strip()
    description = body.get("description", "").strip()
    config = body.get("config", {})

    if not name:
        raise HTTPException(400, "Agent name is required")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        "INSERT INTO agents (user_id, name, description, config, created_at) VALUES (?, ?, ?, ?, ?)",
        (int(user["id"]), name, description, json.dumps(config, ensure_ascii=False), now)
    )
    agent_id = cur.lastrowid
    conn.commit()
    conn.close()

    # create storage dir
    agent_dir(user["id"], str(agent_id))
    return {"status": "ok", "agent": {"id": agent_id, "name": name, "description": description, "config": config}}


@router.get("/list")
def list_agents(authorization: str = Header(None)):
    user = require_auth(authorization)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, config, created_at FROM agents WHERE user_id = ? ORDER BY created_at DESC", (int(user["id"]),))
    rows = cur.fetchall()
    conn.close()
    out = []
    for r in rows:
        cfg = {}
        try:
            cfg = json.loads(r[3]) if r[3] else {}
        except:
            cfg = {}
        out.append({
            "id": r[0],
            "name": r[1],
            "description": r[2],
            "config": cfg,
            "created_at": r[4]
        })
    return {"agents": out}


@router.get("/{agent_id}")
def get_agent(agent_id: int, authorization: str = Header(None)):
    user = require_auth(authorization)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, config, created_at FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Agent not found")

    # fetch agent docs
    cur.execute("SELECT id, file_id, filename, saved_path, added_at FROM agent_docs WHERE agent_id = ? ORDER BY added_at DESC", (agent_id,))
    docs_rows = cur.fetchall()
    conn.close()

    cfg = {}
    try:
        cfg = json.loads(row[3]) if row[3] else {}
    except:
        cfg = {}

    agent_docs = []
    for r in docs_rows:
        agent_docs.append({
            "id": r[0],
            "file_id": r[1],
            "filename": r[2],
            "saved_path": r[3],
            "added_at": r[4]
        })

    return {"agent": {"id": row[0], "name": row[1], "description": row[2], "config": cfg, "created_at": row[4]}, "agent_docs": agent_docs}


@router.post("/{agent_id}/history")
async def post_agent_history(agent_id: int, request: Request, authorization: str = Header(None)):
    user = require_auth(authorization)

    body = await request.json()
    msgs = body.get("messages", [])
    action = body.get("action", "append")

    history_dir = APP_DIR / "data" / "users" / str(user["id"]) / "agents" / str(agent_id)
    history_dir.mkdir(parents=True, exist_ok=True)

    hist_path = history_dir / "chat_history.json"

    if hist_path.exists():
        try:
            prev = json.loads(hist_path.read_text(encoding="utf-8", errors="ignore"))
        except:
            prev = []
    else:
        prev = []

    if action == "replace":
        new_hist = msgs
    else:
        new_hist = prev + msgs

    hist_path.write_text(json.dumps(new_hist, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"history": new_hist}

@router.get("/{agent_id}/history")
async def get_agent_history(agent_id: int, authorization: str = Header(None)):
    user = require_auth(authorization)

    history_dir = APP_DIR / "data" / "users" / str(user["id"]) / "agents" / str(agent_id)
    hist_path = history_dir / "chat_history.json"

    if not hist_path.exists():
        return {"history": []}

    try:
        data = json.loads(hist_path.read_text(encoding="utf-8", errors="ignore"))
    except:
        data = []

    return {"history": data}


@router.delete("/{agent_id}")
def delete_agent(agent_id: int, authorization: str = Header(None)):
    user = require_auth(authorization)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Agent not found")
    cur.execute("DELETE FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    cur.execute("DELETE FROM agent_docs WHERE agent_id = ?", (agent_id,))
    conn.commit()
    conn.close()

    p = agent_dir(user["id"], str(agent_id))
    try:
        # remove files (best-effort)
        for child in p.rglob("*"):
            if child.is_file():
                child.unlink()
        for child in sorted(p.rglob("*"), reverse=True):
            if child.is_dir():
                try:
                    child.rmdir()
                except:
                    pass
        try:
            p.rmdir()
        except:
            pass
    except Exception:
        pass

    return {"status": "ok", "deleted_agent": agent_id}

@router.put("/{agent_id}/update")
async def update_agent(agent_id: int, request: Request, authorization: str = Header(None)):
    user = require_auth(authorization)

    body = await request.json()
    name = body.get("name")
    description = body.get("description")
    config = body.get("config")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Verify exists
    cur.execute("SELECT id FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Agent not found")

    # Update
    cur.execute("""
        UPDATE agents SET
        name = COALESCE(?, name),
        description = COALESCE(?, description),
        config = COALESCE(?, config)
        WHERE id = ? AND user_id = ?
    """, (name, description, json.dumps(config), agent_id, int(user["id"])))

    conn.commit()
    conn.close()

    return {"status": "ok", "updated": agent_id}


@router.post("/{agent_id}/upload")
async def upload_files_to_agent(agent_id: int, request: Request, authorization: str = Header(None)):
    """
    Body: { fileIds: [...] }
    Downloads from Google Drive and indexes into:
    storage/<user_id>/agents/<agent_id>/
    """
    user = require_auth(authorization)

    # verify agent
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT config FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, "Agent not found")

    # load agent config (chunk settings)
    try:
        agent_cfg = json.loads(row[0]) if row[0] else {}
    except:
        agent_cfg = {}

    strategy = agent_cfg.get("chunk_strategy", "fixed")
    chunk_size = int(agent_cfg.get("chunk_size", 800))
    overlap = int(agent_cfg.get("overlap", 200))

    # get body
    try:
        body = await request.json()
    except:
        raw = await request.body()
        body = json.loads(raw.decode()) if raw else {}

    file_ids = body.get("fileIds", [])
    if not isinstance(file_ids, list) or not file_ids:
        raise HTTPException(400, "fileIds must be a non-empty list")

    # build Google Drive client
    gcreds = decrypt_json(user["creds"])
    service = build_drive_service_from_creds(gcreds)

    # dirs
    a_dir = agent_dir(user["id"], str(agent_id))
    docs_dir = a_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []

    for fid in file_ids:
        # download the file
        req = service.files().get_media(fileId=fid)
        from googleapiclient.http import MediaIoBaseDownload

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        content = fh.getvalue()

        # metadata
        meta = service.files().get(fileId=fid, fields="id,name,mimeType").execute()
        fname = meta.get("name") or f"{fid}"
        mime = meta.get("mimeType", "")

        # save file locally
        safe_name = f"{fid}-{fname}"
        fpath = docs_dir / safe_name
        fpath.write_bytes(content)

        # extract text
        extracted = extract_text_from_bytes(content, fname, mime)

        # ---- APPLY CHUNKING STRATEGY ----
        chunks = chunk_text_strategy(extracted, strategy, chunk_size, overlap)

        # ---- INDEX INTO AGENT DIRECTORY ----
        try:
            added = build_and_save_index_to_dir(
                user["id"],
                "\n".join(chunks),
                a_dir,
                f"{agent_id}:{fid}",
                fname
            )
        except Exception as e:
            raise HTTPException(500, f"Indexing failed for {fname}: {e}")

        # record DB row
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO agent_docs (agent_id, file_id, filename, saved_path, added_at) VALUES (?, ?, ?, ?, ?)",
            (agent_id, fid, fname, str(fpath), int(time.time()))
        )
        conn.commit()
        conn.close()

        uploaded.append({
            "id": fid,
            "filename": fname,
            "chunks_added": added
        })

    return JSONResponse({"status": "ok", "uploaded": uploaded})

# --------------------
# Agent-specific generate endpoint (loads agent index files)
# --------------------
@router.post("/{agent_id}/qa/generate")
async def agent_generate(agent_id: int, request: Request, authorization: str = Header(None)):
    user = require_auth(authorization)

    # verify agent
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, config FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Agent not found")
    agent_cfg = {}
    try:
        agent_cfg = json.loads(row[2]) if row[2] else {}
    except:
        agent_cfg = {}

    try:
        body = await request.json()
    except:
        body = {}

    query = body.get("query")
    # robust parsing for k and max_new_tokens
    raw_k = body.get("k", 5)
    try:
        k = int(raw_k) if raw_k is not None else 5
    except (ValueError, TypeError):
        k = 5

    raw_mnt = body.get("max_new_tokens", 64)
    try:
        max_new_tokens = int(raw_mnt) if raw_mnt is not None else 64
    except (ValueError, TypeError):
        max_new_tokens = 64
    max_new_tokens = min(max_new_tokens, 256)

    if not query:
        raise HTTPException(400, "Missing query")

    # load agent index
    a_dir = agent_dir(user["id"], str(agent_id))
    try:
        vectors, meta = load_index_from_dir(a_dir)
    except FileNotFoundError:
        raise HTTPException(400, "Agent has no indexed documents yet.")

    # embed query using same EMBED_MODEL
    q_vec = EMBED_MODEL.encode(query, convert_to_numpy=True, normalize_embeddings=True)
    sims = np.dot(vectors, q_vec)
    topk_idx = sims.argsort()[::-1][:k]

    ctx_items = []
    for i in topk_idx:
        ctx_items.append({"score": float(sims[i]), "text": meta[i]["text"], "filename": meta[i].get("filename", ""), "docId": meta[i].get("docId", "")})

    context_text = "\n\n".join([c["text"] for c in ctx_items])

    prompt = f"Context:\n{context_text}\n\nQuestion: {query}\nAnswer using ONLY the context above."

    try:
        inputs = GEN_TOKENIZER(prompt, return_tensors="pt", truncation=True)
        outputs = GEN_MODEL.generate(**inputs, max_new_tokens=max_new_tokens)
        answer = GEN_TOKENIZER.decode(outputs[0], skip_special_tokens=True)
    except Exception as e:
        raise HTTPException(500, f"Model generation error: {e}")

    # save per-agent history file
    history_dir = APP_DIR / "data" / "users" / str(user["id"]) / "agents" / str(agent_id)
    history_dir.mkdir(parents=True, exist_ok=True)
    hist_path = history_dir / "chat_history.json"
    try:
        if hist_path.exists():
            prev = json.loads(hist_path.read_text(encoding="utf-8", errors="ignore"))
        else:
            prev = []
    except:
        prev = []

    import time
    ts = int(time.time())
    prev.append({"role": "user", "text": query, "ts": ts})
    prev.append({"role": "assistant", "text": answer, "ts": ts + 1, "sources": ctx_items})
    hist_path.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"answer": answer, "sources": ctx_items, "history": prev}

# ---------- PATCH agent (update metadata / config) ----------
@router.patch("/{agent_id}")
async def patch_agent(agent_id: int, request: Request, authorization: str = Header(None)):
    user = require_auth(authorization)
    try:
        body = await request.json()
    except:
        body = {}

    name = body.get("name")
    description = body.get("description")
    config = body.get("config")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Agent not found")

    updates = []
    params = []
    if name is not None:
        updates.append("name = ?"); params.append(name)
    if description is not None:
        updates.append("description = ?"); params.append(description)
    if config is not None:
        updates.append("config = ?"); params.append(json.dumps(config, ensure_ascii=False))

    if updates:
        params.append(agent_id)
        cur.execute(f"UPDATE agents SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()

    return {"status": "ok", "agent_id": agent_id}

# ---------- GET agent history ----------
@router.get("/{agent_id}/history")
def get_agent_history(agent_id: int, authorization: str = Header(None)):
    user = require_auth(authorization)
    history_dir = APP_DIR / "data" / "users" / str(user["id"]) / "agents" / str(agent_id)
    hist_path = history_dir / "chat_history.json"
    if not hist_path.exists():
        return {"history": []}
    try:
        data = json.loads(hist_path.read_text(encoding="utf-8", errors="ignore"))
    except:
        data = []
    return {"history": data}

# ---------- Reindex / retrain agent (background) ----------
@router.post("/{agent_id}/reindex")
def reindex_agent_background(agent_id: int, background_tasks: BackgroundTasks, authorization: str = Header(None)):
    user = require_auth(authorization)

    # verify agent exists
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT config FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Agent not found")

    def _do_reindex():
        try:
            # clear existing agent index files
            a_dir = agent_dir(user["id"], str(agent_id))
            emb = a_dir / "embeddings.npy"
            meta = a_dir / "meta.json"
            if emb.exists():
                try:
                    emb.unlink()
                except:
                    pass
            if meta.exists():
                try:
                    meta.unlink()
                except:
                    pass

            # iterate saved docs and re-run indexing using stored config
            conn2 = sqlite3.connect(DB_PATH)
            cur2 = conn2.cursor()
            cur2.execute("SELECT file_id, filename, saved_path FROM agent_docs WHERE agent_id = ?", (agent_id,))
            rows = cur2.fetchall()
            conn2.close()

            # read agent config
            cfg = {}
            try:
                cfg = json.loads(row[0]) if row and row[0] else {}
            except:
                cfg = {}
            strategy = cfg.get("chunk_strategy", "fixed")
            chunk_size = int(cfg.get("chunk_size", 800))
            overlap = int(cfg.get("overlap", 200))

            for fid, fname, saved_path in rows:
                # if saved path exists read file bytes and extract
                try:
                    p = Path(saved_path)
                    if p.exists():
                        content = p.read_bytes()
                        text = extract_text_from_bytes(content, fname, "")
                    else:
                        # if no local file, skip
                        continue

                    # create chunks using rag_utils chunk strategy helper
                    chunks = chunk_text_strategy(text, strategy, chunk_size, overlap)
                    # join chunks with newline and write into agent index via helper
                    build_and_save_index_to_dir(user["id"], "\n".join(chunks), agent_dir(user["id"], str(agent_id)), f"{agent_id}:{fid}", fname)

                except Exception as e:
                    print("Reindex: failed for", fname, e)
        except Exception as e:
            print("Reindex failed:", e)

    background_tasks.add_task(_do_reindex)
    return {"status": "ok", "reindex_queued": True}
