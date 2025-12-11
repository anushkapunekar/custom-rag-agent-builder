// src/components/DriveFiles.jsx
import React, { useEffect, useState } from "react";
import Modal from "./Modal";
import { downloadFiles, uploadFilesToAgent, listDocs } from "../api/api";

const API_KEY = import.meta.env.VITE_GOOGLE_API_KEY;

export default function DriveFiles({ jwt, gToken, agentId }) {
  const [backendFiles, setBackendFiles] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalPayload, setModalPayload] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchBackendFiles();
  }, [jwt]);

  async function fetchBackendFiles() {
    const res = await listDocs(jwt);
    setBackendFiles(res.docs || []);
  }

  function getGToken() {
    return (
      gToken ||
      localStorage.getItem("gToken") ||
      localStorage.getItem("g_access_token")
    );
  }

  // -----------------------
  // PICKER → buildPicker()
  // -----------------------
  const openPicker = () => {
    const token = getGToken();
    if (!API_KEY) return alert("Missing Google API key (VITE_GOOGLE_API_KEY)");
    if (!token) return alert("Missing Google Drive token. Please login again.");

    // Fix Picker UNDER modal → force high z-index
    const pickerCss = document.createElement("style");
    pickerCss.innerHTML = `
      .picker-dialog {
        z-index: 999999 !important;
      }
    `;
    document.head.appendChild(pickerCss);

    if (!window.gapi || !window.google?.picker) {
      const script = document.createElement("script");
      script.src = "https://apis.google.com/js/api.js";
      script.onload = () =>
        window.gapi.load("picker", () => buildPicker(token));
      document.body.appendChild(script);
      return;
    }

    window.gapi.load("picker", () => buildPicker(token));
  };

  const buildPicker = (token) => {
    const view = new window.google.picker.DocsView(
      window.google.picker.ViewId.DOCS
    )
      .setIncludeFolders(true)
      .setSelectFolderEnabled(false);

    const picker = new window.google.picker.PickerBuilder()
      .setDeveloperKey(API_KEY)
      .setOAuthToken(token)
      .addView(view)
      .setCallback(onPicked)
      .setTitle("Select Google Drive files")
      .build();

    picker.setVisible(true);
  };

  // -----------------------
  // PICKER CALLBACK
  // -----------------------
  const onPicked = async (data) => {
    if (data.action !== window.google.picker.Action.PICKED) return;
    const ids = (data.docs || []).map((d) => d.id);
    await doUpload(ids);
  };

  // -----------------------
  // UPLOAD HANDLER
  // -----------------------
  const doUpload = async (ids) => {
    setLoading(true);

    try {
      let res;

      // If agentId exists → upload into AGENT index
      if (agentId) {
        res = await uploadFilesToAgent(agentId, ids, jwt);
      } else {
        // Otherwise → upload into GLOBAL RAG index
        res = await downloadFiles(ids, jwt);
      }

      // Trigger UI refresh
      localStorage.setItem("docs_updated", Date.now());
      window.dispatchEvent(new Event("storage"));

      setModalPayload(res);
      setModalOpen(true);
    } catch (e) {
      alert("Upload failed: " + e.message);
    }

    setLoading(false);
  };

  return (
    <div style={{ padding: 20 }}>
      <h3>
        {agentId ? "Upload Documents to Agent" : "Upload Documents from Drive"}
      </h3>

      <button onClick={openPicker} style={{ marginBottom: 10 }}>
        Select from Google Drive
      </button>

      <Modal
        open={modalOpen}
        title={agentId ? "Agent Updated" : "Document Indexed"}
        onClose={() => setModalOpen(false)}
      >
        <div>
          <p>{modalPayload?.message}</p>

          <h4>Files processed:</h4>
          <ul>
            {(modalPayload?.uploaded ||
              modalPayload?.files_uploaded ||
              []).map((f, i) => (
              <li key={i}>{f.filename}</li>
            ))}
          </ul>
        </div>
      </Modal>

      {loading && <div>Processing…</div>}
    </div>
  );
}
