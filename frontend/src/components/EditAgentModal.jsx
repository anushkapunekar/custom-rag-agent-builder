// src/components/EditAgentModal.jsx
import React, { useState, useEffect } from "react";
import Modal from "./Modal";

export default function EditAgentModal({ open, onClose, agent, jwt, onSaved, updateAgent }) {
  const [name, setName] = useState(agent?.name || "");
  const [description, setDescription] = useState(agent?.description || "");
  const [chunkStrategy, setChunkStrategy] = useState(agent?.config?.chunk_strategy || "fixed");
  const [chunkSize, setChunkSize] = useState(agent?.config?.chunk_size || 800);
  const [overlap, setOverlap] = useState(agent?.config?.overlap || 200);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setName(agent?.name || "");
    setDescription(agent?.description || "");
    setChunkStrategy(agent?.config?.chunk_strategy || "fixed");
    setChunkSize(agent?.config?.chunk_size || 800);
    setOverlap(agent?.config?.overlap || 200);
  }, [agent, open]);

  async function save() {
    setSaving(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        config: {
          chunk_strategy: chunkStrategy,
          chunk_size: Number(chunkSize),
          overlap: Number(overlap)
        }
      };
      await updateAgent(agent.id, payload);
      onSaved && onSaved();
      onClose();
    } catch (e) {
      alert("Save failed: " + (e.message || e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} title={`Edit Agent — ${agent?.name || ""}`} onClose={onClose}>
      <div style={{ display: "grid", gap: 10 }}>
        <label>Agent name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} />

        <label>Description</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />

        <label>Chunking strategy</label>
        <select value={chunkStrategy} onChange={(e) => setChunkStrategy(e.target.value)}>
          <option value="smart">Smart (sentence-aware)</option>
          <option value="fixed">Fixed (character-based)</option>
          <option value="sentences">Sentences (split on sentence boundaries)</option>
        </select>

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

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={onClose} disabled={saving}>Cancel</button>
          <button onClick={save} disabled={saving}>{saving ? "Saving…" : "Save & Reindex"}</button>
        </div>
      </div>
    </Modal>
  );
}
