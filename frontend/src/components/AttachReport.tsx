import { useState } from "react";

type AttachStep = {
  id?: string;
  phase?: string;
  label?: string;
  status?: "found" | "missing";
  fail_hint?: string;
};

type ExportLink = {
  ok?: boolean;
  filename?: string;
  download_url?: string;
  error?: string;
};

type AttachReportData = {
  ok?: boolean;
  overall?: string;
  passed?: number;
  total?: number;
  filename?: string;
  steps?: AttachStep[];
  first_missing?: AttachStep | null;
  alerts?: string[];
  references?: string[];
  exports?: {
    xlsx?: ExportLink;
    pdf?: ExportLink;
  };
  log_summary?: {
    total_lines?: number;
    error_count?: number;
    level_counts?: Record<string, number>;
    top_errors?: { message?: string; count?: number }[];
  };
  error?: string;
};

const STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  COMPLETE: { bg: "#dcfce7", color: "#166534", label: "Complete attach" },
  PARTIAL: { bg: "#fef3c7", color: "#92400e", label: "Partial attach" },
  IN_PROGRESS: { bg: "#dbeafe", color: "#1e40af", label: "In progress" },
  NOT_DETECTED: { bg: "#fee2e2", color: "#991b1b", label: "Not detected" },
};

export default function AttachReport({
  data,
  apiUrl,
  sessionId,
}: {
  data: AttachReportData;
  apiUrl: string;
  sessionId?: string | null;
}) {
  if (data.error || data.ok === false) {
    return (
      <div style={{ marginTop: 12, padding: 12, background: "#fef2f2", borderRadius: 8, fontSize: 14 }}>
        {data.error ?? "Attach report failed"}
      </div>
    );
  }

  const overall = data.overall ?? "UNKNOWN";
  const style = STATUS_STYLE[overall] ?? STATUS_STYLE.NOT_DETECTED;
  const pct = data.total ? Math.round(((data.passed ?? 0) / data.total) * 100) : 0;
  const [exporting, setExporting] = useState<string | null>(null);

  const downloadBtn = (label: string, href: string, bg: string) => (
    <a
      href={href}
      download
      style={{
        display: "inline-block",
        padding: "6px 12px",
        background: bg,
        color: "#fff",
        borderRadius: 6,
        textDecoration: "none",
        fontSize: 13,
        fontWeight: 600,
      }}
    >
      {label}
    </a>
  );

  const requestExport = async (format: "xlsx" | "pdf") => {
    setExporting(format);
    try {
      const form = new FormData();
      form.append("session_id", sessionId ?? "default");
      form.append("format", format);
      const res = await fetch(`${apiUrl}/api/nr-sa/attach-report/export`, { method: "POST", body: form });
      const out = await res.json();
      const link = format === "xlsx" ? out.xlsx : out.pdf;
      if (link?.ok && link.download_url) {
        window.open(`${apiUrl}${link.download_url}`, "_blank");
      }
    } finally {
      setExporting(null);
    }
  };

  return (
    <div
      style={{
        marginTop: 12,
        border: "1px solid #e2e8f0",
        borderRadius: 10,
        overflow: "hidden",
        fontSize: 14,
      }}
    >
      <div
        style={{
          padding: "12px 16px",
          background: style.bg,
          color: style.color,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div>
          <strong style={{ fontSize: 15 }}>NR SA Initial Attach</strong>
          <span style={{ marginLeft: 8, fontWeight: 600 }}>{style.label}</span>
          {data.filename && (
            <div style={{ fontSize: 12, opacity: 0.85, marginTop: 2 }}>{data.filename}</div>
          )}
        </div>
        <div style={{ fontWeight: 700, fontSize: 18 }}>
          {data.passed}/{data.total}
        </div>
      </div>

      <div style={{ padding: "8px 16px", background: "#f8fafc" }}>
        <div
          style={{
            height: 6,
            borderRadius: 3,
            background: "#e2e8f0",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: "100%",
              background: overall === "COMPLETE" ? "#22c55e" : overall === "PARTIAL" ? "#f59e0b" : "#ef4444",
              transition: "width 0.3s",
            }}
          />
        </div>
      </div>

      {data.alerts && data.alerts.length > 0 && (
        <div style={{ padding: "10px 16px", background: "#fff7ed", borderBottom: "1px solid #fed7aa" }}>
          {data.alerts.map((a, i) => (
            <div key={i} style={{ color: "#9a3412", fontSize: 13, marginBottom: i < data.alerts!.length - 1 ? 4 : 0 }}>
              ⚠ {a}
            </div>
          ))}
        </div>
      )}

      <div style={{ padding: "8px 0" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#f1f5f9", textAlign: "left" }}>
              <th style={{ padding: "6px 16px", fontWeight: 600 }}>Phase</th>
              <th style={{ padding: "6px 8px", fontWeight: 600 }}>Step</th>
              <th style={{ padding: "6px 16px", fontWeight: 600, width: 48 }}>OK</th>
            </tr>
          </thead>
          <tbody>
            {(data.steps ?? []).map((s, i) => (
              <tr
                key={s.id ?? i}
                style={{
                  borderTop: "1px solid #f1f5f9",
                  background: s.status === "missing" && data.first_missing?.id === s.id ? "#fef2f2" : undefined,
                }}
              >
                <td style={{ padding: "6px 16px", color: "#64748b" }}>{s.phase}</td>
                <td style={{ padding: "6px 8px" }}>{s.label}</td>
                <td style={{ padding: "6px 16px", textAlign: "center" }}>
                  {s.status === "found" ? (
                    <span style={{ color: "#16a34a", fontWeight: 700 }}>✓</span>
                  ) : (
                    <span style={{ color: "#dc2626", fontWeight: 700 }}>✗</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.first_missing && overall !== "COMPLETE" && (
        <div style={{ padding: "12px 16px", background: "#fef2f2", borderTop: "1px solid #fecaca" }}>
          <strong style={{ color: "#991b1b" }}>First gap:</strong>{" "}
          {data.first_missing.label}
          {data.first_missing.fail_hint && (
            <div style={{ marginTop: 4, color: "#7f1d1d", fontSize: 13 }}>{data.first_missing.fail_hint}</div>
          )}
        </div>
      )}

      {data.log_summary && (
        <div style={{ padding: "10px 16px", borderTop: "1px solid #e2e8f0", fontSize: 12, color: "#64748b" }}>
          {data.log_summary.total_lines?.toLocaleString()} lines
          {data.log_summary.error_count != null && ` · ${data.log_summary.error_count} errors`}
          {data.log_summary.level_counts && (
            <> · {Object.entries(data.log_summary.level_counts).map(([k, v]) => `${k}:${v}`).join(" ")}</>
          )}
        </div>
      )}

      {data.references && data.references.length > 0 && (
        <div style={{ padding: "10px 16px", borderTop: "1px solid #e2e8f0", fontSize: 12 }}>
          {data.references.map((url, i) => (
            <a
              key={i}
              href={url}
              target="_blank"
              rel="noreferrer"
              style={{ display: "block", color: "#2563eb", marginBottom: 2 }}
            >
              {url.includes("sharetechnote") ? "ShareTechnote — Initial Attach" : "Amarisoft SA Log Analysis"}
            </a>
          ))}
        </div>
      )}

      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid #e2e8f0",
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          alignItems: "center",
        }}
      >
        {data.exports?.xlsx?.ok && data.exports.xlsx.download_url
          ? downloadBtn(
              "Download Excel",
              `${apiUrl}${data.exports.xlsx.download_url}`,
              "#0d9488",
            )
          : (
            <button
              type="button"
              disabled={!!exporting}
              onClick={() => requestExport("xlsx")}
              style={{
                padding: "6px 12px",
                background: "#0d9488",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                cursor: exporting ? "default" : "pointer",
              }}
            >
              {exporting === "xlsx" ? "Exporting…" : "Download Excel"}
            </button>
          )}
        {data.exports?.pdf?.ok && data.exports.pdf.download_url
          ? downloadBtn(
              "Download PDF",
              `${apiUrl}${data.exports.pdf.download_url}`,
              "#dc2626",
            )
          : (
            <button
              type="button"
              disabled={!!exporting}
              onClick={() => requestExport("pdf")}
              style={{
                padding: "6px 12px",
                background: "#dc2626",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                cursor: exporting ? "default" : "pointer",
              }}
            >
              {exporting === "pdf" ? "Exporting…" : "Download PDF"}
            </button>
          )}
      </div>
    </div>
  );
}

export type { AttachReportData };
