// src/pages/AgentSettingsPage.jsx
import React, { useEffect, useState } from "react";
import EditAgentModal from "../components/EditAgentModal";
import DriveFiles from "../components/DriveFiles";
import {
  getAgent,
  updateAgent,
  reindexAgent,
  deleteAgent,
  getAgentDocs,
  deleteAgentDoc
} from "../api/api";

export default function AgentSettingsPage({ jwt, agentId, onBack }) {
  const [agent, setAgent] = useState(null);
  const [tab, setTab] = useState("general");
  const [openEdit, setOpenEdit] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (agentId) loadAgent();
  }, [agentId]);

  async function loadAgent() {
    try {
      const res = await getAgent(agentId, jwt);
      setAgent(res.agent);
    } catch (e) {
      console.error("Load agent failed", e);
    }
  }

  async function onUpdateAgent(id, payload) {
    await updateAgent(id, payload, jwt);
    await reindexAgent(id, jwt);
    await loadAgent();
  }

  async function handleReindex() {
    setLoading(true);
    try {
      await reindexAgent(agentId, jwt);
      alert("Reindex started in background.");
    } catch (e) {
      alert("Reindex failed: " + e.message);
    }
    setLoading(false);
  }

  async function handleDelete() {
    if (!window.confirm("Delete this agent permanently?")) return;
    await deleteAgent(agentId, jwt);
    alert("Agent deleted.");
    onBack && onBack();
  }

  if (!agent) return <div style={{ padding: 20 }}>Loading agent…</div>;

  return (
    <div style={{ display: "flex", gap: 20, padding: 20 }}>

      {/* LEFT SIDEBAR */}
      <div style={{ width: 300, borderRight: "1px solid #eee", paddingRight: 20 }}>
        <h3>{agent.name}</h3>
        <p>{agent.description}</p>

        {/* Tabs */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <button onClick={() => setTab("general")}>General</button>
          <button onClick={() => setTab("chunking")}>Chunking</button>
          <button onClick={() => setTab("model")}>Model</button>
          <button onClick={() => setTab("docs")}>Documents</button>
        </div>

        <div style={{ marginTop: 12 }}>
          <button onClick={() => setOpenEdit(true)}>Edit</button>
          <button onClick={handleReindex} disabled={loading}>
            {loading ? "Reindexing…" : "Reindex"}
          </button>
          <button onClick={handleDelete} style={{ color: "red" }}>
            Delete
          </button>
        </div>

        <small>Agent ID: {agent.id}</small>
      </div>

      {/* RIGHT COLUMN */}
      <div style={{ flex: 1 }}>

        {tab === "general" && (
          <div>
            <h4>General</h4>
            <p><b>Name:</b> {agent.name}</p>
            <p><b>Description:</b> {agent.description}</p>
          </div>
        )}

        {tab === "chunking" && (
          <div>
            <h4>Chunking Settings</h4>
            <p><b>Strategy:</b> {agent.config?.chunk_strategy}</p>
            <p><b>Chunk Size:</b> {agent.config?.chunk_size}</p>
            <p><b>Overlap:</b> {agent.config?.overlap}</p>
            <button onClick={() => setOpenEdit(true)}>Edit Chunking</button>
          </div>
        )}

        {tab === "model" && (
          <div>
            <h4>Model</h4>
            <p>Currently using flan-t5-base server model.</p>
          </div>
        )}

        {tab === "docs" && (
          <div>
            <h4>Documents</h4>
            <DriveFiles
              jwt={jwt}
              gToken={localStorage.getItem("gToken") || localStorage.getItem("g_access_token")}
              agentId={agent.id}
            />
            <AgentDocList agentId={agent.id} jwt={jwt} />
          </div>
        )}

      </div>

      <EditAgentModal
        open={openEdit}
        onClose={() => setOpenEdit(false)}
        agent={agent}
        jwt={jwt}
        updateAgent={onUpdateAgent}
      />
    </div>
  );
}



// ---------------------------
// AgentDocList Component
// ---------------------------
function AgentDocList({ agentId, jwt }) {
  const [docs, setDocs] = useState([]);

  useEffect(() => {
    load();
  }, [agentId]);

  async function load() {
    try {
      const res = await getAgentDocs(agentId, jwt);
      setDocs(res.agent_docs || []);
    } catch {
      setDocs([]);
    }
  }

  async function removeDoc(fileId) {
    if (!window.confirm("Remove document from agent?")) return;
    await deleteAgentDoc(agentId, fileId, jwt);
    load();
  }

  return (
    <ul style={{ marginTop: 12 }}>
      {docs.length === 0 && <p>No documents added yet.</p>}
      {docs.map(doc => (
        <li key={doc.id} style={{ marginBottom: 8 }}>
          {doc.filename} ({doc.file_id})
          <button style={{ marginLeft: 8 }} onClick={() => removeDoc(doc.file_id)}>
            Remove
          </button>
        </li>
      ))}
    </ul>
  );
}
