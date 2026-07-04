"""Re-export RF Coverage Agent from backend.agents package."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agents.rf_coverage_agent import (  # noqa: E402
    CoverageScoreCalculator,
    RFCoverageAgent,
    analyze_rf_coverage,
    build_hotspots_df,
    classify_row,
    detect_beam_coverage_gaps,
    detect_cell_edge_regions,
    detect_coverage_holes,
    detect_high_bler_zones,
    detect_interference_regions,
    detect_latency_hotspots,
    detect_low_sinr_zones,
    detect_throughput_degradation_zones,
    detect_weak_coverage_zones,
    geospatial_dataset_path,
    get_coverage_hotspots,
    get_coverage_summary,
    load_geospatial_df,
)

__all__ = [
    "CoverageScoreCalculator",
    "RFCoverageAgent",
    "analyze_rf_coverage",
    "build_hotspots_df",
    "classify_row",
    "detect_beam_coverage_gaps",
    "detect_cell_edge_regions",
    "detect_coverage_holes",
    "detect_high_bler_zones",
    "detect_interference_regions",
    "detect_latency_hotspots",
    "detect_low_sinr_zones",
    "detect_throughput_degradation_zones",
    "detect_weak_coverage_zones",
    "geospatial_dataset_path",
    "get_coverage_hotspots",
    "get_coverage_summary",
    "load_geospatial_df",
]
