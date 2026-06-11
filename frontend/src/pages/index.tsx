import { useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "https://telecomgpt-api.onrender.com";

export default function Home() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const ask = async () => {
    const res = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    setAnswer(data.answer);
  };
  return (
    <main style={{ padding: 24 }}>
      <h1>TelecomGPT</h1>
      <textarea
        value={query}
        onChange={e => setQuery(e.target.value)}
        rows={4}
        style={{ width: "100%" }}
      />
      <button onClick={ask}>Ask</button>
      <pre style={{ marginTop: 16 }}>{answer}</pre>
    </main>
  );
}
