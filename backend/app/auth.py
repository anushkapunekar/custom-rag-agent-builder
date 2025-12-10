# ---------------- GOOGLE OAUTH LOGIN + CALLBACK (FINAL VERSION) ----------------

import os, json, sqlite3
from urllib.parse import urlencode
from datetime import timedelta, datetime
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from jose import jwt

from .utils import encrypt_json, decrypt_json, ensure_user_dir

router = APIRouter(prefix="/auth", tags=["auth"])

# -------------------------
# CONFIG
# -------------------------
APP_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = APP_DIR / "credentials" / "credentials.json"
DB_PATH = APP_DIR / "users.db"

SECRET_KEY = "supersecret"  # change in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days

# Ensure no trailing slash to avoid // in redirect
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

REDIRECT_URI = "http://localhost:8000/auth/google/callback"

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.readonly",
]


# -------------------------
# INIT SQLITE
# -------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            name TEXT,
            creds TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


# -------------------------
# JWT HELPERS
# -------------------------
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Required by index_routes, drive.py, retriever.py."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# -------------------------
# Get user from DB
# -------------------------
def get_user_by_id(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, email, name, creds FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": str(row[0]),
        "email": row[1],
        "name": row[2],
        "creds": row[3],
    }


# -------------------------
# GOOGLE LOGIN
# -------------------------
@router.get("/google/login")
def google_login():
    if not CREDENTIALS_PATH.exists():
        raise HTTPException(500, "Missing credentials.json inside app/credentials/")

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(
        str(CREDENTIALS_PATH),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    # offline access is REQUIRED for refresh_token
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true"
    )

    return RedirectResponse(auth_url)


# -------------------------
# GOOGLE CALLBACK
# -------------------------
@router.get("/google/callback")
def google_callback(request: Request):

    params = dict(request.query_params)
    code = params.get("code")

    if not code:
        raise HTTPException(400, "Missing authorization code from Google")

    # -------------------------
    # READ Google client secrets
    # -------------------------
    data = json.loads(CREDENTIALS_PATH.read_text())
    client_info = data.get("web") or data.get("installed")

    client_id = client_info["client_id"]
    client_secret = client_info["client_secret"]
    token_uri = client_info.get("token_uri", "https://oauth2.googleapis.com/token")

    # -------------------------
    # EXCHANGE CODE FOR TOKENS
    # -------------------------
    token_res = requests.post(
        token_uri,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=10
    )

    tj = token_res.json()
    if "access_token" not in tj:
        return JSONResponse({"google_error": tj}, status_code=400)

    access_token = tj["access_token"]
    refresh_token = tj.get("refresh_token")
    id_token = tj.get("id_token")

    # -------------------------
    # GET USERINFO
    # -------------------------
    ui = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

    email = ui.get("email")
    name = ui.get("name") or email

    if not email:
        raise HTTPException(400, "Google did not return an email")

    # -------------------------
    # STORE CREDENTIALS
    # -------------------------
    stored = {
        "token": access_token,
        "refresh_token": refresh_token,
        "token_uri": token_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES,
        "id_token": id_token
    }

    encrypted = encrypt_json(stored)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email=?", (email,))
    row = cur.fetchone()

    if row:
        user_id = row[0]
        cur.execute(
            "UPDATE users SET name=?, creds=? WHERE id=?",
            (name, encrypted, user_id)
        )
    else:
        cur.execute(
            "INSERT INTO users(email, name, creds) VALUES (?, ?, ?)",
            (email, name, encrypted)
        )
        user_id = cur.lastrowid

    conn.commit()
    conn.close()

    ensure_user_dir(str(user_id))

    # -------------------------
    # CREATE JWT FOR FRONTEND
    # -------------------------
    jwt_token = create_access_token({"sub": str(user_id), "email": email})

    # -------------------------
    # BUILD FRONTEND REDIRECT URL WITH TOKENS
    # -------------------------
    frag = urlencode({
        "jwt": jwt_token,
        "g_access_token": access_token,
        "g_refresh_token": refresh_token or ""
    })

    FE = FRONTEND_URL.rstrip("/")
    redirect_url = f"{FE}/#{frag}"

    # -------------------------
    # FINAL FIX → HTML REDIRECT (NO 307 LOOP)
    # -------------------------
    html = f"""
    <html>
        <head><meta http-equiv="refresh" content="0; url={redirect_url}" /></head>
        <body>
            Redirecting...
            <script>
                window.location.href = "{redirect_url}";
            </script>
        </body>
    </html>
    """

    return HTMLResponse(content=html)