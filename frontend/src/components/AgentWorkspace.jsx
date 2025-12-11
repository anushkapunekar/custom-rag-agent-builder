// src/components/AgentWorkspace.jsx
import React, { useState, useEffect, useRef } from "react";
import { uploadFilesToAgent, getAgentHistory, saveAgentHistory } from "../api/api";
import DriveFiles from "./DriveFiles";

export default function AgentWorkspace({ jwt, agent, onBack }) {
  const [tab, setTab] = useState("chat");
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [agentDocs, setAgentDocs] = useState([]);
  const endRef = useRef(null);

  useEffect(() => {
    if (!agent) return;
    loadAgentDocs();
    loadAgentHistory();
  }, [agent]);

  async function loadAgentDocs() {
    try {
      const res = await fetch(`${import.meta.env.VITE_BACKEND_URL || "http://localhost:8000"}/agents/${agent.id}`, {
        headers: { Authorization: `Bearer ${jwt}` }
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setAgentDocs(data.agent_docs || []);
    } catch {
      setAgentDocs([]);
    }
  }

  async function loadAgentHistory() {
    try {
      const data = await getAgentHistory(agent.id, jwt);
      setMessages(data.history || []);
    } catch (e) {
      console.error("History load error", e);
    }
  }

  async function askAgent() {
    if (!question.trim()) return;
    setLoading(true);

    try {
      const res = await fetch(`${import.meta.env.VITE_BACKEND_URL || "http://localhost:8000"}/agents/${agent.id}/qa/generate`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${jwt}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: question, k: 5, max_new_tokens: 150 }),
      });

      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      const userMsg = { role: "user", text: question, ts: Date.now() };
      const botMsg = { role: "assistant", text: data.answer, ts: Date.now() + 1, sources: data.sources };

      setMessages((prev) => {
        const updated = [...prev, userMsg, botMsg];

        saveAgentHistory(agent.id, updated, jwt)
          .catch(err => console.error("history save failed", err));

        return updated;
      });

      setQuestion("");
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (e) {
      alert("Chat error: " + e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(fileIds) {
    try {
      await uploadFilesToAgent(agent.id, fileIds, jwt);
      alert("Uploaded & indexed!");
      loadAgentDocs();
    } catch (e) {
      alert("Upload failed: " + e.message);
    }
  }

  return (
    <div style={{ padding: 20, height: "100%", display: "flex", flexDirection: "column" }}>
      {/* header */}
      <div style={{ marginBottom: 20, display: "flex", justifyContent: "space-between" }}>
        <h2>🤖 {agent.name}</h2>
        <button onClick={onBack} style={{ padding: 8 }}>⬅ Back</button>
      </div>

      {/* tabs */}
      <div style={{ marginBottom: 20, display: "flex", gap: 10 }}>
        <button onClick={() => setTab("chat")}>💬 Chat</button>
        <button onClick={() => setTab("docs")}>📄 Documents</button>
        <button onClick={() => setTab("upload")}>⬆ Upload</button>
        <button onClick={() => setTab("settings")}>⚙ Settings</button>
      </div>

      {tab === "chat" && (
        <>
          <div style={{ flex: 1, overflowY: "auto", border: "1px solid #ddd", padding: 12, borderRadius: 8 }}>
            {messages.map((m, i) => (
              <div key={i} style={{ marginBottom: 12, textAlign: m.role === "user" ? "right" : "left" }}>
                <div style={{ display: "inline-block", background: m.role === "user" ? "#d6f5e1" : "#efefef", padding: "8px 12px", borderRadius: 8 }}>
                  {m.text}
                </div>
              </div>
            ))}
            <div ref={endRef}></div>
          </div>

          <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
            <input style={{ flex: 1 }} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask your agent..." />
            <button onClick={askAgent} disabled={loading}>{loading ? "Thinking…" : "Ask"}</button>
          </div>
        </>
      )}

      {tab === "docs" && (
        <div>
          <h3>Documents</h3>
          <ul>
            {agentDocs.length === 0 && <p>No documents.</p>}
            {agentDocs.map((d) => <li key={d.id}>{d.filename}</li>)}
          </ul>
        </div>
      )}

      {tab === "upload" && (
        <div>
          <h3>Upload docs to agent</h3>
          <DriveFiles jwt={jwt} gToken={localStorage.getItem("gToken") || localStorage.getItem("g_access_token")} agentId={agent.id} />
        </div>
      )}

      {tab === "settings" && (
        <div>
          <h3>Settings</h3>
          <p>Open the agent settings page for advanced controls.</p>
        </div>
      )}
    </div>
  );
}
