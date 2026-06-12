"""Extended specialist agents — drive-test, logs, prediction, compliance, spec, compare, verifier, deploy, eval."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..loaders import TelecomDB
    from ..tools import ToolRegistry


def run_drive_test_agent(query: str, tools: "ToolRegistry", session_id: str = "default") -> dict:
    from pathlib import Path

    uploads = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / session_id
    paths = list(uploads.glob("*.csv")) if uploads.exists() else []
    from analytics.kaggle_charts import pick_csv_path, build_kaggle_dashboard
    from analytics.rf_map import build_rf_map_artifacts

    path = str(paths[0]) if paths else str(pick_csv_path(query) or "")
    if not path:
        return {"agent": "drive_test", "content": "No CSV found. Upload a drive-test file or download Kaggle datasets.", "artifacts": []}

    rules = tools.run("run_drive_test_rules", path=path)
    dash = build_kaggle_dashboard(query, csv_path=path)
    maps = build_rf_map_artifacts(path)
    artifacts = list(dash.get("charts") or []) + maps
    lines = [f"**Drive-test analysis:** `{Path(path).name}`"]
    if rules.ok:
        lines.append(f"SLA overall: **{rules.output.get('overall')}**")
        for r in rules.output.get("rules", []):
            lines.append(f"  • {r['rule']}: {r['fail_pct']}% fail ({r['threshold']})")
    return {"agent": "drive_test", "content": "\n".join(lines), "artifacts": artifacts, "tool_calls": [{"tool": "drive_test"}]}


def run_log_agent(query: str, tools: "ToolRegistry", session_id: str = "default") -> dict:
    from pathlib import Path

    uploads = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / session_id
    log_paths = []
    if uploads.exists():
        log_paths = list(uploads.glob("*.log")) + list(uploads.glob("*.txt"))
    content_parts = []
    artifacts = []
    for p in log_paths[:1]:
        r = tools.run("analyze_log", path=str(p))
        if r.ok:
            s = r.output
            content_parts.append(
                f"**Log analysis:** {p.name}\n"
                f"Levels: {s.get('level_counts')}\n"
                f"Top errors: {s.get('top_errors', [])[:3]}"
            )
            if s.get("level_counts"):
                from analytics.charts import level_counts_chart
                artifacts.append({
                    "type": "chart", "ok": True, "title": "Log levels",
                    "plotly_json": level_counts_chart(s["level_counts"]).to_json(),
                })
    if not content_parts:
        content_parts.append("Upload a `.log` or `.txt` UE/QXDM file to analyze. Generic parser detects INFO/WARN/ERROR and RRC/NAS keywords.")
    return {"agent": "log", "content": "\n".join(content_parts), "artifacts": artifacts}


def run_prediction_agent(query: str, tools: "ToolRegistry") -> dict:
    from analytics.kaggle_charts import pick_csv_path
    from analytics.csv_tools import load_csv_path, detect_rf_columns
    import pandas as pd

    path = pick_csv_path(query)
    if not path:
        return {"agent": "prediction", "content": "No KPI CSV available for prediction.", "artifacts": []}

    df = load_csv_path(str(path))
    rf = detect_rf_columns(df)
    tp = rf.get("throughput")
    rsrp = rf.get("rsrp")
    lines = [f"**Prediction lite** on `{path.name}` ({len(df)} rows)"]
    artifacts = []

    if tp and rsrp and pd.api.types.is_numeric_dtype(df[tp]) and pd.api.types.is_numeric_dtype(df[rsrp]):
        sub = df[[rsrp, tp]].dropna().tail(500)
        if len(sub) > 10:
            mean_tp = sub[tp].mean()
            trend = sub[tp].iloc[-20:].mean() - sub[tp].iloc[:20].mean()
            lines.append(f"Avg throughput: {mean_tp:.1f} Mbps")
            lines.append(f"Recent trend (last vs first 20): {trend:+.1f} Mbps")
            lines.append(f"RSRP correlation: {sub[rsrp].corr(sub[tp]):.2f}")
            try:
                from analytics.charts import chart_from_csv
                artifacts.append({
                    "type": "chart", "ok": True, "title": "Throughput vs RSRP (prediction view)",
                    "plotly_json": chart_from_csv(sub, chart_type="scatter", x=rsrp, y=tp),
                })
            except Exception:
                pass
    else:
        lines.append("Need numeric RSRP + throughput columns for trend prediction.")

    return {"agent": "prediction", "content": "\n".join(lines), "artifacts": artifacts}


def run_compliance_agent(query: str, db: "TelecomDB", tools: "ToolRegistry") -> dict:
    band = tools.run("lookup_bands", query=query)
    fcc = db.db.get("fcc", {})
    lines = ["**Compliance / regulatory**"]
    if band.ok:
        lines.append(str(band.output)[:1500])
    if fcc:
        lines.append(f"FCC licensed NR (sample): {fcc.get('licensed', [])[:8]}")
    return {"agent": "compliance", "content": "\n".join(lines)}


def run_spec_agent(query: str, tools: "ToolRegistry", session_id: str = "default") -> dict:
    r = tools.run("hybrid_search", query=query, session_id=session_id, k=6)
    if not r.ok:
        return {"agent": "spec", "content": "", "sources": []}
    ctx, cites = r.output if isinstance(r.output, tuple) else (str(r.output), [])
    ql = query.lower()
    prefix = "**3GPP / spec research**\n"
    if "38." in ql or "36." in ql:
        prefix = f"**3GPP TS reference search**\n"
    return {"agent": "spec", "content": prefix + ctx[:3500], "sources": cites}


def run_comparison_agent(query: str, db: "TelecomDB", tools: "ToolRegistry") -> dict:
    comp = db.answer_comparison(query)
    dev = tools.run("compare_devices", query=query)
    parts = []
    if comp:
        parts.append(f"**Technology comparison**\n{comp}")
    if dev.ok and dev.output and "Could not find" not in str(dev.output):
        parts.append(f"**Device comparison**\n{dev.output}")
    return {"agent": "comparison", "content": "\n\n".join(parts) if parts else ""}


def run_verifier_agent(query: str, answer: str, agent_outputs: list[dict], db: "TelecomDB") -> dict:
    """Cross-check synthesizer draft against KB agent outputs."""
    if not answer:
        return {"agent": "verifier", "content": answer, "verified": False}

    kb_text = " ".join(
        o.get("content", "") for o in agent_outputs if o.get("agent") in ("telecom_kb", "compliance", "comparison")
    )
    issues = []
    for band in ("n78", "n77", "n41", "b66"):
        if band in query.lower() and band in kb_text.lower() and band not in answer.lower():
            issues.append(f"Answer may be missing band {band} from KB.")

    if issues:
        note = "\n\n*(Verifier note: " + "; ".join(issues) + ")*"
        return {"agent": "verifier", "content": answer + note, "verified": False, "issues": issues}
    return {"agent": "verifier", "content": answer, "verified": True, "issues": []}


def run_deploy_agent() -> dict:
    import os
    from telecom_ai.reasoning import _ollama_reachable

    return {
        "agent": "deploy",
        "content": (
            "**System status**\n"
            f"• Mode: {os.environ.get('TELECOMGPT_MODE', 'orchestrator')}\n"
            f"• OpenAI configured: {bool(os.environ.get('OPENAI_API_KEY'))}\n"
            f"• Ollama reachable: {_ollama_reachable()}\n"
            f"• API: https://telecomgpt.onrender.com\n"
            f"• UI: https://telecomgpt.vercel.app"
        ),
    }


def run_eval_agent(db: "TelecomDB") -> dict:
    from telecom_ai.core import TelecomAI
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent.parent / "data" / "telecom_master_db.json"
    ai = TelecomAI(str(p))
    cases = ["What is n78?", "What is PRACH?", "Does the S23 support CA?"]
    results = []
    for q in cases:
        r = ai.run(q)
        results.append({"query": q, "ok": bool(r and len(r) > 20), "len": len(r or "")})
    passed = sum(1 for x in results if x["ok"])
    return {
        "agent": "eval",
        "content": f"**Eval smoke test:** {passed}/{len(cases)} passed\n" + "\n".join(f"• {x['query']}: {'OK' if x['ok'] else 'FAIL'}" for x in results),
        "eval_results": results,
    }
