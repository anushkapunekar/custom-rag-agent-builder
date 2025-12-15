// src/components/AgentWorkspace.jsx
import React, { useState, useEffect, useRef } from "react";
import { uploadFilesToAgent, getAgentHistory, saveAgentHistory } from "../api/api";
import DriveFiles from "./DriveFiles";

const BACKEND = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

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
      const res = await fetch(`${BACKEND}/agents/${agent.id}`, {
        headers: { Authorization: `Bearer ${jwt}` }
      });
      if (!res.ok) throw new Error();
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
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "auto" }), 50);
    } catch (e) {
      console.error("History load error", e);
    }
  }

  // ---------------- CHAT ----------------
  async function askAgent() {
    if (!question.trim()) return;
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND}/agents/${agent.id}/qa/generate`, {
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
      const botMsg = {
        role: "assistant",
        text: data.answer,
        ts: Date.now() + 1,
        sources: data.sources || [],
      };

      const updated = [...messages, userMsg, botMsg];
      setMessages(updated);

      // persist history
      await saveAgentHistory(agent.id, updated, jwt);

      setQuestion("");
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (e) {
      alert("Chat error: " + e.message);
    } finally {
      setLoading(false);
    }
  }

  // ---------------- FEEDBACK ----------------
  async function sendFeedback({ correct, query, answer, better_answer }) {
    try {
      await fetch(`${BACKEND}/agents/${agent.id}/feedback`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${jwt}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          correct,
          query,
          answer,
          better_answer: better_answer || null,
        }),
      });
      alert(correct ? "Feedback noted 👍" : "Thanks — retraining scheduled 👌");
    } catch (e) {
      alert("Feedback error: " + e.message);
    }
  }

  // ---------------- UPLOAD ----------------
  async function handleUpload(fileIds) {
    try {
      await uploadFilesToAgent(agent.id, fileIds, jwt);
      alert("Uploaded & indexed!");
      loadAgentDocs();
    } catch (e) {
      alert("Upload failed: " + e.message);
    }
  }

  // ---------------- UI ----------------
  return (
    <div style={{ padding: 20, height: "100%", display: "flex", flexDirection: "column" }}>
      {/* HEADER */}
      <div style={{ marginBottom: 20, display: "flex", justifyContent: "space-between" }}>
        <h2>🤖 {agent.name}</h2>
        <button onClick={onBack}>⬅ Back</button>
      </div>

      {/* TABS */}
      <div style={{ marginBottom: 20, display: "flex", gap: 10 }}>
        <button onClick={() => setTab("chat")}>💬 Chat</button>
        <button onClick={() => setTab("docs")}>📄 Documents</button>
        <button onClick={() => setTab("upload")}>⬆ Upload</button>
        <button onClick={() => setTab("settings")}>⚙ Settings</button>
      </div>

      {/* CHAT */}
      {tab === "chat" && (
        <>
          <div style={{ flex: 1, overflowY: "auto", border: "1px solid #ddd", padding: 12, borderRadius: 8 }}>
            {messages.map((m, i) => (
              <div key={i} style={{ marginBottom: 14, textAlign: m.role === "user" ? "right" : "left" }}>
                <div
                  style={{
                    display: "inline-block",
                    background: m.role === "user" ? "#d6f5e1" : "#efefef",
                    padding: "8px 12px",
                    borderRadius: 8,
                  }}
                >
                  {m.text}
                </div>

                {/* FEEDBACK BUTTONS */}
                {m.role === "assistant" && (
                  <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                    <button onClick={() =>
                      sendFeedback({ correct: true, query: m.text, answer: m.text })
                    }>👍</button>

                    <button onClick={async () => {
                      const better = prompt("Optional: paste a better answer (or leave empty)");
                      sendFeedback({
                        correct: false,
                        query: m.text,
                        better_answer: better,
                      });
                    }}>👎</button>
                  </div>
                )}
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
            <input
              style={{ flex: 1 }}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask your agent..."
            />
            <button onClick={askAgent} disabled={loading}>
              {loading ? "Thinking…" : "Ask"}
            </button>
          </div>
        </>
      )}

      {/* DOCS */}
      {tab === "docs" && (
        <div>
          <h3>Documents</h3>
          <ul>
            {agentDocs.length === 0 && <p>No documents.</p>}
            {agentDocs.map((d) => (
              <li key={d.id}>{d.filename}</li>
            ))}
          </ul>
        </div>
      )}

      {/* UPLOAD */}
      {tab === "upload" && (
        <div>
          <h3>Upload docs to agent</h3>
          <DriveFiles
            jwt={jwt}
            gToken={localStorage.getItem("gToken") || localStorage.getItem("g_access_token")}
            agentId={agent.id}
          />
        </div>
      )}

      {/* SETTINGS */}
      {tab === "settings" && (
        <div>
          <h3>Agent Settings</h3>
          <p>Advanced controls coming next (edit config, chunking, retrain).</p>
        </div>
      )}
    </div>
  );
}
