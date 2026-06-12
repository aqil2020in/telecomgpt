import { useEffect, useRef } from "react";

type PlotlyChartProps = {
  plotlyJson: string;
  title?: string;
};

export default function PlotlyChart({ plotlyJson, title }: PlotlyChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mounted = true;
    const el = containerRef.current;
    if (!el) return;

    (async () => {
      const Plotly = await import("plotly.js-dist-min");
      if (!mounted || !containerRef.current) return;
      try {
        const fig = JSON.parse(plotlyJson);
        await Plotly.newPlot(
          containerRef.current,
          fig.data ?? [],
          { ...fig.layout, autosize: true, margin: { l: 48, r: 24, t: title ? 48 : 40, b: 48 } },
          { responsive: true, displayModeBar: false }
        );
        if (title && containerRef.current) {
          const layout = containerRef.current.querySelector(".gtitle");
          if (layout) layout.textContent = title;
        }
      } catch {
        containerRef.current.innerHTML =
          '<p style="color:#b00020;font-size:13px">Could not render chart.</p>';
      }
    })();

    return () => {
      mounted = false;
      if (el) {
        import("plotly.js-dist-min").then((Plotly) => {
          try {
            Plotly.purge(el);
          } catch {
            /* ignore */
          }
        });
      }
    };
  }, [plotlyJson, title]);

  return (
    <div
      style={{
        marginTop: 12,
        width: "100%",
        minWidth: 280,
        maxWidth: 640,
        background: "#fff",
        borderRadius: 8,
        border: "1px solid #e5e7eb",
        overflow: "hidden",
      }}
    >
      {title && (
        <div
          style={{
            padding: "8px 12px",
            fontSize: 13,
            fontWeight: 600,
            borderBottom: "1px solid #e5e7eb",
            color: "#374151",
          }}
        >
          {title}
        </div>
      )}
      <div ref={containerRef} style={{ width: "100%", height: 360 }} />
    </div>
  );
}
