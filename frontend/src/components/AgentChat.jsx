
import React, { useEffect, useState, useRef } from "react";
import { getHistory, generateAnswer } from "../api/api";

export default function AgentChat({ jwt, agent }) {
  // agent: { id, name, description }
  const [messages, setMessages] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    if (!jwt || !agent) return;
    loadHistory();
  }, [jwt, agent]);

  async function loadHistory() {
    try {
      const res = await getHistory(jwt);
      // Filter history for entries that belong to this agent if you saved with sources
      // For now we load global history and show; if you prefer agent-specific history implement endpoint.
      setMessages(res.history || []);
    } catch {
      setMessages([]);
    }
  }

  function scrollEnd() {
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 120);
  }

  async function ask() {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await generateAnswer(q, jwt, 5, 200, agent.id);
      setMessages(res.history || [...messages, { role: "user", text: q }, { role: "assistant", text: res.answer }]);
      setQ("");
      scrollEnd();
    } catch (e) {
      alert("Error: " + e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: 12 }}>
      <div style={{ flex: 1, overflowY: "auto", border: "1px solid #ddd", padding: 12, borderRadius: 8 }}>
        <h4>{agent ? `Agent: ${agent.name}` : "Select an agent"}</h4>
        {messages.map((m, i) => (
          <div key={i} style={{ margin: "8px 0", textAlign: m.role === "user" ? "right" : "left" }}>
            <div style={{ display: "inline-block", background: m.role === "user" ? "#c7f7d4" : "#f0f0f0", padding: 8, borderRadius: 8 }}>
              {m.text}
            </div>
          </div>
        ))}
        <div ref={endRef}></div>
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: 1 }} placeholder="Ask this agent..." />
        <button onClick={ask} disabled={loading}>{loading ? "Thinking..." : "Ask"}</button>
      </div>
    </div>
  );
}
