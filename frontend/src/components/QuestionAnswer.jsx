import React from "react";

export default function QuestionAnswer({ answer, sources }) {
  if (!answer) return null;
  return (
    <div style={{ marginTop: 16 }}>
      <h4>Answer</h4>
      <div style={{ whiteSpace: "pre-wrap", border: "1px solid #eee", padding: 12, borderRadius: 6 }}>{answer}</div>

      {sources && sources.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <h5>Sources</h5>
          <ol>
            {sources.map((s, i) => (
              <li key={i}>
                <strong>{s.filename || s.docId}</strong> — score: {s.score.toFixed(3)}
                <div style={{ fontSize: 13, color: "#333" }}>{s.text?.slice(0, 300)}{s.text?.length > 300 ? "…" : ""}</div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
