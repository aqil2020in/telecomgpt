import { useEffect, useRef, useState } from "react";

function apiBaseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_API_URL ?? "https://telecomgpt.onrender.com";
  const first = raw.trim().split(/\s+/)[0];
  return first.replace(/\/+$/, "");
}

const API_URL = apiBaseUrl();

type Message = { role: "user" | "assistant"; content: string };

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: text,
          history: messages,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? `Request failed (${res.status})`);
      }
      setMessages([
        ...nextMessages,
        { role: "assistant", content: data.answer ?? "(empty response)" },
      ]);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not reach the API. Wait a moment and try again."
      );
      setMessages(messages);
    } finally {
      setLoading(false);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        maxWidth: 820,
        margin: "0 auto",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <header style={{ padding: "16px 20px", borderBottom: "1px solid #e0e0e0" }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>TelecomGPT</h1>
        <p style={{ margin: "4px 0 0", color: "#666", fontSize: 14 }}>
          Chat about 5G NR, LTE, bands, devices, and RF engineering
        </p>
      </header>

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px 20px",
          background: "#fafafa",
        }}
      >
        {messages.length === 0 && !loading && (
          <div style={{ color: "#888", fontSize: 14, lineHeight: 1.6 }}>
            <p>Try asking:</p>
            <ul>
              <li>What is the difference between LTE and 5G?</li>
              <li>What is n78?</li>
              <li>Does the S23 support n77+n78 CA?</li>
              <li>What is PRACH?</li>
            </ul>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: m.role === "user" ? "flex-end" : "flex-start",
              marginBottom: 12,
            }}
          >
            <div
              style={{
                maxWidth: "85%",
                padding: "12px 16px",
                borderRadius: 12,
                background: m.role === "user" ? "#2563eb" : "#fff",
                color: m.role === "user" ? "#fff" : "#111",
                border: m.role === "assistant" ? "1px solid #e0e0e0" : "none",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                lineHeight: 1.5,
                fontSize: 15,
              }}
            >
              {m.content}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ color: "#666", fontSize: 14, marginBottom: 12 }}>
            Thinking…
          </div>
        )}

        {error && (
          <p style={{ color: "#b00020", fontSize: 14 }} role="alert">
            {error}
          </p>
        )}
        <div ref={bottomRef} />
      </div>

      <footer
        style={{
          padding: "12px 20px 20px",
          borderTop: "1px solid #e0e0e0",
          background: "#fff",
        }}
      >
        <div style={{ display: "flex", gap: 8 }}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            placeholder="Ask a question… (Enter to send, Shift+Enter for new line)"
            style={{
              flex: 1,
              resize: "none",
              padding: 12,
              borderRadius: 8,
              border: "1px solid #ccc",
              fontSize: 15,
              boxSizing: "border-box",
            }}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            style={{
              padding: "0 20px",
              borderRadius: 8,
              border: "none",
              background: loading || !input.trim() ? "#94a3b8" : "#2563eb",
              color: "#fff",
              cursor: loading || !input.trim() ? "default" : "pointer",
              fontWeight: 600,
            }}
          >
            Send
          </button>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => {
              setMessages([]);
              setError("");
            }}
            style={{
              marginTop: 8,
              background: "none",
              border: "none",
              color: "#666",
              cursor: "pointer",
              fontSize: 13,
              textDecoration: "underline",
            }}
          >
            Clear chat
          </button>
        )}
      </footer>
    </main>
  );
}
