// src/components/Sidebar.jsx
import React, { useEffect, useState } from "react";
import { listDocs } from "../api/api";

export default function Sidebar({ jwt, onSelectDoc, setView }) {
  const [docs, setDocs] = useState([]);

  useEffect(() => {
    if (!jwt) return;
    loadDocs();

    window.addEventListener("storage", loadDocs);
    return () => window.removeEventListener("storage", loadDocs);
  }, [jwt]);

  async function loadDocs() {
    try {
      const res = await listDocs(jwt);
      setDocs(res.docs || []);
    } catch (e) {
      setDocs([]);
    }
  }

  return (
    <div style={{
      width: 260,
      borderRight: "1px solid #eee",
      padding: 16,
      background: "#fafafa"
    }}>

      {/* MAIN NAVIGATION */}
      <button onClick={() => setView("chat")} style={btnStyle}>💬 Chat</button>
      <button onClick={() => setView("docs")} style={btnStyle}>📄 Documents</button>
      <button onClick={() => setView("upload")} style={btnStyle}>⬆ Upload</button>
      <button onClick={() => setView("agents")} style={btnStyle}>🤖 Agents</button>

      {/* DOCUMENTS LIST */}
      <h3>Your Documents</h3>
      <ul style={{ listStyle: "none", paddingLeft: 0 }}>
        {docs.map((d, i) => (
          <li
            key={i}
            onClick={() => {
              setView("chat");
              onSelectDoc(d);
            }}
            style={{ padding: "6px 0", cursor: "pointer" }}
          >
            📄 {d.name || d.filename}
          </li>
        ))}
      </ul>

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
