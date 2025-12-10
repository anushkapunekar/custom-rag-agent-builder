"""
indexer.py

Handles:
- Extracting text from files
- Chunking
- Embeddings
- Storing chunks in Chroma (PersistentClient)
"""

from pathlib import Path
import docx
import pdfminer.high_level as pdf_reader
from sentence_transformers import SentenceTransformer

# New Chroma API (2025)
from chromadb import PersistentClient

from .utils import ensure_user_dir

# --------------------------
# CONFIG
# --------------------------
EMB_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

embedder = SentenceTransformer(EMB_MODEL_NAME)

# Global persistent Chroma client
chroma_client = PersistentClient(path="data/chroma")


# -----------------------------------------------------------
# TEXT EXTRACTORS
# -----------------------------------------------------------
def extract_text(file_path: Path) -> str:
    """
    Extract text depending on file type.
    """

    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        try:
            return pdf_reader.extract_text(str(file_path))
        except Exception:
            return ""

    if suffix == ".docx":
        try:
            doc = docx.Document(str(file_path))
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception:
            return ""

    # Fallback for txt, md, etc.
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception:
        return ""


# -----------------------------------------------------------
# CHUNKING
# -----------------------------------------------------------
def chunk_text(text: str, chunk_size=800, overlap=100):
    """
    Splits text into overlapping word chunks.
    """
    if not text:
        return []

    words = text.split()
    chunks = []

    start = 0
    while start < len(words):
        chunk = words[start : start + chunk_size]
        chunks.append(" ".join(chunk))
        start += chunk_size - overlap

    return chunks


# -----------------------------------------------------------
# INDEX A SINGLE FILE
# -----------------------------------------------------------
def index_user_file(user_id: str, local_path: str, file_id: str, file_name: str):
    """
    Reads file → extracts text → chunks → embeds → stores in Chroma.
    """

    path = Path(local_path)
    text = extract_text(path)
    chunks = chunk_text(text)

    if not chunks:
        return 0  # nothing to index

    # Create/fetch collection for user
    coll_name = f"user_{user_id}"
    collection = chroma_client.get_or_create_collection(name=coll_name)

    # Create metadata list for each chunk
    metadatas = [{"source": file_name, "file_id": file_id} for _ in chunks]

    # Each chunk needs unique ID
    ids = [f"{file_id}_{i}" for i in range(len(chunks))]

    # Embed
    embeddings = embedder.encode(chunks, convert_to_numpy=True).tolist()

    # Add to vector DB
    collection.add(
        documents=chunks,
        metadatas=metadatas,
        ids=ids,
        embeddings=embeddings
    )

    return len(chunks)


# -----------------------------------------------------------
# RE-INDEX ALL FILES FOR A USER
# -----------------------------------------------------------
def reindex_user(user_id: str):
    """
    Deletes collection and rebuilds it from scratch.
    """

    coll_name = f"user_{user_id}"

    # Delete existing collection if exists
    try:
        chroma_client.delete_collection(coll_name)
    except:
        pass

    # Create new collection
    chroma_client.get_or_create_collection(coll_name)

    # Get user directory
    user_dir = ensure_user_dir(user_id)
    files_dir = user_dir / "files"

    total_chunks = 0

    for file in files_dir.iterdir():
        file_id = file.name
        file_name = file.name

        total_chunks += index_user_file(
            user_id=user_id,
            local_path=str(file),
            file_id=file_id,
            file_name=file_name
        )

    return {"indexed_chunks": total_chunks}
