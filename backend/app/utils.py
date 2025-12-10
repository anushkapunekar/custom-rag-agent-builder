import os
import json
from pathlib import Path
from cryptography.fernet import Fernet

# -----------------------------
# Encryption Key (Auto-created)
# -----------------------------

KEY_PATH = Path("app/.secret_key")

# Generate key if not exists
if not KEY_PATH.exists():
    KEY_PATH.write_bytes(Fernet.generate_key())

fernet = Fernet(KEY_PATH.read_bytes())


# -----------------------------
# Encrypt / Decrypt JSON
# -----------------------------

def encrypt_json(obj: dict) -> str:
    """Encrypt dict to string"""
    raw = json.dumps(obj).encode("utf-8")
    return fernet.encrypt(raw).decode("utf-8")


def decrypt_json(token_str: str) -> dict:
    """Decrypt string back to dict"""
    raw = fernet.decrypt(token_str.encode("utf-8"))
    return json.loads(raw.decode("utf-8"))


# -----------------------------
# Create user directories safely
# -----------------------------

def ensure_user_dir(user_id: str) -> Path:
    """
    Creates directories:
      data/users/<user_id>/
      data/users/<user_id>/files/
      data/users/<user_id>/chroma_db/
    """
    base = Path("data/users") / str(user_id)
    base.mkdir(parents=True, exist_ok=True)

    (base / "files").mkdir(exist_ok=True)
    (base / "chroma_db").mkdir(exist_ok=True)

    return base
