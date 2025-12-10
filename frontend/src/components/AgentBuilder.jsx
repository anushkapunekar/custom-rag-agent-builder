// src/components/AgentBuilder.jsx
import React, { useState, useEffect } from "react";
import Modal from "./Modal";
import { createAgent, listDocs, uploadFilesToAgent } from "../api/api";

const API_KEY = import.meta.env.VITE_GOOGLE_API_KEY;

export default function AgentBuilder({ jwt, gToken: gTokenProp, onCreated }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [chunkStrategy, setChunkStrategy] = useState("smart");
  const [preset, setPreset] = useState("medium");
  const [chunkSize, setChunkSize] = useState(800);
  const [overlap, setOverlap] = useState(200);
  const [selectedDriveFiles, setSelectedDriveFiles] = useState([]);
  const [backendDriveFiles, setBackendDriveFiles] = useState([]);
  const [loading, setLoading] = useState(false);

  // load backend list for optional selection
  useEffect(() => {
    if (!jwt) return;
    fetchBackendFiles();
    // presets -> initial values
    applyPreset("medium");
  }, [jwt]);

  function applyPreset(key) {
    setPreset(key);
    if (key === "small") {
      setChunkSize(400);
      setOverlap(80);
    } else if (key === "medium") {
      setChunkSize(800);
      setOverlap(200);
    } else if (key === "large") {
      setChunkSize(1600);
      setOverlap(400);
    }
  }

  async function fetchBackendFiles() {
    try {
      const res = await listDocs(jwt);
      setBackendDriveFiles(res.docs || []);
    } catch {
      setBackendDriveFiles([]);
    }
  }

  // get token - prefer prop, fallback to localStorage
  function getGToken() {
    return gTokenProp || localStorage.getItem("gToken") || localStorage.getItem("g_access_token");
  }

function openPicker() {
  const token = getGToken();
  if (!API_KEY) return alert("Missing Google developer API key (VITE_GOOGLE_API_KEY).");
  if (!token) {
    return alert(
      "Missing Google Drive access token. Please login again so your gToken can be saved."
    );
  }

  function startPicker() {
    window.gapi.load("picker", () => buildPicker(token));
  }

  // Ensure gapi is loaded
  if (!window.gapi || !window.google?.picker) {
    const script = document.createElement("script");
    script.src = "https://apis.google.com/js/api.js";
    script.onload = startPicker;
    document.body.appendChild(script);
  } else {
    startPicker();
  }
}

function buildPicker(token) {
  const view = new window.google.picker.DocsView(window.google.picker.ViewId.DOCS)
    .setIncludeFolders(false)
    .setSelectFolderEnabled(false);

  const picker = new window.google.picker.PickerBuilder()
    .setDeveloperKey(API_KEY)
    .setOAuthToken(token)
    .addView(view)
    .setTitle("Select files to add to agent")
    .setCallback((data) => {
      if (data.action === window.google.picker.Action.PICKED) {
        const picked = (data.docs || []).map(d => ({ id: d.id, name: d.name }));
        setSelectedDriveFiles(prev => {
          const ids = new Set(prev.map(p => p.id));
          const merged = [...prev];
          picked.forEach(p => { if (!ids.has(p.id)) merged.push(p); });
          return merged;
        });
      }
    })
    .build();

  picker.setVisible(true);

  // ⭐ FIX: Raise picker above your modal (modal had z-index 9999)
  setTimeout(() => {
    const dialogs = document.querySelectorAll(".picker-dialog");
    dialogs.forEach((d) => {
      d.style.zIndex = "99999999";    // Highest priority
      d.style.position = "fixed";     // Prevent clipping
    });
  }, 200);
}

  function toggleBackendFile(id, filename) {
    setSelectedDriveFiles((s) => {
      if (s.find(x => x.id === id)) return s.filter(x => x.id !== id);
      return [...s, { id, name: filename }];
    });
  }

  async function create() {
    if (!name.trim()) return alert("Agent needs a name");
    setLoading(true);

    const config = {
      chunk_strategy: chunkStrategy,
      chunk_size: Number(chunkSize),
      overlap: Number(overlap)
    };

    try {
      const res = await createAgent({ name, description: desc, config }, jwt);
      const agent = res.agent;
      if (selectedDriveFiles.length) {
        const ids = selectedDriveFiles.map(d => d.id);
        await uploadFilesToAgent(agent.id, ids, jwt);
      }
      alert("Agent created!");
      setOpen(false);
      setName(""); setDesc(""); setSelectedDriveFiles([]);
      onCreated && onCreated();
    } catch (e) {
      alert("Failed to create agent: " + (e.message || e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button onClick={() => setOpen(true)}>Build your own agent</button>

      <Modal open={open} title="Create Agent" onClose={() => setOpen(false)}>
        <div style={{ display: "grid", gap: 10 }}>
          <label>Agent name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} />

          <label>Description</label>
          <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} />

          <div>
            <label>Chunking strategy</label>
            <select value={chunkStrategy} onChange={(e) => setChunkStrategy(e.target.value)}>
              <option value="smart">Smart (sentence-aware)</option>
              <option value="fixed">Fixed (character-based)</option>
              <option value="sentences">Sentences (split on sentence boundaries)</option>
            </select>
          </div>

          <div>
            <label>Presets</label>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => applyPreset("small")}>Small</button>
              <button onClick={() => applyPreset("medium")}>Medium</button>
              <button onClick={() => applyPreset("large")}>Large</button>
              <div style={{ marginLeft: 12 }}>
                <small>Custom:</small>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <div style={{ flex: 1 }}>
              <label>Chunk size</label>
              <input type="number" value={chunkSize} onChange={(e) => setChunkSize(e.target.value)} />
            </div>
            <div style={{ width: 140 }}>
              <label>Overlap</label>
              <input type="number" value={overlap} onChange={(e) => setOverlap(e.target.value)} />
            </div>
          </div>

          <div>
            <h4>Attach files</h4>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={openPicker}>Pick from Google Drive</button>
              <button onClick={fetchBackendFiles}>Load backend list</button>
            </div>

            <div style={{ marginTop: 8 }}>
              <small>Or add files available from your previously indexed Drive list:</small>
              <ul style={{ maxHeight: 160, overflow: "auto", paddingLeft: 16 }}>
                {backendDriveFiles.map(d => (
                  <li key={d.id} style={{ marginBottom: 6 }}>
                    <button onClick={() => toggleBackendFile(d.id, d.name)} style={{ marginRight: 8 }}>
                      {selectedDriveFiles.find(x => x.id === d.id) ? "✓" : "Add"}
                    </button>
                    {d.name}
                  </li>
                ))}
                {backendDriveFiles.length === 0 && <li style={{ color: "#666" }}>No backend files found</li>}
              </ul>
            </div>

            <div>
              <h5>Selected</h5>
              <ul>
                {selectedDriveFiles.map(f => <li key={f.id}>{f.name} <small style={{ color: "#666" }}>({f.id})</small></li>)}
                {selectedDriveFiles.length === 0 && <li style={{ color: "#666" }}>No files chosen</li>}
              </ul>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={create} disabled={loading}>{loading ? "Creating…" : "Create Agent"}</button>
            <button onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </div>
      </Modal>
    </>
  );
}
