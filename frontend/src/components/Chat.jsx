import React, { useEffect, useState, useRef } from "react";
import { getHistory, generateAnswer } from "../api/api";
import QuestionAnswer from "./QuestionAnswer";

export default function Chat({ jwt, selectedDoc }) {
  const [messages, setMessages] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    if (!jwt) return;
    loadHistory();
  }, [jwt]);

  async function loadHistory() {
    try {
      const res = await getHistory(jwt);
      setMessages(res.history || []);
      scrollToEnd();
    } catch (e) {
      setMessages([]);
    }
  }

  function scrollToEnd() {
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 120);
  }

  async function ask() {
    if (!q.trim()) return;
    setLoading(true);
    try {
      // backend's generate returns { answer, sources, history }
      const res = await generateAnswer(q, jwt, 5, null);
      if (res.history) setMessages(res.history);
      else {
        setMessages((m) => [...m, { role: "user", text: q }, { role: "assistant", text: res.answer }]);
      }
      setQ("");
      scrollToEnd();
    } catch (e) {
      alert("Error: " + (e.message || e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{
        flex: 1, overflowY: "auto", border: "1px solid #eee", padding: 12, borderRadius: 8
      }}>
        {messages.map((m, i) => (
          <div key={i} style={{ margin: "8px 0", textAlign: m.role === "user" ? "right" : "left" }}>
            <div style={{
              display: "inline-block",
              background: m.role === "user" ? "#DCF8C6" : "#F1F0F0",
              padding: "8px 12px",
              borderRadius: 12,
              maxWidth: "80%"
            }}>
              {m.text}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about your documents..." style={{ flex: 1, padding: 8 }} />
        <button onClick={ask} disabled={loading || !q.trim()}>{loading ? "Thinking..." : "Ask"}</button>
      </div>

      {/* Optional: show last answer sources */}
      {/* <QuestionAnswer jwt={jwt} /> */}
    </div>
  );
}
