// src/components/AgentChat.jsx
import React, { useEffect, useState, useRef } from "react";
import { getHistory, generateAnswer, getAgent } from "../api/api"; // getAgent should be added to api.js

export default function AgentChat({ jwt, agent }) {
  const [loading, setLoading] = useState(true);
  const [agentMeta, setAgentMeta] = useState(null);
  const [messages, setMessages] = useState([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState(null);
  const [thinking, setThinking] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    let active = true;
    setError(null);
    setLoading(true);
    setAgentMeta(null);
    setMessages([]);

    async function init() {
      if (!agent || !agent.id) {
        setError("No agent selected.");
        setLoading(false);
        return;
      }

      try {
        // 1) optional: fetch agent metadata (useful to show config)
        try {
          const res = await getAgent(agent.id, jwt);
          if (!active) return;
          setAgentMeta(res.agent || { id: agent.id, name: agent.name });
        } catch (e) {
          // Not fatal — continue. But show a console message.
          console.warn("Failed loading agent meta:", e.message || e);
          setAgentMeta({ id: agent.id, name: agent.name });
        }

        // 2) fetch user's chat history (we keep global history for now)
        try {
          const hist = await getHistory(jwt);
          if (!active) return;
          // optionally filter history for messages that include this agent in sources,
          // but for now we show global history
          setMessages((hist.history || []).slice(-200));
        } catch (e) {
          console.warn("Failed loading history:", e.message || e);
          setMessages([]);
        }
      } catch (e) {
        if (!active) return;
        setError("Failed to initialize agent: " + (e.message || e));
      } finally {
        if (active) setLoading(false);
      }
    }

    init();

    return () => {
      active = false;
    };
  }, [agent, jwt]);

  function scrollEnd() {
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 120);
  }

   async function ask() {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await generateAgentAnswer(agent.id, q, jwt, 5, 200);
      // backend returns { answer, sources, history }
      if (res.history) {
        setMessages(res.history);
      } else {
        setMessages((m) => [...m, { role: "user", text: q }, { role: "assistant", text: res.answer }]);
      }
      setQ("");
      scrollEnd();
    } catch (e) {
      alert("Agent error: " + (e.message || e));
    } finally {
      setLoading(false);
    }
  }
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: 12 }}>
      <div style={{ flex: 1, overflowY: "auto", border: "1px solid #ddd", padding: 12, borderRadius: 8 }}>
        <h4>{agentMeta ? `Agent: ${agentMeta.name}` : `Agent: ${agent?.name}`}</h4>

        {messages.length === 0 && <div style={{ color: "#666" }}>No chat history yet. Ask the agent anything.</div>}

        {messages.map((m, i) => (
          <div key={i} style={{ margin: "10px 0", textAlign: m.role === "user" ? "right" : "left" }}>
            <div style={{ display: "inline-block", padding: "10px 14px", background: m.role === "user" ? "#c7f7d4" : "#f0f0f0", borderRadius: 12, maxWidth: "80%" }}>
              {m.text}
            </div>
          </div>
        ))}

        <div ref={endRef}></div>
      </div>

      <div style={{ marginTop: 12 }}>
        {error && <div style={{ color: "red", marginBottom: 8 }}>{error}</div>}
        <div style={{ display: "flex", gap: 8 }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Ask ${agent?.name}...`} style={{ flex: 1, padding: 10 }} />
          <button onClick={ask} disabled={thinking || !q.trim()}>
            {thinking ? "Thinking..." : "Ask"}
          </button>
        </div>
      </div>
    </div>
  );
}
