// ---------------------------
// Backend Base URL
// ---------------------------
const BACKEND = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";


// ---------------------------
// AUTH
// ---------------------------
export function authGoogleLoginUrl() {
  return `${BACKEND}/auth/google/login`;
}


// ---------------------------
// DRIVE
// ---------------------------
export async function listDocs(token) {
  const res = await fetch(`${BACKEND}/drive/list_docs`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to list docs");
  return res.json();
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

  if (!res.ok) throw new Error(await res.text());
  return res.json();
}


// ---------------------------
// GLOBAL RAG (main chatbot)
// ---------------------------
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

export async function generateAnswer(query, token, k = 5, max_new_tokens = 200, agentId = null) {
  const res = await fetch(`${BACKEND}/qa/generate`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query,
      k,
      max_new_tokens,
      docId: agentId
    }),
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

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

  if (!res.ok) throw new Error(await res.text());
  return res.json();
}


// ---------------------------
// AGENTS SYSTEM
// ---------------------------

// Create agent
export async function createAgent(payload, token) {
  const res = await fetch(`${BACKEND}/agents/create`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// List agents
export async function listAgents(token) {
  const res = await fetch(`${BACKEND}/agents/list`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Get agent (metadata + documents)
export async function getAgent(agentId, token) {
  const res = await fetch(`${BACKEND}/agents/${agentId}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Upload docs to agent
export async function uploadFilesToAgent(agentId, fileIds, token) {
  const res = await fetch(`${BACKEND}/agents/${agentId}/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ fileIds }),
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Optional helper (not used but kept clean)
export async function listAgentDocs(agentId, token) {
  const res = await fetch(`${BACKEND}/agents/${agentId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.agent_docs || [];
}

// Fetch agent docs
export async function getAgentDocs(agentId, token) {
  const res = await fetch(`${BACKEND}/agents/${agentId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Delete a doc from agent
export async function deleteAgentDoc(agentId, fileId, token) {
  const res = await fetch(`${BACKEND}/agents/${agentId}/docs/${fileId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---------------------------
// Agent Chat History (fixed)
// ---------------------------
export async function getAgentHistory(agentId, token) {
  const res = await fetch(`${BACKEND}/agents/${agentId}/history`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function saveAgentHistory(agentId, messages, token) {
  const res = await fetch(`${BACKEND}/agents/${agentId}/history`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      action: "replace",
      messages,
    }),
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json();
}


// Update agent settings (chunking etc)
export async function updateAgent(agentId, payload, token) {
  const res = await fetch(`${BACKEND}/agents/${agentId}`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Reindex agent
export async function reindexAgent(agentId, token) {
  const res = await fetch(`${BACKEND}/agents/${agentId}/reindex`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}


// Delete agent
export async function deleteAgent(agentId, token) {
  const res = await fetch(`${BACKEND}/agents/${agentId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
