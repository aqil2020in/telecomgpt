"""TelecomAI — multi-agent orchestrator over TelecomDB knowledge layer."""

from __future__ import annotations

import os

from .graph import build_graph, initial_state as legacy_initial_state
from .loaders import TelecomDB
from .orchestrator import build_orchestrator_graph, initial_state as orch_initial_state


class TelecomAI:
    def __init__(self, db_path: str):
        self.db = TelecomDB(db_path)
        self._use_orchestrator = os.environ.get("TELECOMGPT_MODE", "orchestrator") != "legacy"
        self._graph = None

    @property
    def graph(self):
        if self._graph is None:
            self._graph = (
                build_orchestrator_graph(self.db)
                if self._use_orchestrator
                else build_graph(self.db)
            )
        return self._graph

    def run(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
        session_id: str | None = None,
    ) -> str:
        return self.run_with_trace(query, history=history, session_id=session_id)["answer"]

    def run_with_trace(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
        session_id: str | None = None,
    ) -> dict:
        if self._use_orchestrator:
            state = orch_initial_state(query, history, session_id)
            result = self.graph.invoke(state)
            return {
                "answer": result.get("answer") or "",
                "session_id": result.get("session_id"),
                "plan": result.get("plan"),
                "active_agent": result.get("active_agent"),
                "steps": result.get("steps") or [],
                "sources": result.get("sources") or [],
                "artifacts": result.get("artifacts") or [],
                "confidence": result.get("confidence"),
                "needs_clarification": result.get("needs_clarification"),
                "workflow_tasks": result.get("workflow_tasks") or [],
                "guardrail_issues": result.get("guardrail_issues") or [],
                "memory_context": result.get("memory_context"),
                "mode": "orchestrator",
            }
        result = self.graph.invoke(legacy_initial_state(query, history))
        return {
            "answer": result.get("answer") or "",
            "intent": result.get("intent"),
            "steps": result.get("steps") or [],
            "sources": result.get("sources") or [],
            "mode": "legacy",
        }

    def list_tools(self) -> list[dict]:
        from .tools import build_tool_registry

        return build_tool_registry(self.db).list_specs()

    def run_fast(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
        session_id: str | None = None,
    ) -> dict:
        """Fast grounded path — KB shortcuts, BM25 RAG + LLM, no full graph."""
        import uuid

        from .guardrails import check_input, check_output
        from .reasoning import llm_answer_with_sources

        pre = check_input(query)
        if not pre["allowed"]:
            return {
                "answer": pre["message"],
                "session_id": session_id or "default",
                "sources": [],
                "mode": "fast",
                "guardrail_issues": pre.get("issues") or [],
            }

        q = pre.get("redacted_query") or query
        sid = session_id or str(uuid.uuid4())[:12]

        from analytics.coverage_optimizer import (
            build_coverage_map_artifacts,
            explain_coverage_optimizer,
            looks_like_coverage_optimizer_query,
            optimize_coverage,
            parse_geo_from_query,
        )

        if looks_like_coverage_optimizer_query(q):
            from pathlib import Path

            plat, plon, pradius = parse_geo_from_query(q)
            uploads = Path(__file__).resolve().parent.parent / "data" / "uploads" / sid
            csv_path = ""
            if uploads.exists():
                csvs = sorted(uploads.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
                if csvs:
                    csv_path = str(csvs[0])
            if not csv_path:
                sample = Path(__file__).resolve().parent.parent / "data" / "samples" / "coverage_dallas_3mi.csv"
                csv_path = str(sample) if sample.exists() else ""
            md = explain_coverage_optimizer(q, csv_path=csv_path or None, session_id=sid)
            artifacts: list = []
            if csv_path:
                result = optimize_coverage(csv_path, center_lat=plat, center_lon=plon, radius_miles=pradius)
                artifacts = build_coverage_map_artifacts(result) if result.get("ok") else []
            post = check_output(md)
            answer = post.get("filtered_answer") or md
            return {
                "answer": answer,
                "session_id": sid,
                "sources": [],
                "artifacts": artifacts,
                "mode": "fast-kb",
                "guardrail_issues": list(pre.get("issues") or []) + list(post.get("issues") or []),
            }

        instant = self._instant_answer(q)
        if instant:
            post = check_output(instant)
            answer = post.get("filtered_answer") or instant
            return {
                "answer": answer,
                "session_id": sid,
                "sources": [],
                "artifacts": [],
                "mode": "fast-kb",
                "guardrail_issues": list(pre.get("issues") or []) + list(post.get("issues") or []),
            }

        answer, sources = llm_answer_with_sources(
            q, self.db, history=history, fast=True
        )
        post = check_output(answer or "")
        answer = post.get("filtered_answer") or answer or ""

        return {
            "answer": answer,
            "session_id": sid,
            "sources": sources or [],
            "artifacts": [],
            "mode": "fast",
            "guardrail_issues": list(pre.get("issues") or []) + list(post.get("issues") or []),
        }

    def _instant_answer(self, query: str) -> str:
        """Cheap TelecomDB lookups — no LLM, no vector/Chroma."""
        from analytics.harq_rrc_fault import explain_rrc_harq_fault, looks_like_rrc_harq_fault_query
        from tnic.bridge import looks_like_tnic_rca_query, run_tnic_rca_markdown
        from .loaders import looks_like_phy_math

        if looks_like_rrc_harq_fault_query(query):
            return explain_rrc_harq_fault(query)

        if looks_like_tnic_rca_query(query):
            return run_tnic_rca_markdown(query)

        from analytics.coverage_optimizer import (
            explain_coverage_optimizer,
            looks_like_coverage_optimizer_query,
        )

        if looks_like_coverage_optimizer_query(query):
            return explain_coverage_optimizer(query)

        db = self.db
        checks = (
            db.glossary_lookup,
            db.answer_band_regulatory,
            db.answer_ca_endc_nrdc,
        )
        for fn in checks:
            try:
                hit = fn(query)
            except Exception:
                hit = ""
            if hit:
                return hit
        if looks_like_phy_math(query):
            try:
                return db.answer_phy_math(query) or ""
            except Exception:
                pass
        return ""
