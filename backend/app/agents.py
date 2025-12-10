# backend/app/agents.py
import json
import sqlite3
import time
import io
from googleapiclient.http import MediaIoBaseDownload

from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import JSONResponse

from .auth import decode_token, get_user_by_id
from .utils import ensure_user_dir, decrypt_json
from .rag_utils import build_and_save_index  # we already have this signature (user_id, full_text, doc_id=None, filename=None)
from .drive import build_drive_service_from_creds, extract_text_from_bytes

router = APIRouter(prefix="/agents", tags=["agents"])

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "users.db"  # same DB used by auth
STORAGE_BASE = APP_DIR / "storage"
STORAGE_BASE.mkdir(exist_ok=True, parents=True)

# ---------------------------
# DB init for agents
# ---------------------------
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

# ---------------------------
# Helpers
# ---------------------------
def require_auth(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(404, "User not found")
    return user

def agent_storage_for(user_id: str, agent_id: str) -> Path:
    p = STORAGE_BASE / str(user_id) / "agents" / str(agent_id)
    p.mkdir(parents=True, exist_ok=True)
    return p

# ---------------------------
# Create agent
# ---------------------------
@router.post("/create")
async def create_agent(request: Request, authorization: str = Header(None)):
    user = require_auth(authorization)

    try:
        body = await request.json()
    except:
        body = {}

    name = (body.get("name") or "").strip()
    description = body.get("description", "").strip()
    config = body.get("config", {})  # chunk size, overlap, other prefs

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

    # create storage folder
    agent_storage_for(user["id"], str(agent_id))

    return {"status": "ok", "agent": {"id": agent_id, "name": name, "description": description, "config": config}}

# ---------------------------
# List agents for user
# ---------------------------
@router.get("/list")
def list_agents(authorization: str = Header(None)):
    user = require_auth(authorization)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, config, created_at FROM agents WHERE user_id = ? ORDER BY created_at DESC", (int(user["id"]),))
    rows = cur.fetchall()
    conn.close()

    agents = []
    for r in rows:
        cfg = {}
        try:
            cfg = json.loads(r[3]) if r[3] else {}
        except:
            cfg = {}
        agents.append({
            "id": r[0],
            "name": r[1],
            "description": r[2],
            "config": cfg,
            "created_at": r[4]
        })

    return {"agents": agents}

# ---------------------------
# Get single agent meta
# ---------------------------
@router.get("/{agent_id}")
def get_agent(agent_id: int, authorization: str = Header(None)):
    user = require_auth(authorization)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, config, created_at FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Agent not found")
    cfg = {}
    try:
        cfg = json.loads(row[3]) if row[3] else {}
    except:
        cfg = {}
    return {"agent": {"id": row[0], "name": row[1], "description": row[2], "config": cfg, "created_at": row[4]}}

# ---------------------------
# Delete agent (clear storage + DB rows)
# ---------------------------
@router.delete("/{agent_id}")
def delete_agent(agent_id: int, authorization: str = Header(None)):
    user = require_auth(authorization)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Agent not found")

    # delete agent rows
    cur.execute("DELETE FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    cur.execute("DELETE FROM agent_docs WHERE agent_id = ?", (agent_id,))
    conn.commit()
    conn.close()

    # remove files on disk if exist
    p = STORAGE_BASE / str(user["id"]) / "agents" / str(agent_id)
    try:
        if p.exists():
            # remove tree carefully
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
    except Exception as e:
        # ignore disk delete problems
        print("Warning: failed to remove agent storage:", e)

    return {"status": "ok", "deleted_agent": agent_id}

# ---------------------------
# Upload documents for agent (drive fileIds)
# ---------------------------

@router.post("/{agent_id}/upload")
async def upload_files_to_agent(agent_id: int, request: Request, authorization: str = Header(None)):
    """
    Body: { "fileIds": ["id1","id2"...] }
    This downloads files using the user's saved Google creds, extracts text,
    but indexes into the agent-specific index (stored under storage/<user>/agents/<agent_id>).
    """
    user = require_auth(authorization)

    # check agent belongs to user
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, config FROM agents WHERE id = ? AND user_id = ?", (agent_id, int(user["id"])))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Agent not found")
    agent_cfg = {}
    try:
        agent_cfg = json.loads(row[1]) if row[1] else {}
    except:
        agent_cfg = {}
    conn.close()

    try:
        body = await request.json()
    except:
        raw = await request.body()
        body = json.loads(raw.decode()) if raw else {}

    file_ids = body.get("fileIds", [])
    if not isinstance(file_ids, list) or not file_ids:
        raise HTTPException(400, "fileIds must be a non-empty list")

    # load user's google creds (from users table)
    # reusing auth.get_user_by_id flow: user["creds"] is encrypted
    gcreds = decrypt_json(user["creds"])
    service = build_drive_service_from_creds(gcreds)

    user_agents_dir = agent_storage_for(user["id"], str(agent_id))
    docs_dir = user_agents_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    combined_text = ""
    # iterate
    for fid in file_ids:
        req = service.files().get_media(fileId=fid)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        content = fh.getvalue()
        meta = service.files().get(fileId=fid, fields="id,name,mimeType").execute()
        fname = meta.get("name") or f"{fid}"
        mime = meta.get("mimeType", "")

        safe_name = f"{fid}-{fname}"
        fpath = docs_dir / safe_name
        fpath.write_bytes(content)

        # extract using same util from drive module
        extracted = extract_text_from_bytes(content, fname, mime)
        # index: pass doc_id as "<agent_id>:<fid>" so meta stores doc ownership
        doc_id_tag = f"{agent_id}:{fid}"
        # call rag_utils to append into agent-specific index area
        # Note: build_and_save_index stores into storage/<user_id>/...; we will
        # create a symlink-like behavior: copy extracted text into agent dir and call with doc_id
        # But rag_utils stores in APP_DIR/storage/<user_id> -- to isolate, we'll change working dir temporarily.
        # Simpler: write extracted text file and call build_and_save_index which appends into global user index.
        # To keep agent-specific index separate we will store meta with docId tag; loader will filter by docId.
        # Call build_and_save_index with doc_id and filename
        try:
            added_chunks = build_and_save_index(user["id"], extracted, doc_id=doc_id_tag, filename=fname)
        except Exception as e:
            raise HTTPException(500, f"Failed to index file {fname}: {e}")

        # record in agent_docs table
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO agent_docs (agent_id, file_id, filename, saved_path, added_at) VALUES (?, ?, ?, ?, ?)",
            (agent_id, fid, fname, str(fpath), int(time.time()))
        )
        conn.commit()
        conn.close()

        uploaded.append({"id": fid, "filename": fname, "chunks_added": added_chunks})

    return JSONResponse({"status": "ok", "uploaded": uploaded})
