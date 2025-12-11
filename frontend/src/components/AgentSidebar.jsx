// src/components/AgentSidebar.jsx
import React from "react";

export default function AgentSidebar({ jwt, agent, view, setView }) {
  return (
    <div style={{ width: 260, borderRight: "1px solid #eee", padding: 16, background: "#fafafa" }}>
      <h3>{agent.name}</h3>
      <p style={{ color: "#666" }}>{agent.description}</p>

      <div style={{ marginTop: 20 }}>
        <button style={btn} onClick={() => setView("chat")}>💬 Chat</button>
        <button style={btn} onClick={() => setView("docs")}>📄 Documents</button>
        <button style={btn} onClick={() => setView("upload")}>⬆ Upload</button>
        <button style={btn} onClick={() => setView("settings")}>⚙ Settings</button>
      </div>
    </div>
  );
}

const btn = {
  display: "block",
  width: "100%",
  padding: "10px",
  marginBottom: 8,
  textAlign: "left",
  borderRadius: 6,
  border: "1px solid #ddd",
  background: "#fff",
  cursor: "pointer"
};
