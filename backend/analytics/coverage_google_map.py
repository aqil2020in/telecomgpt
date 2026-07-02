"""Build Google Maps drive-route payload for coverage optimizer UI."""

from __future__ import annotations

from typing import Any

MILES_TO_METERS = 1609.344


def build_coverage_google_map_artifact(result: dict[str, Any]) -> dict[str, Any] | None:
    """Structured map data for Google Maps (frontend renders with NEXT_PUBLIC_GOOGLE_MAPS_API_KEY)."""
    if not result.get("ok"):
        return None

    c = result["center"]
    return {
        "type": "coverage_drive_map",
        "ok": True,
        "map_provider": "google",
        "title": f"Drive route map — {c['radius_miles']} mi radius",
        "source_csv": result.get("source"),
        "map_data": {
            "center": {"lat": c["lat"], "lng": c["lon"]},
            "radius_miles": c["radius_miles"],
            "radius_meters": round(c["radius_miles"] * MILES_TO_METERS, 1),
            "drive_route": result.get("drive_route") or [],
            "best_locations": result.get("best_measured") or [],
            "weak_zones": result.get("weak_zones") or [],
            "suggested_verify": result.get("suggested_verify") or [],
        },
    }
