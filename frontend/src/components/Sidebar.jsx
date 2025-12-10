// src/components/Sidebar.jsx
import React, { useEffect, useState } from "react";
import { listDocs } from "../api/api";

export default function Sidebar({ jwt, onSelectDoc, setView }) {
  const [docs, setDocs] = useState([]);

  useEffect(() => {
    loadDocs();
    window.addEventListener("storage", loadDocs);
    return () => window.removeEventListener("storage", loadDocs);
  }, []);

  async function loadDocs() {
    try {
      const res = await listDocs(jwt);
      setDocs(res.docs || []);
    } catch (e) {
      console.error("Failed to load docs", e);
    }
  }

  return (
    <div style={{
      width: 250,
      borderRight: "1px solid #eee",
      padding: 16,
      background: "#fafafa"
    }}>
      <button onClick={() => setView("chat")} style={btnStyle}>💬 Chat</button>
      <button onClick={() => setView("docs")} style={btnStyle}>📄 Documents</button>
      <button onClick={() => setView("upload")} style={btnStyle}>⬆ Upload</button>

      <h3>Your Documents</h3>
      <ul style={{ listStyle: "none", padding: 0 }}>
        {docs.map((d, i) => (
          <li
            key={i}
            onClick={() => onSelectDoc(d)}
            style={{ cursor: "pointer", padding: "6px 0" }}
          >
            📄 {d.name}
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
  cursor: "pointer"
};
