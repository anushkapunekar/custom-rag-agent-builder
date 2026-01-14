#  Custom RAG System with Multi-Agent Support

This project is a **from-scratch Retrieval-Augmented Generation (RAG) system** built using **FastAPI + React**, designed to help users chat with their own documents and create independent AI agents, each with its own knowledge base and memory.

The system runs **fully locally** (no vector DB yet) and stores embeddings, documents, and chat history on disk.

---

### What This Project Does

#### 1. Custom RAG (Main Chat)
* Upload documents from **Google Drive**
* Extract text from **PDF / DOCX / PPTX**
* **Chunk and embed** documents
* Ask questions and get answers **strictly from your documents**
* Chat history is saved per user

#### 2. Multi-Agent System
* Create multiple agents
* Each agent has:
    * Its own documents
    * Its own embeddings
    * Its own chat history
* **Agents do not share memory** with each other
* Agents can be trained incrementally using feedback

#### 3. Self-Improving Agents (Hybrid Learning)
Agents can improve over time using:
* 👍 **Positive feedback** (reinforces correct answers)
* 👎 **Negative feedback** (optionally with a better answer)
* **Automatic retraining** when retrieval quality is low

> **Note:** This is retrieval-level learning, not model fine-tuning.

---

###  Architecture Overview



```text
Frontend (React)
   |
   |  REST API
   v
Backend (FastAPI)
   |
   |-- Document ingestion (Google Drive)
   |-- Chunking + embeddings (SentenceTransformers)
   |-- Retrieval (cosine similarity)
   |-- Answer generation (FLAN-T5)
   |
   └── Local Storage (Disk)
```

---

 Storage Structure (Very Important)
This project does NOT use a vector database yet. All data is stored locally on disk:

Plaintext

backend/app/storage/
└── <user_id>/
    ├── embeddings.npy        # main RAG vectors
    ├── meta.json             # main RAG metadata
    ├── docs/                 # uploaded files
    │
    └── agents/
        └── <agent_id>/
            ├── embeddings.npy
            ├── meta.json
            ├── docs/
            │   └── <fileid>-filename.pdf
* Agent chat history is stored separately: backend/app/data/users/<user_id>/agents/<agent_id>/chat_history.json

* Everything persists across refreshes and restarts.

---

 Chunking Strategies (Per Agent)
Each agent can define its own chunking behavior:

JSON

{
  "chunk_strategy": "fixed | sentences | smart",
  "chunk_size": 800,
  "overlap": 200
}
These settings are stored in the agent config (SQLite), applied during document upload, and reused during retraining / reindexing.

---

💬 Feedback & Learning
Agents support feedback via thumbs:

👍 Correct answer: Reinforces knowledge by adding a synthetic Q/A document.

👎 Wrong answer: Optionally provide a better answer; triggers background retraining.

Additionally, if average similarity during retrieval is too low, the agent auto-reindexes in the background. This is safe, explainable learning, not black-box fine-tuning.

---

 Tech Stack
 **Backend**:

* FastAPI

* SentenceTransformers (all-MiniLM-L6-v2)

* Transformers (google/flan-t5-base)

* SQLite (agents & metadata)

* Google Drive API

* NumPy

**Frontend**:

* React (Vite)

* Custom UI for Chat, Agents, Uploads, and Feedback

* Authentication

* Google OAuth

* JWT-based backend authentication

* ❌ What This Project Does NOT Use (Yet)
  
* ❌ Vector databases (Chroma, Pinecone, FAISS, etc.)

* ❌ Cloud inference

* ❌ Model fine-tuning

* ❌ Paid APIs (besides optional Google Drive)

Everything runs locally.

---

 Future Improvements (Planned):

* Replace file-based storage with ChromaDB

* Agent settings UI (edit agent config)

* Better document preview

* Streaming responses

* Optional cloud deployment
  
