import { useState } from "react";

function apiBaseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_API_URL ?? "https://telecomgpt.onrender.com";
  // Vercel env vars pasted with newlines break fetch — use first URL only.
  const first = raw.trim().split(/\s+/)[0];
  return first.replace(/\/+$/, "");
}

const API_URL = apiBaseUrl();

export default function Home() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const ask = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setAnswer("");
    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? `Request failed (${res.status})`);
      }
      setAnswer(data.answer ?? "(empty response)");
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not reach the API. The Render backend may be waking up — wait 30s and try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <h1>TelecomGPT</h1>
      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        rows={4}
        style={{ width: "100%", boxSizing: "border-box" }}
        placeholder='Try: "What is n78?" or "Does the S23 support n77+n78 CA?"'
      />
      <button onClick={ask} disabled={loading || !query.trim()}>
        {loading ? "Asking…" : "Ask"}
      </button>
      {error && (
        <p style={{ marginTop: 16, color: "#b00020" }} role="alert">
          {error}
        </p>
      )}
      {answer && (
        <pre
          style={{
            marginTop: 16,
            padding: 16,
            background: "#f5f5f5",
            color: "#111",
            borderRadius: 8,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {answer}
        </pre>
      )}
    </main>
  );
}
