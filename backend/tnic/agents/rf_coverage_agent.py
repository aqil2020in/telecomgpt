"""RF Coverage Agent — 3-mile Google Maps drive-test analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tnic.services.coverage_google_map import build_coverage_google_map_artifact
from tnic.services.coverage_optimizer import (
    DEFAULT_RADIUS_MI,
    optimize_coverage,
    parse_geo_from_query,
)


@dataclass
class RFCoverageDiagnosis:
    """Structured RF coverage drive-test diagnosis."""

    issue_class: str
    root_cause: str
    confidence: float
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    map_artifact: dict[str, Any] | None = None
    optimization: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_class": self.issue_class,
            "root_cause": self.root_cause,
            "confidence": round(self.confidence, 2),
            "summary": self.summary,
            "metrics": self.metrics,
            "evidence": self.evidence,
            "recommendations": self.recommendations,
            "map_artifact": self.map_artifact,
        }


class RFCoverageAgent:
    """Analyzes geospatial drive-test CSV within a 3-mile site radius."""

    name = "rf_coverage_agent"

    def analyze_drive_test(
        self,
        query: str = "",
        csv_path: str | Path | None = None,
        center_lat: float | None = None,
        center_lon: float | None = None,
        radius_miles: float | None = None,
    ) -> RFCoverageDiagnosis:
        lat, lon, radius = parse_geo_from_query(query)
        if center_lat is not None:
            lat = center_lat
        if center_lon is not None:
            lon = center_lon
        if radius_miles is not None:
            radius = radius_miles

        result = optimize_coverage(
            csv_path,
            center_lat=lat,
            center_lon=lon,
            radius_miles=radius or DEFAULT_RADIUS_MI,
        )
        if not result.get("ok"):
            return RFCoverageDiagnosis(
                issue_class="No Data",
                root_cause=result.get("error", "Drive-test analysis failed."),
                confidence=0.0,
                summary=result.get("error", "No data"),
                optimization=result,
            )

        return self._diagnose(result)

    def analyze(self, kpis: dict[str, Any], query: str = "") -> RFCoverageDiagnosis:
        csv_path = kpis.get("drive_test_csv") or kpis.get("csv_path")
        return self.analyze_drive_test(
            query=query,
            csv_path=csv_path,
            center_lat=kpis.get("center_lat"),
            center_lon=kpis.get("center_lon"),
            radius_miles=kpis.get("radius_miles"),
        )

    def _diagnose(self, result: dict[str, Any]) -> RFCoverageDiagnosis:
        weak = result.get("weak_zones") or []
        holes = result.get("coverage_holes") or []
        best = result.get("best_measured") or []
        mix = result.get("coverage_status_mix") or {}
        hole_count = int(mix.get("Coverage_Hole", 0))
        poor_count = int(mix.get("Poor", 0) + mix.get("Fair", 0))
        points = int(result.get("points_in_radius") or 0)

        if hole_count > points * 0.15:
            issue = "Coverage Hole Cluster"
            root = (
                f"Drive-test within {result['center']['radius_miles']} mi shows "
                f"{hole_count} coverage-hole samples ({round(100*hole_count/max(points,1),1)}%) — "
                "geo gaps between sectors/beams require tilt or small-cell fill."
            )
            confidence = min(0.92, 0.72 + hole_count / max(points, 1))
        elif len(weak) >= 5:
            issue = "Weak RF Zones"
            root = (
                f"{len(weak)} weak zones (RF score < 40 or RSRP < −108 dBm) inside "
                f"{result['center']['radius_miles']}-mile cluster — edge/clutter degradation."
            )
            confidence = 0.85
        else:
            issue = "Acceptable Coverage"
            root = (
                f"Drive-test within {result['center']['radius_miles']} mi is generally healthy; "
                "focus retest on suggested verify coordinates."
            )
            confidence = 0.70

        evidence = [
            f"Samples in radius: {points} ({result.get('unique_locations')} unique locations)",
            f"Coverage status mix: {mix}",
            f"Best location RF score: {best[0]['rf_score'] if best else '—'} "
            f"at {best[0]['latitude']}, {best[0]['longitude']}" if best else "No best location",
            f"Weak zones identified: {len(weak)}",
            f"Coverage holes tagged: {len(holes)}",
        ]
        if best:
            evidence.append(
                f"Top SINR {best[0].get('sinr', '—')} dB · RSRP {best[0].get('rsrp', '—')} dBm"
            )

        recommendations = [
            "Open Google Maps drive route — green = best UE test locations, red = weak zones",
            "Retest at top-ranked lat/lon before cluster-wide parameter changes",
            "Investigate coverage holes with beam/azimuth overlay and clutter map",
        ]
        if weak:
            recommendations.append("Audit tilt/power on sectors serving weak-zone coordinates")
        if result.get("suggested_verify"):
            recommendations.append("Drive suggested verify points (blue markers) to confirm IDW predictions")

        map_artifact = build_coverage_google_map_artifact(result)
        summary = (
            f"RF drive-test: {points} samples in {result['center']['radius_miles']} mi · "
            f"{len(best)} best · {len(weak)} weak · {len(holes)} holes"
        )

        return RFCoverageDiagnosis(
            issue_class=issue,
            root_cause=root,
            confidence=round(confidence, 2),
            summary=summary,
            metrics={
                "center_lat": result["center"]["lat"],
                "center_lon": result["center"]["lon"],
                "radius_miles": result["center"]["radius_miles"],
                "points_in_radius": points,
                "weak_zone_count": len(weak),
                "coverage_hole_count": hole_count,
                "poor_fair_count": poor_count,
            },
            evidence=evidence,
            recommendations=recommendations,
            map_artifact=map_artifact,
            optimization=result,
        )


def analyze_rf_coverage(
    query: str = "",
    csv_path: str | Path | None = None,
    radius_miles: float = DEFAULT_RADIUS_MI,
) -> dict[str, Any]:
    """Convenience API for RF coverage drive-test RCA + Google Maps artifact."""
    return RFCoverageAgent().analyze_drive_test(
        query=query, csv_path=csv_path, radius_miles=radius_miles
    ).to_dict()
