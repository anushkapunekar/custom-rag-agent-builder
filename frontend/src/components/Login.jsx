import React, { useState } from "react";
import { authGoogleLoginUrl } from "../api/api.js";

export default function Login({ onToken }) {
  const [manual, setManual] = useState("");

  const handleOpenLogin = () => {
    // Open backend OAuth flow in a new tab/window
    window.open(authGoogleLoginUrl(), "_blank");
    alert(
      "A new window/tab opened for Google login. After completing the Google flow you'll see a JSON response containing access_token. Copy that value and paste it in the 'Paste token' box."
    );
  };

  const handlePasteToken = () => {
    if (!manual) return alert("Paste the token from /auth/google/callback response (access_token)");
    onToken(manual.trim());
  };

  return (
    <div className="panel">
      <h2>Login</h2>
      <p>
        Click <strong>Login with Google</strong> — a Google OAuth window will open. After successful sign-in
        you will see a JSON response showing the JWT (access_token). Copy that token and paste it below.
      </p>

      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={handleOpenLogin}>Login with Google</button>
      </div>

      <div style={{ marginTop: 12 }}>
        <label>Paste token (access_token) here:</label>
        <input value={manual} onChange={(e) => setManual(e.target.value)} placeholder="paste JWT here" />
        <div style={{ marginTop: 8 }}>
          <button onClick={handlePasteToken}>Use Token</button>
        </div>
      </div>
    </div>
  );
}
