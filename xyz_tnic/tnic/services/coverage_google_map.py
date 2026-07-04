"""Google Maps HTML and artifacts for RF coverage drive-test maps."""

from __future__ import annotations

import json
import os
from typing import Any

MILES_TO_METERS = 1609.344


def build_coverage_google_map_artifact(result: dict[str, Any]) -> dict[str, Any] | None:
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
            "coverage_holes": result.get("coverage_holes") or [],
            "suggested_verify": result.get("suggested_verify") or [],
        },
    }


def google_maps_api_key() -> str:
    return (
        os.environ.get("GOOGLE_MAPS_API_KEY")
        or os.environ.get("NEXT_PUBLIC_GOOGLE_MAPS_API_KEY")
        or ""
    ).strip()


def render_google_maps_html(map_data: dict[str, Any], *, height: int = 560) -> str:
    """Embed Google Maps with drive route, best/weak markers, and 3 mi radius circle."""
    api_key = google_maps_api_key()
    center = map_data.get("center") or {"lat": 32.937, "lng": -96.984}
    radius_m = map_data.get("radius_meters") or 4828
    payload = json.dumps(map_data)

    if not api_key:
        return f"""
        <div style="font-family:sans-serif;padding:16px;background:#fef3c7;border-radius:8px;">
          <strong>Google Maps API key not set.</strong>
          Set <code>GOOGLE_MAPS_API_KEY</code> or <code>NEXT_PUBLIC_GOOGLE_MAPS_API_KEY</code>.
          <p>Center: {center['lat']:.5f}, {center['lng']:.5f} · Radius: {map_data.get('radius_miles', 3)} mi</p>
          <p>Best locations: {len(map_data.get('best_locations') or [])} ·
             Weak zones: {len(map_data.get('weak_zones') or [])} ·
             Route points: {len(map_data.get('drive_route') or [])}</p>
        </div>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <style>#map {{ height: {height}px; width: 100%; border-radius: 8px; }}</style>
</head>
<body>
  <div id="map"></div>
  <script>
    const mapData = {payload};
    function initMap() {{
      const center = mapData.center;
      const map = new google.maps.Map(document.getElementById('map'), {{
        zoom: 13,
        center: center,
        mapTypeId: 'roadmap',
      }});
      new google.maps.Circle({{
        strokeColor: '#4338ca',
        strokeOpacity: 0.8,
        strokeWeight: 2,
        fillColor: '#6366f1',
        fillOpacity: 0.08,
        map,
        center,
        radius: {radius_m},
      }});
      new google.maps.Marker({{
        position: center,
        map,
        title: 'Site center',
        icon: 'http://maps.google.com/mapfiles/ms/icons/purple-dot.png',
      }});
      const route = (mapData.drive_route || []).map(p => ({{lat: p.latitude, lng: p.longitude}}));
      if (route.length > 1) {{
        new google.maps.Polyline({{
          path: route,
          geodesic: true,
          strokeColor: '#64748b',
          strokeOpacity: 0.85,
          strokeWeight: 3,
          map,
        }});
      }}
      (mapData.best_locations || []).forEach((p, i) => {{
        new google.maps.Marker({{
          position: {{lat: p.latitude, lng: p.longitude}},
          map,
          title: 'Best #' + (i+1) + ' score ' + p.rf_score,
          icon: 'http://maps.google.com/mapfiles/ms/icons/green-dot.png',
        }});
      }});
      (mapData.weak_zones || []).forEach(p => {{
        new google.maps.Marker({{
          position: {{lat: p.latitude, lng: p.longitude}},
          map,
          title: 'Weak zone score ' + p.rf_score,
          icon: 'http://maps.google.com/mapfiles/ms/icons/red-dot.png',
        }});
      }});
      (mapData.coverage_holes || []).forEach(p => {{
        new google.maps.Marker({{
          position: {{lat: p.latitude, lng: p.longitude}},
          map,
          title: 'Coverage hole',
          icon: 'http://maps.google.com/mapfiles/ms/icons/orange-dot.png',
        }});
      }});
      (mapData.suggested_verify || []).forEach(p => {{
        new google.maps.Marker({{
          position: {{lat: p.latitude, lng: p.longitude}},
          map,
          title: 'Suggested verify SINR ' + p.predicted_sinr_db,
          icon: 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png',
        }});
      }});
    }}
  </script>
  <script async defer
    src="https://maps.googleapis.com/maps/api/js?key={api_key}&callback=initMap"></script>
</body>
</html>
"""
