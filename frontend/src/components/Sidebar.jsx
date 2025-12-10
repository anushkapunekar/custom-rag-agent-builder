// src/components/Sidebar.jsx
import React, { useEffect, useState } from "react";
import { listDocs, listAgents } from "../api/api";
import AgentBuilder from "./AgentBuilder";

export default function Sidebar({ jwt, onSelectDoc, onSelectAgent, setView }) {
  const [docs, setDocs] = useState([]);
  const [agents, setAgents] = useState([]);

  useEffect(() => {
    if (!jwt) return;
    loadDocs();
    loadAgents();

    window.addEventListener("storage", refreshAll);
    return () => window.removeEventListener("storage", refreshAll);
  }, [jwt]);

  function refreshAll() {
    loadDocs();
    loadAgents();
  }

  async function loadDocs() {
    try {
      const res = await listDocs(jwt);
      setDocs(res.docs || []);
    } catch (e) {
      setDocs([]);
    }
  }

  async function loadAgents() {
    try {
      const res = await listAgents(jwt);
      setAgents(res.agents || []);
    } catch (e) {
      setAgents([]);
    }
  }

  return (
    <div style={{
      width: 260,
      borderRight: "1px solid #eee",
      padding: 16,
      background: "#fafafa"
    }}>

      {/* 🔥 ORIGINAL BUTTONS (restored) */}
      <button onClick={() => setView("chat")} style={btnStyle}>💬 Chat</button>
      <button onClick={() => setView("docs")} style={btnStyle}>📄 Documents</button>
      <button onClick={() => setView("upload")} style={btnStyle}>⬆ Upload</button>

      {/* 🔥 Documents */}
      <h3>Your Documents</h3>
      <ul style={{ listStyle: "none", paddingLeft: 0 }}>
        {docs.map((d, i) => (
          <li key={i}
              onClick={() => onSelectDoc(d)}
              style={{ padding: "6px 0", cursor: "pointer" }}>
            📄 {d.name || d.filename}
          </li>
        ))}
      </ul>

      {/* 🔥 Agents Section */}
      <div style={{ marginTop: 20 }}>
        <h3>Your Agents</h3>

        <AgentBuilder
          jwt={jwt}
          gToken={localStorage.getItem("gToken") || localStorage.getItem("g_access_token")}
          onCreated={loadAgents}
        />

        <ul style={{ listStyle: "none", paddingLeft: 0, marginTop: 10 }}>
          {agents.map((a) => (
            <li key={a.id}
                onClick={() => onSelectAgent(a)}
                style={{ padding: "6px 0", cursor: "pointer" }}>
              🤖 {a.name}
            </li>
          ))}
        </ul>
      </div>

    </div>
  );
}

const btnStyle = {
  width: "100%",
  padding: "10px",
  textAlign: "left",
  border: "1px solid #ddd",
  borderRadius: 6,
  marginBottom: 8,
  cursor: "pointer",
  background: "#fff"
};
