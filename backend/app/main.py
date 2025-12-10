# backend/app/main.py
import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
print("OAUTHLIB FLAG =", os.environ.get("OAUTHLIB_INSECURE_TRANSPORT"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .index_routes import router as index_router
from .auth import router as auth_router
from .drive import router as drive_router
from .retriever import router as qa_router
from .maintenance import router as maintenance_router
from .agents import router as agents_router

try:
    from .chat_history import router as chat_router
except Exception as e:
    chat_router = None
    print("WARNING: chat_history import failed:", e)

app = FastAPI(title="Custom RAG Backend")

# Allow frontend (localhost:5173) to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # OR ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REGISTER ROUTERS
app.include_router(auth_router)
app.include_router(drive_router)
app.include_router(qa_router)
app.include_router(index_router)
app.include_router(maintenance_router)
# Only include chat router if import succeeded
if chat_router:
    app.include_router(chat_router)

if agents_router:
    app.include_router(agents_router)    

@app.get("/")
def root():
    return {"message": "Custom RAG backend running"}
