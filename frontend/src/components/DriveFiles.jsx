// src/components/DriveFiles.jsx
import React, { useEffect, useState } from "react";
import Modal from "./Modal";
import { downloadFiles, listDocs } from "../api/api";

const API_KEY = import.meta.env.VITE_GOOGLE_API_KEY;

export default function DriveFiles({ jwt, gToken }) {
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

  // 🔥 Open Google Drive Picker
// snippet inside src/components/DriveFiles.jsx — replace openPicker/buildPicker section with this:

  // get token from props or localStorage
  function getGToken() {
    return gToken || localStorage.getItem("gToken") || localStorage.getItem("g_access_token");
  }

  const openPicker = () => {
    const token = getGToken();
    if (!API_KEY) return alert("Missing Google developer API key (VITE_GOOGLE_API_KEY).");
    if (!token) {
      return alert(
        "Missing Google Drive token. Make sure you have completed Google login and the backend callback stored the token. " +
        "If you just authorized, refresh the app once."
      );
    }

    // ensure gapi loaded
    if (!window.gapi || !window.google?.picker) {
      const script = document.createElement("script");
      script.src = "https://apis.google.com/js/api.js";
      script.onload = () => window.gapi.load("picker", () => buildPicker(token));
      document.body.appendChild(script);
      return;
    }

    window.gapi.load("picker", () => buildPicker(token));
  };

  const buildPicker = (token) => {
    const view = new window.google.picker.DocsView(window.google.picker.ViewId.DOCS)
      .setIncludeFolders(true)
      .setSelectFolderEnabled(false);

    const picker = new window.google.picker.PickerBuilder()
      .setDeveloperKey(API_KEY)
      .setOAuthToken(token)
      .addView(view)
      .setCallback(onPicked)
      .setTitle("Select Google Drive files to index")
      .build();

    picker.setVisible(true);
  };

  const onPicked = async (data) => {
    if (data.action !== window.google.picker.Action.PICKED) return;
    const ids = (data.docs || []).map((d) => d.id);
    await doDownload(ids);
  };

  // download + index
  const doDownload = async (ids) => {
    setLoading(true);
    try {
      const res = await downloadFiles(ids, jwt);

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
      <h3>Upload Documents from Google Drive</h3>

      <button onClick={openPicker} style={{ marginBottom: 10 }}>
        Select from Google Drive
      </button>

      <Modal open={modalOpen} title="Document Indexed" onClose={() => setModalOpen(false)}>
        <div>
          <p>{modalPayload?.message}</p>
          <h4>Files added:</h4>
          <ul>
            {(modalPayload?.files_uploaded || []).map((f, i) => (
              <li key={i}>{f.filename}</li>
            ))}
          </ul>
        </div>
      </Modal>

      {loading && <div>Processing…</div>}
    </div>
  );
}
