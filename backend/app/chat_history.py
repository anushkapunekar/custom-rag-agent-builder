# backend/app/chat_history.py
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from .auth import decode_token, get_user_by_id
from .utils import ensure_user_dir

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/save")
async def save_message(request: Request, authorization: str = Header(None)):
    """
    Body: { "docId": "...", "role": "user|assistant", "text": "..." }
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(404, "User not found")

    body = await request.json()
    doc_id = body.get("docId")
    role = body.get("role", "user")
    text = body.get("text", "")
    if not doc_id or not text:
        raise HTTPException(400, "docId and text required")

    user_dir = ensure_user_dir(user["id"])
    hist_dir = user_dir / "chat_history"
    hist_dir.mkdir(exist_ok=True)
    file_path = hist_dir / f"{doc_id}.json"

    try:
        if file_path.exists():
            data = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
        else:
            data = []
    except:
        data = []

    entry = {"role": role, "text": text}
    data.append(entry)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return JSONResponse({"status":"ok", "saved": entry})


@router.get("/history")
def get_history(docId: str = None, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    user = get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(404, "User not found")
    if not docId:
        raise HTTPException(400, "docId query parameter required")
    user_dir = ensure_user_dir(user["id"])
    hist_dir = user_dir / "chat_history"
    file_path = hist_dir / f"{docId}.json"
    if not file_path.exists():
        return {"history": []}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
    except:
        data = []
    return {"history": data}
