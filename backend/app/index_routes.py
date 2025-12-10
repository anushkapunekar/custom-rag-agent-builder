"""
index_routes.py

Extra index management routes:
- /index/reindex  → rebuild entire collection
- /index/status   → show number of chunks indexed
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from chromadb import PersistentClient

from .auth import decode_token
from .indexer import reindex_user
from .utils import ensure_user_dir

router = APIRouter(prefix="/index", tags=["index"])
security = HTTPBearer()

# Same Chroma client as indexer & retriever
chroma = PersistentClient(path="data/chroma")


# -----------------------------
# GET /index/status
# -----------------------------
@router.get("/status")
def index_status(token=Depends(security)):
    payload = decode_token(token.credentials)
    user_id = payload.get("sub")

    collection_name = f"user_{user_id}"

    try:
        collection = chroma.get_collection(collection_name)
    except:
        return {"chunks": 0, "message": "No index found"}

    count = collection.count()
    return {"chunks": count}


# -----------------------------
# POST /index/reindex
# -----------------------------
@router.post("/reindex")
def rebuild_index(token=Depends(security)):
    payload = decode_token(token.credentials)
    user_id = payload.get("sub")

    result = reindex_user(user_id)
    return {"message": "Reindex completed", "stats": result}
