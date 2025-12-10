// src/App.jsx
import React, { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import Chat from "./components/Chat";
import DriveFiles from "./components/DriveFiles";
import { authGoogleLoginUrl } from "./api/api";

export default function App() {
  const [jwt, setJwt] = useState(localStorage.getItem("jwt"));
  const [gToken, setGToken] = useState(localStorage.getItem("gToken"));
  const [view, setView] = useState("chat"); 
  const [selectedDoc, setSelectedDoc] = useState(null);

  // 🔥 FIXED LOGIN CALLBACK — HANDLES TOKENS FROM BACKEND
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
  }

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

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      
      <Sidebar setView={setView} jwt={jwt} onSelectDoc={setSelectedDoc} />

      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {/* Header */}
        <div style={{
          padding: 10,
          borderBottom: "1px solid #eee",
          display: "flex",
          justifyContent: "space-between"
        }}>
          <div>
            {selectedDoc ? `📄 ${selectedDoc.name}` : "Ask your documents"}
          </div>

          <div>
            <button onClick={logout} style={{ padding: 6, borderRadius: 6 }}>
              Logout
            </button>
          </div>
        </div>

        {/* Views */}
        {view === "chat" && <Chat jwt={jwt} selectedDoc={selectedDoc} />}
        {view === "docs" && <DriveFiles jwt={jwt} gToken={gToken} />}
        {view === "upload" && <DriveFiles jwt={jwt} gToken={gToken} />}
      </div>
    </div>
  );
}
