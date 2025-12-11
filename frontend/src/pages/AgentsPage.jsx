// src/pages/AgentPage.jsx
import React, { useEffect, useState } from "react";
import { listAgents, deleteAgent } from "../api/api";
import AgentBuilder from "../components/AgentBuilder";
import AgentWorkspace from "../components/AgentWorkspace";

export default function AgentPage({ jwt }) {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [mode, setMode] = useState("list"); 
  // modes: "list" → list of agents; "create" → create form; "workspace" → manage agent

  useEffect(() => {
    if (!jwt) return;
    loadAgents();
  }, [jwt]);

  async function loadAgents() {
    try {
      const res = await listAgents(jwt);
      setAgents(res.agents || []);
    } catch (e) {
      console.error("Failed to load agents", e);
    }
  }

  async function removeAgent(id) {
    if (!window.confirm("Delete this agent permanently?")) return;
    try {
      await deleteAgent(id, jwt);
      loadAgents();
      setSelectedAgent(null);
      setMode("list");
    } catch (e) {
      alert("Failed to delete: " + e.message);
    }
  }

  return (
    <div style={{ padding: 20 }}>

      {/* AGENT LIST PAGE */}
      {mode === "list" && (
        <>
          <h2>Your Agents</h2>
          <button
            style={{ padding: 10, marginBottom: 20 }}
            onClick={() => setMode("create")}
          >
            ➕ Build New Agent
          </button>

          {agents.length === 0 && <p>No agents created yet.</p>}

          <ul style={{ listStyle: "none", paddingLeft: 0 }}>
            {agents.map((a) => (
              <li
                key={a.id}
                style={{
                  padding: "10px",
                  border: "1px solid #ddd",
                  borderRadius: 8,
                  marginBottom: 10,
                  background: "#fafafa",
                  cursor: "pointer"
                }}
              >
                <div onClick={() => { setSelectedAgent(a); setMode("workspace"); }}>
                  🤖 <b>{a.name}</b>
                  <br />
                  <small>{a.description}</small>
                </div>

                <button
                  style={{
                    marginTop: 8,
                    background: "#ffdddd",
                    padding: "6px",
                    borderRadius: 6
                  }}
                  onClick={() => removeAgent(a.id)}
                >
                  ❌ Delete
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {/* CREATE AGENT PAGE */}
      {mode === "create" && (
        <>
          <h2>Create Your Agent</h2>
          <AgentBuilder
            jwt={jwt}
            gToken={localStorage.getItem("gToken")}
            onCreated={() => {
              loadAgents();
              setMode("list");
            }}
          />
          <br />
          <button onClick={() => setMode("list")}>⬅ Back</button>
        </>
      )}

      {/* AGENT WORKSPACE PAGE */}
      {mode === "workspace" && selectedAgent && (
        <AgentWorkspace
          jwt={jwt}
          agent={selectedAgent}
          onBack={() => setMode("list")}
        />
      )}
    </div>
  );
}
