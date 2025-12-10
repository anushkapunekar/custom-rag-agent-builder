// src/api/api.js

const BACKEND = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

// ---------------- AUTH ----------------
export function authGoogleLoginUrl() {
  return `${BACKEND}/auth/google/login`;
}

// ---------------- DOCUMENTS ----------------
export async function listDocs(token) {
  const res = await fetch(`${BACKEND}/drive/list_docs`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to list docs");
  return res.json(); // { docs: [...] }
}

export async function downloadFiles(fileIds, token) {
  const res = await fetch(`${BACKEND}/drive/download`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ fileIds }),
  });

  if (!res.ok) {
    const t = await res.text();
    throw new Error(t);
  }
  return res.json();
}

// ---------------- RETRIEVAL ----------------
export async function retrieve(query, token, k = 5, docId = null) {
  const res = await fetch(`${BACKEND}/qa/retrieve`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query, k, docId }),
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---------------- GENERATE ----------------
export async function generateAnswer(query, token, k = 5, docId = null) {
  const res = await fetch(`${BACKEND}/qa/generate`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query, k, docId }),
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json(); // { answer, sources, history }
}

// ---------------- CHAT HISTORY ----------------
export async function getHistory(token) {
  const res = await fetch(`${BACKEND}/qa/history`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) throw new Error("Failed to load history");
  return res.json(); // { history: [...] }
}

export async function saveHistory(messages, token, action = "replace") {
  const res = await fetch(`${BACKEND}/qa/history`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ action, messages }),
  });

  if (!res.ok) throw new Error("Failed to save history");
  return res.json();
}
