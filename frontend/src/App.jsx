// src/App.jsx
import React, { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import Chat from "./components/Chat";
import AgentChat from "./components/AgentChat";
import DriveFiles from "./components/DriveFiles";
import { authGoogleLoginUrl } from "./api/api";

export default function App() {
  const [jwt, setJwt] = useState(localStorage.getItem("jwt"));
  const [gToken, setGToken] = useState(localStorage.getItem("gToken"));

  // 🌟 Main UI states
  const [view, setView] = useState("chat"); 
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState(null);

  // ---------------------------
  // HANDLE GOOGLE LOGIN CALLBACK
  // ---------------------------
  useEffect(() => {
    const hash = new URLSearchParams(window.location.hash.substring(1));
    const jwtToken = hash.get("jwt");
    const gDriveToken = hash.get("g_access_token");

    let updated = false;

    if (jwtToken) {
      localStorage.setItem("jwt", jwtToken);
      setJwt(jwtToken);
      updated = true;
    }

    if (gDriveToken) {
      localStorage.setItem("gToken", gDriveToken);
      setGToken(gDriveToken);
      updated = true;
    }

    if (updated) {
      window.history.replaceState({}, document.title, "/");
    }
  }, []);

  function login() {
    window.location.href = authGoogleLoginUrl();
  }

  function logout() {
    localStorage.clear();
    setJwt(null);
    setGToken(null);
    setSelectedAgent(null);
    setSelectedDoc(null);
  }

  // ---------------------------
  // LOGIN PAGE
  // ---------------------------
  if (!jwt) {
    return (
      <div style={{
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        gap: 20
      }}>
        <h2>Login to Continue</h2>
        <button onClick={login} style={{ padding: 10, borderRadius: 6 }}>
          Sign in with Google
        </button>
      </div>
    );
  }

  // ---------------------------
  // LOGGED IN UI
  // ---------------------------
  return (
    <div style={{ display: "flex", height: "100vh" }}>

      {/* SIDEBAR */}
    <Sidebar
  jwt={jwt}
  setView={setView}   // <-- REQUIRED!
  onSelectDoc={(doc) => {
    setSelectedAgent(null);
    setSelectedDoc(doc);
    setView("chat");
  }}
  onSelectAgent={(agent) => {
    setSelectedDoc(null);
    setSelectedAgent(agent);
    setView("agent");
  }}
/>

      {/* MAIN PANEL */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>

        {/* HEADER */}
        <div style={{
          padding: 10,
          borderBottom: "1px solid #eee",
          display: "flex",
          justifyContent: "space-between"
        }}>
          <div>
            {selectedAgent
              ? `🤖 Agent: ${selectedAgent.name}`
              : selectedDoc
                ? `📄 ${selectedDoc.name}`
                : "Ask your knowledge base"}
          </div>

          <button onClick={logout} style={{ padding: 6, borderRadius: 6 }}>
            Logout
          </button>
        </div>

        {/* VIEWS */}
        {view === "chat" && (
          <Chat jwt={jwt} selectedDoc={selectedDoc} />
        )}

        {view === "agent" && selectedAgent && (
          <AgentChat jwt={jwt} agent={selectedAgent} />
        )}

        {(view === "docs" || view === "upload") && (
          <DriveFiles jwt={jwt} gToken={gToken} />
        )}

      </div>
    </div>
  );
}
