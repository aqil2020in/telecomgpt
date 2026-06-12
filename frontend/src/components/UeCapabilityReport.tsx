import { useState } from "react";

type ExportLink = {
  ok?: boolean;
  filename?: string;
  download_url?: string;
  error?: string;
};

type UeCapStep = {
  id?: string;
  label?: string;
  direction?: string;
  status?: string;
  note?: string;
  optional?: boolean;
};

type UeCapField = {
  field?: string;
  status?: string;
};

export type UeCapabilityReportData = {
  ok?: boolean;
  overall?: string;
  procedure_passed?: number;
  procedure_total?: number;
  filename?: string;
  steps?: UeCapStep[];
  fields?: UeCapField[];
  bands_detected?: string[];
  segmentation?: boolean;
  first_missing?: UeCapStep | null;
  alerts?: string[];
  pitfalls?: string[];
  troubleshooting?: { symptom?: string; checks?: string[] }[];
  references?: string[];
  spec_refs?: string[];
  exports?: {
    xlsx?: ExportLink;
    pdf?: ExportLink;
  };
  error?: string;
};

const STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  COMPLETE: { bg: "#dcfce7", color: "#166534", label: "Capa exchange complete" },
  PARTIAL: { bg: "#fef3c7", color: "#92400e", label: "Partial capa procedure" },
  FIELDS_ONLY: { bg: "#e0e7ff", color: "#3730a3", label: "IE hints only" },
  NOT_DETECTED: { bg: "#fee2e2", color: "#991b1b", label: "Not detected" },
};

export default function UeCapabilityReport({
  data,
  apiUrl,
  sessionId,
}: {
  data: UeCapabilityReportData;
  apiUrl: string;
  sessionId?: string | null;
}) {
  if (data.error || data.ok === false) {
    return (
      <div style={{ marginTop: 12, padding: 12, background: "#fef2f2", borderRadius: 8, fontSize: 14 }}>
        {data.error ?? "UE Capability report failed"}
      </div>
    );
  }

  const overall = data.overall ?? "UNKNOWN";
  const style = STATUS_STYLE[overall] ?? STATUS_STYLE.NOT_DETECTED;
  const fieldsFound = (data.fields ?? []).filter((f) => f.status === "found").map((f) => f.field);
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
      const res = await fetch(`${apiUrl}/api/nr/ue-capability/report/export`, { method: "POST", body: form });
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
          <strong style={{ fontSize: 15 }}>NR UE Capability</strong>
          <span style={{ marginLeft: 8, fontWeight: 600 }}>{style.label}</span>
          {data.filename && (
            <div style={{ fontSize: 12, opacity: 0.85, marginTop: 2 }}>{data.filename}</div>
          )}
        </div>
        <div style={{ fontWeight: 700, fontSize: 18 }}>
          {data.procedure_passed}/{data.procedure_total}
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
              <th style={{ padding: "6px 16px", fontWeight: 600 }}>Step</th>
              <th style={{ padding: "6px 8px", fontWeight: 600 }}>Direction</th>
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
                <td style={{ padding: "6px 16px" }}>{s.label}</td>
                <td style={{ padding: "6px 8px", color: "#64748b" }}>{s.direction ?? "—"}</td>
                <td style={{ padding: "6px 16px", textAlign: "center" }}>
                  {s.status === "found" ? (
                    <span style={{ color: "#16a34a", fontWeight: 700 }}>✓</span>
                  ) : s.status === "optional" ? (
                    <span style={{ color: "#94a3b8" }}>~</span>
                  ) : (
                    <span style={{ color: "#dc2626", fontWeight: 700 }}>✗</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(fieldsFound.length > 0 || (data.bands_detected?.length ?? 0) > 0) && (
        <div style={{ padding: "10px 16px", borderTop: "1px solid #e2e8f0", fontSize: 13 }}>
          {fieldsFound.length > 0 && (
            <div>
              <strong>IE hints:</strong> {fieldsFound.join(", ")}
            </div>
          )}
          {data.bands_detected && data.bands_detected.length > 0 && (
            <div style={{ marginTop: 4 }}>
              <strong>Bands in log:</strong> {data.bands_detected.join(", ")}
            </div>
          )}
          {data.segmentation && (
            <div style={{ marginTop: 4, color: "#92400e" }}>
              RRC segmentation detected (9000 byte PDCP SDU limit)
            </div>
          )}
        </div>
      )}

      {data.first_missing && overall !== "COMPLETE" && (
        <div style={{ padding: "12px 16px", background: "#fef2f2", borderTop: "1px solid #fecaca" }}>
          <strong style={{ color: "#991b1b" }}>First gap:</strong> {data.first_missing.label}
          {data.first_missing.note && (
            <div style={{ marginTop: 4, color: "#7f1d1d", fontSize: 13 }}>{data.first_missing.note}</div>
          )}
        </div>
      )}

      {data.troubleshooting && data.troubleshooting.length > 0 && overall !== "COMPLETE" && (
        <details style={{ padding: "10px 16px", borderTop: "1px solid #e2e8f0", fontSize: 13 }}>
          <summary style={{ cursor: "pointer", color: "#2563eb" }}>Troubleshooting guide</summary>
          {data.troubleshooting.map((t, i) => (
            <div key={i} style={{ marginTop: 8 }}>
              <strong>{t.symptom}</strong>
              <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                {(t.checks ?? []).map((c, j) => (
                  <li key={j}>{c}</li>
                ))}
              </ul>
            </div>
          ))}
        </details>
      )}

      {data.references && data.references.length > 0 && (
        <div style={{ padding: "10px 16px", borderTop: "1px solid #e2e8f0", fontSize: 12 }}>
          {data.references.map((url, i) => (
            <a
              key={i}
              href={url}
              target="_blank"
              rel="noreferrer"
              style={{ display: "block", color: "#2563eb" }}
            >
              ShareTechnote — UE Capability
            </a>
          ))}
          {data.spec_refs && data.spec_refs.length > 0 && (
            <div style={{ marginTop: 4, color: "#64748b" }}>Specs: {data.spec_refs.join(", ")}</div>
          )}
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
          ? downloadBtn("Download Excel", `${apiUrl}${data.exports.xlsx.download_url}`, "#0d9488")
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
          ? downloadBtn("Download PDF", `${apiUrl}${data.exports.pdf.download_url}`, "#dc2626")
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
