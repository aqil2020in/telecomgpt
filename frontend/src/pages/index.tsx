import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";

const PlotlyChart = dynamic(() => import("../components/PlotlyChart"), { ssr: false });

function apiBaseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_API_URL ?? "https://telecomgpt.onrender.com";
  const first = raw.trim().split(/\s+/)[0];
  return first.replace(/\/+$/, "");
}

const API_URL = apiBaseUrl();

type Artifact = {
  type?: string;
  ok?: boolean;
  filename?: string;
  download_url?: string;
  slides?: number;
  title?: string;
  plotly_json?: string;
  chart_type?: string;
  source_csv?: string;
  geojson?: object;
  point_count?: number;
};

type Source = {
  title?: string;
  url?: string;
  source?: string;
  snippet?: string;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  artifacts?: Artifact[];
  sources?: Source[];
  trace?: {
    steps?: string[];
    plan?: { agents?: string[]; agent_categories?: Record<string, string> };
    workflow_tasks?: { agent: string; status: string; category?: string }[];
    guardrail_issues?: string[];
    confidence?: number;
  };
};

type AskResponse = {
  answer?: string;
  session_id?: string;
  artifacts?: Artifact[];
  sources?: Source[];
  steps?: string[];
  plan?: { agents?: string[]; agent_categories?: Record<string, string> };
  confidence?: number;
  workflow_tasks?: { agent: string; status: string; category?: string }[];
  guardrail_issues?: string[];
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [showTrace, setShowTrace] = useState(false);
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    fetch(`${API_URL}/api/health`, { method: "GET" })
      .then((r) => setApiReady(r.ok))
      .catch(() => setApiReady(false));
  }, []);

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
      if (apiReady === false) {
        await fetch(`${API_URL}/api/health`, { method: "GET" });
      }

      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), 120_000);

      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: text,
          history: messages,
          session_id: sessionId,
          trace: showTrace,
        }),
        signal: controller.signal,
      });
      window.clearTimeout(timer);
      const data: AskResponse = await res.json();
      if (!res.ok) {
        throw new Error((data as { detail?: string }).detail ?? `Request failed (${res.status})`);
      }
      if (data.session_id) setSessionId(data.session_id);
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: data.answer ?? "(empty response)",
          artifacts: data.artifacts,
          sources: data.sources,
          trace: showTrace
            ? {
                steps: data.steps,
                plan: data.plan,
                workflow_tasks: data.workflow_tasks,
                guardrail_issues: data.guardrail_issues,
                confidence: data.confidence,
              }
            : undefined,
        },
      ]);
    } catch (e) {
      const msg =
        e instanceof Error
          ? e.name === "AbortError"
            ? "The request timed out after 2 minutes. Try a shorter question like “What is n78?” or wait and retry."
            : e.message.includes("fetch") || e.name === "TypeError"
              ? `Could not reach the API at ${API_URL}. The server may be waking up — wait 30s and try again.`
              : e.message
          : "Could not reach the API. Wait a moment and try again.";
      setError(msg);
      setMessages(messages);
    } finally {
      setLoading(false);
    }
  };

  const uploadFile = async (file: File) => {
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("session_id", sessionId ?? "default");
      const res = await fetch(`${API_URL}/api/upload`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error ?? "Upload failed");
      }
      if (data.session_id) setSessionId(data.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Uploaded **${data.filename}** (${data.size_bytes} bytes). Ask me to analyze this drive-test CSV or log file.`,
        },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const renderArtifact = (a: Artifact, j: number) => {
    if (a.type === "chart" && a.ok && a.plotly_json) {
      return (
        <PlotlyChart
          key={`chart-${j}`}
          plotlyJson={a.plotly_json}
          title={a.title ?? a.source_csv}
        />
      );
    }
    if (a.type === "map" && a.ok) {
      return (
        <div key={`map-${j}`} style={{ marginTop: 10, fontSize: 13, color: "#475569" }}>
          RF map: {a.point_count ?? 0} GPS points
          {a.title ? ` — ${a.title}` : ""}
        </div>
      );
    }
    if (a.ok && a.download_url) {
      const isExcel = a.type === "excel" || a.filename?.endsWith(".xlsx");
      return (
        <div key={`dl-${j}`} style={{ marginTop: 10 }}>
          <a
            href={`${API_URL}${a.download_url}`}
            download={a.filename}
            style={{
              display: "inline-block",
              padding: "8px 14px",
              background: isExcel ? "#0d9488" : "#059669",
              color: "#fff",
              borderRadius: 6,
              textDecoration: "none",
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            Download {a.filename ?? (isExcel ? "report.xlsx" : "report.pptx")}
            {a.slides ? ` (${a.slides} slides)` : ""}
          </a>
        </div>
      );
    }
    return null;
  };

  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        maxWidth: 900,
        margin: "0 auto",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <header style={{ padding: "16px 20px", borderBottom: "1px solid #e0e0e0" }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>TelecomGPT</h1>
        <p style={{ margin: "4px 0 0", color: "#666", fontSize: 14 }}>
          LangGraph hub — hybrid CrewAI + AutoGen · layered memory · guardrails
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
        {apiReady === false && (
          <p style={{ color: "#b45309", fontSize: 13, marginBottom: 8 }}>
            API waking up or unreachable — first request may take up to a minute on Render.
          </p>
        )}

        {messages.length === 0 && !loading && (
          <div style={{ color: "#888", fontSize: 14, lineHeight: 1.6 }}>
            <p>Try asking:</p>
            <ul>
              <li>Chart the 5G KPI Kaggle dataset</li>
              <li>Upload a drive-test CSV, then ask for RF map + SLA rules</li>
              <li>Generate a PowerPoint report on 5G network slicing</li>
              <li>Compare S23 vs S24 CA support</li>
              <li>What is n78? What is PRACH?</li>
              <li>Run eval smoke test</li>
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
                maxWidth:
                  m.role === "assistant" &&
                  m.artifacts?.some((a) => a.type === "chart" || a.type === "map")
                    ? "95%"
                    : "85%",
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
              {m.role === "assistant" && m.artifacts?.map(renderArtifact)}
              {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                <details style={{ marginTop: 10, fontSize: 13 }}>
                  <summary style={{ cursor: "pointer", color: "#2563eb" }}>
                    Sources ({m.sources.length})
                  </summary>
                  <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                    {m.sources.slice(0, 8).map((s, k) => (
                      <li key={k}>
                        {s.url ? (
                          <a href={s.url} target="_blank" rel="noreferrer">
                            {s.title ?? s.source ?? s.url}
                          </a>
                        ) : (
                          s.title ?? s.snippet?.slice(0, 80) ?? "Reference"
                        )}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {m.role === "assistant" && m.trace && (
                <details style={{ marginTop: 8, fontSize: 12, color: "#64748b" }}>
                  <summary style={{ cursor: "pointer" }}>Agent trace</summary>
                  {m.trace.confidence != null && (
                    <p style={{ margin: "4px 0" }}>Confidence: {m.trace.confidence}</p>
                  )}
                  {m.trace.plan?.agents && (
                    <p style={{ margin: "4px 0" }}>
                      Plan: {m.trace.plan.agents.join(" → ")}
                    </p>
                  )}
                  {m.trace.plan?.agent_categories && (
                    <p style={{ margin: "4px 0", fontSize: 11 }}>
                      {Object.entries(m.trace.plan.agent_categories)
                        .map(([a, c]) => `${a}(${c})`)
                        .join(", ")}
                    </p>
                  )}
                  {m.trace.workflow_tasks && m.trace.workflow_tasks.length > 0 && (
                    <ul style={{ margin: "4px 0", paddingLeft: 16 }}>
                      {m.trace.workflow_tasks.map((t, k) => (
                        <li key={k}>
                          {t.agent} [{t.category ?? "agent"}] — {t.status}
                        </li>
                      ))}
                    </ul>
                  )}
                  {m.trace.guardrail_issues && m.trace.guardrail_issues.length > 0 && (
                    <p style={{ margin: "4px 0", color: "#b45309" }}>
                      Guardrails: {m.trace.guardrail_issues.join(", ")}
                    </p>
                  )}
                  {m.trace.steps && (
                    <p style={{ margin: 0 }}>{m.trace.steps.join(" · ")}</p>
                  )}
                </details>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ color: "#666", fontSize: 14, marginBottom: 12 }}>
            Running multi-agent pipeline…
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
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8, alignItems: "center" }}>
          {[
            "Chart 5G KPI dataset",
            "Compare S23 vs S24",
            "Run eval smoke test",
          ].map((label) => (
            <button
              key={label}
              type="button"
              disabled={loading}
              onClick={() => setInput(label)}
              style={{
                padding: "4px 10px",
                fontSize: 12,
                borderRadius: 999,
                border: "1px solid #cbd5e1",
                background: "#f8fafc",
                cursor: loading ? "default" : "pointer",
              }}
            >
              {label}
            </button>
          ))}
          <label style={{ fontSize: 12, marginLeft: 8, display: "flex", alignItems: "center", gap: 4 }}>
            <input
              type="checkbox"
              checked={showTrace}
              onChange={(e) => setShowTrace(e.target.checked)}
            />
            Show agent trace
          </label>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.log,.txt"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) uploadFile(f);
            }}
          />
          <button
            type="button"
            disabled={uploading || loading}
            onClick={() => fileRef.current?.click()}
            title="Upload CSV or log"
            style={{
              padding: "10px 12px",
              borderRadius: 8,
              border: "1px solid #cbd5e1",
              background: "#f8fafc",
              cursor: uploading || loading ? "default" : "pointer",
              fontSize: 18,
            }}
          >
            {uploading ? "…" : "📎"}
          </button>
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
              setSessionId(null);
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
