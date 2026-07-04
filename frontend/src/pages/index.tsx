import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import AttachReport, { type AttachReportData } from "../components/AttachReport";
import type { CoverageDriveMapData } from "../components/CoverageDriveMap";

const PlotlyChart = dynamic(() => import("../components/PlotlyChart"), { ssr: false });
const CoverageDriveMap = dynamic(() => import("../components/CoverageDriveMap"), { ssr: false });

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
  map_provider?: string;
  map_data?: CoverageDriveMapData;
  attach_report?: AttachReportData;
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
  async?: boolean;
  job_id?: string;
  status?: string;
  error?: string;
  message?: string;
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function isCoverageOptimizerQuery(text: string): boolean {
  const t = text.toLowerCase();
  return (
    t.includes("coverage optimizer") ||
    t.includes("best ue location") ||
    t.includes("drive route map") ||
    (/\d+\.\d{4,}\s*,\s*-?\d+\.\d{4,}/.test(text) &&
      (t.includes("mile") || t.includes("radius") || t.includes("coverage")))
  );
}

async function pollJob(jobId: string, onStatus?: (s: string) => void): Promise<AskResponse> {
  const deadline = Date.now() + 8 * 60_000;
  while (Date.now() < deadline) {
    const res = await fetch(`${API_URL}/api/jobs/${jobId}`);
    const data: AskResponse = await res.json();
    if (!res.ok) {
      throw new Error((data as { detail?: string }).detail ?? `Job poll failed (${res.status})`);
    }
    if (data.status) onStatus?.(data.status);
    if (data.status === "completed") return data;
    if (data.status === "failed") {
      throw new Error(data.error ?? "Background job failed");
    }
    await sleep(2000);
  }
  throw new Error("Background job timed out after 8 minutes. Check Render logs and retry.");
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [attachLoading, setAttachLoading] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [showTrace, setShowTrace] = useState(false);
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const attachLogRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    const wake = async () => {
      try {
        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), 90_000);
        const r = await fetch(`${API_URL}/api/health`, { method: "GET", signal: controller.signal });
        window.clearTimeout(timer);
        setApiReady(r.ok);
      } catch {
        setApiReady(false);
      }
    };
    wake();
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
    setJobStatus(null);

    try {
      if (apiReady === false) {
        await fetch(`${API_URL}/api/health`, { method: "GET" });
      }

      const controller = new AbortController();
      const askTimeoutMs = isCoverageOptimizerQuery(text) ? 90_000 : 60_000;
      const timer = window.setTimeout(() => controller.abort(), askTimeoutMs);

      let res: Response;
      if (isCoverageOptimizerQuery(text)) {
        const params = new URLSearchParams({
          q: text,
          session_id: sessionId ?? "default",
        });
        res = await fetch(`${API_URL}/api/rf/coverage-optimizer?${params.toString()}`, {
          method: "GET",
          signal: controller.signal,
        });
      } else {
        res = await fetch(`${API_URL}/ask`, {
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
      }
      window.clearTimeout(timer);
      let data: AskResponse = await res.json();
      if (!res.ok) {
        throw new Error((data as { detail?: string }).detail ?? (data as { error?: string }).error ?? `Request failed (${res.status})`);
      }

      if (!isCoverageOptimizerQuery(text) && data.async && data.job_id) {
        setJobStatus(data.status ?? "queued");
        data = await pollJob(data.job_id, setJobStatus);
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
            ? "Could not start the request in time. The server may be waking up — wait 60s and try again."
            : e.message.includes("fetch") || e.name === "TypeError"
              ? `Could not reach the API at ${API_URL}. The server may be waking up — wait 30s and try again.`
              : e.message
          : "Could not reach the API. Wait a moment and try again.";
      setError(msg);
      setMessages(messages);
    } finally {
      setLoading(false);
      setJobStatus(null);
    }
  };

  const runAttachReport = async (file?: File, sessionOverride?: string) => {
    setAttachLoading(true);
    setError("");
    try {
      const sid = sessionOverride ?? sessionId ?? "default";
      const form = new FormData();
      form.append("session_id", sid);
      if (file) form.append("file", file);
      form.append("generate_exports", "1");
      const res = await fetch(`${API_URL}/api/nr-sa/attach-report`, { method: "POST", body: form });
      const data: AttachReportData = await res.json();
      if (!res.ok || data.ok === false) {
        if (!file) {
          attachLogRef.current?.click();
          return;
        }
        throw new Error(data.error ?? "Attach report failed");
      }
      if (data.filename && file) {
        setSessionId(sid);
      }
      const overall = data.overall ?? "UNKNOWN";
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `**NR SA Attach Report** — ${overall} (${data.passed}/${data.total} steps)`,
          artifacts: [{ type: "attach_report", ok: true, attach_report: data, filename: data.filename }],
        },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Attach report failed");
    } finally {
      setAttachLoading(false);
      if (attachLogRef.current) attachLogRef.current.value = "";
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
      const isLog = /\.(log|txt)$/i.test(data.filename ?? file.name);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: isLog
            ? `Uploaded **${data.filename}** (${data.size_bytes} bytes). Running attach report…`
            : `Uploaded **${data.filename}** (${data.size_bytes} bytes). Ask me to analyze this drive-test CSV or log file.`,
        },
      ]);
      if (isLog) {
        await runAttachReport(undefined, data.session_id ?? sessionId ?? "default");
      }
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
    if (a.type === "coverage_drive_map" && a.ok && a.map_data) {
      return (
        <CoverageDriveMap
          key={`gmap-${j}`}
          title={a.title ?? "Drive route map — Google Maps"}
          data={a.map_data}
        />
      );
    }
    if (a.type === "attach_report" && a.attach_report) {
      return <AttachReport key={`attach-${j}`} data={a.attach_report} apiUrl={API_URL} sessionId={sessionId} />;
    }
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
      if (a.plotly_json) {
        return (
          <PlotlyChart
            key={`map-${j}`}
            plotlyJson={a.plotly_json}
            title={a.title ?? "Drive route map"}
          />
        );
      }
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
          XYZ Network Intelligence Copilot — TNIC RCA · coverage · attach · fault analysis
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
              <li>Root cause analysis — call drop, throughput, HO, RACH</li>
              <li>Fault analysis RRC fail (HARQ / K1 / RV)</li>
              <li>Coverage optimizer — upload CSV first for Google Maps route</li>
              <li>Upload log → NR SA attach report</li>
              <li>What is n78? What is PRACH?</li>
              <li>Validate NR SA registration test case</li>
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
                  m.artifacts?.some(
                    (a) => a.type === "chart" || a.type === "map" || a.type === "coverage_drive_map"
                  )
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
            {jobStatus === "running"
              ? "Running multi-agent pipeline…"
              : jobStatus === "queued"
                ? "Queued — waiting for worker…"
                : "Starting…"}
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
            "Root cause analysis call drop",
            "Root cause low throughput",
            "Fault analysis RRC fail",
            "Coverage optimizer 3 mile radius",
            "Explain NR protocol stack C-plane vs U-plane",
            "Validate NR SA registration",
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
          <button
            type="button"
            disabled={attachLoading || loading}
            onClick={() => runAttachReport()}
            title="NR SA Initial Attach report (session log or pick file)"
            style={{
              padding: "4px 12px",
              fontSize: 12,
              borderRadius: 999,
              border: "1px solid #7c3aed",
              background: attachLoading ? "#ede9fe" : "#f5f3ff",
              color: "#5b21b6",
              cursor: attachLoading || loading ? "default" : "pointer",
              fontWeight: 600,
            }}
          >
            {attachLoading ? "Analyzing…" : "📋 Attach Report"}
          </button>
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
            ref={attachLogRef}
            type="file"
            accept=".log,.txt"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) runAttachReport(f);
            }}
          />
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
