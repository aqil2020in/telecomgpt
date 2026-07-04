"""Knowledge graph — complaint → KPI → fault → root cause → recommendation."""

from __future__ import annotations

from typing import Any

from app.models.schemas import KnowledgeGraph, KnowledgeGraphEdge, KnowledgeGraphNode, RuleFinding


def build_knowledge_graph(
    *,
    complaint: str,
    issue_type: str,
    kpis: dict[str, Any],
    findings: list[RuleFinding],
    actions: list[str],
) -> KnowledgeGraph:
    nodes: list[KnowledgeGraphNode] = []
    edges: list[KnowledgeGraphEdge] = []

    cid = "complaint_1"
    nodes.append(KnowledgeGraphNode(id=cid, type="complaint", label=(complaint or issue_type)[:80]))

    kpi_node_ids: list[str] = []
    for i, (k, v) in enumerate(list(kpis.items())[:8]):
        kid = f"kpi_{i}"
        nodes.append(KnowledgeGraphNode(id=kid, type="kpi", label=f"{k}={v}"))
        edges.append(KnowledgeGraphEdge(source=cid, target=kid, relation="observed_kpi"))
        kpi_node_ids.append(kid)

    issue_id = f"issue_{issue_type}"
    nodes.append(KnowledgeGraphNode(id=issue_id, type="fault", label=issue_type.replace("_", " ").title()))
    edges.append(KnowledgeGraphEdge(source=cid, target=issue_id, relation="triaged_to"))

    for i, f in enumerate(findings[:3]):
        rc_id = f"rca_{i}"
        nodes.append(KnowledgeGraphNode(id=rc_id, type="root_cause", label=f.probable_cause[:100]))
        edges.append(KnowledgeGraphEdge(source=issue_id, target=rc_id, relation="probable_cause"))
        if kpi_node_ids:
            edges.append(KnowledgeGraphEdge(source=kpi_node_ids[0], target=rc_id, relation="supports"))

    for i, action in enumerate(actions[:3]):
        rec_id = f"rec_{i}"
        nodes.append(KnowledgeGraphNode(id=rec_id, type="recommendation", label=action[:100]))
        if findings:
            edges.append(KnowledgeGraphEdge(source=f"rca_{min(i, len(findings)-1)}", target=rec_id, relation="recommends"))

    return KnowledgeGraph(nodes=nodes, edges=edges)
