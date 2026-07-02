import { useEffect, useRef, useState } from "react";

export type DriveMapPoint = {
  latitude: number;
  longitude: number;
  rf_score?: number;
  rsrp?: number;
  sinr?: number;
  rsrq?: number;
  distance_mi?: number;
  ssb_beam?: number | string;
  predicted_sinr_db?: number;
  confidence?: string;
};

export type CoverageDriveMapData = {
  center: { lat: number; lng: number };
  radius_miles: number;
  radius_meters: number;
  drive_route: DriveMapPoint[];
  best_locations: DriveMapPoint[];
  weak_zones: DriveMapPoint[];
  suggested_verify: DriveMapPoint[];
};

type CoverageDriveMapProps = {
  title?: string;
  data: CoverageDriveMapData;
};

type GoogleMaps = typeof google.maps;

let mapsScriptPromise: Promise<void> | null = null;

function loadGoogleMaps(apiKey: string): Promise<void> {
  if (typeof window !== "undefined" && (window as Window & { google?: { maps: GoogleMaps } }).google?.maps) {
    return Promise.resolve();
  }
  if (mapsScriptPromise) return mapsScriptPromise;

  mapsScriptPromise = new Promise((resolve, reject) => {
    const id = "google-maps-js";
    if (document.getElementById(id)) {
      const check = () => {
        if ((window as Window & { google?: { maps: GoogleMaps } }).google?.maps) resolve();
        else setTimeout(check, 50);
      };
      check();
      return;
    }
    const script = document.createElement("script");
    script.id = id;
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=geometry`;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Google Maps"));
    document.head.appendChild(script);
  });
  return mapsScriptPromise;
}

function mapsUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps?q=${lat},${lng}`;
}

function directionsUrl(origin: DriveMapPoint, dest: DriveMapPoint): string {
  return `https://www.google.com/maps/dir/?api=1&origin=${origin.latitude},${origin.longitude}&destination=${dest.latitude},${dest.longitude}&travelmode=driving`;
}

export default function CoverageDriveMap({ title, data }: CoverageDriveMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY?.trim() ?? "";

  useEffect(() => {
    if (!apiKey) {
      setError("Set NEXT_PUBLIC_GOOGLE_MAPS_API_KEY to show Google Maps drive routes.");
      return;
    }
    if (!mapRef.current) return;

    let cancelled = false;
    const overlays: Array<google.maps.Marker | google.maps.Polyline | google.maps.Circle> = [];

    (async () => {
      try {
        await loadGoogleMaps(apiKey);
        if (cancelled || !mapRef.current) return;

        const g = (window as Window & { google: { maps: GoogleMaps } }).google.maps;
        const map = new g.Map(mapRef.current, {
          center: data.center,
          zoom: 13,
          mapTypeId: "roadmap",
          streetViewControl: false,
          fullscreenControl: true,
        });

        new g.Circle({
          map,
          center: data.center,
          radius: data.radius_meters,
          strokeColor: "#6366f1",
          strokeOpacity: 0.9,
          strokeWeight: 2,
          fillColor: "#6366f1",
          fillOpacity: 0.06,
        });

        if (data.drive_route.length >= 2) {
          const path = data.drive_route.map((p) => ({ lat: p.latitude, lng: p.longitude }));
          overlays.push(
            new g.Polyline({
              map,
              path,
              strokeColor: "#475569",
              strokeOpacity: 0.95,
              strokeWeight: 4,
              geodesic: true,
            })
          );
          data.drive_route.forEach((p) => {
            overlays.push(
              new g.Marker({
                map,
                position: { lat: p.latitude, lng: p.longitude },
                icon: {
                  path: g.SymbolPath.CIRCLE,
                  scale: 4,
                  fillColor: "#94a3b8",
                  fillOpacity: 1,
                  strokeColor: "#fff",
                  strokeWeight: 1,
                },
                title: `RSRP ${p.rsrp ?? "—"} · SINR ${p.sinr ?? "—"}`,
              })
            );
          });
        }

        data.best_locations.slice(0, 5).forEach((p, i) => {
          overlays.push(
            new g.Marker({
              map,
              position: { lat: p.latitude, lng: p.longitude },
              label: { text: String(i + 1), color: "#fff", fontWeight: "700" },
              icon: {
                path: g.SymbolPath.CIRCLE,
                scale: 12,
                fillColor: "#16a34a",
                fillOpacity: 1,
                strokeColor: "#fff",
                strokeWeight: 2,
              },
              title: `Best #${i + 1} · score ${p.rf_score} · SINR ${p.sinr ?? "—"}`,
            })
          );
        });

        data.weak_zones.slice(0, 5).forEach((p) => {
          overlays.push(
            new g.Marker({
              map,
              position: { lat: p.latitude, lng: p.longitude },
              icon: {
                path: g.SymbolPath.CIRCLE,
                scale: 10,
                fillColor: "#dc2626",
                fillOpacity: 1,
                strokeColor: "#fff",
                strokeWeight: 2,
              },
              title: `Weak · score ${p.rf_score}`,
            })
          );
        });

        data.suggested_verify.forEach((p) => {
          overlays.push(
            new g.Marker({
              map,
              position: { lat: p.latitude, lng: p.longitude },
              icon: {
                path: g.SymbolPath.BACKWARD_CLOSED_ARROW,
                scale: 5,
                fillColor: "#2563eb",
                fillOpacity: 1,
                strokeColor: "#fff",
                strokeWeight: 1,
              },
              title: `Verify · pred SINR ${p.predicted_sinr_db ?? "—"} dB`,
            })
          );
        });

        overlays.push(
          new g.Marker({
            map,
            position: data.center,
            label: { text: "Site", color: "#5b21b6", fontWeight: "700" },
            icon: {
              path: g.SymbolPath.CIRCLE,
              scale: 11,
              fillColor: "#7c3aed",
              fillOpacity: 1,
              strokeColor: "#fff",
              strokeWeight: 2,
            },
            title: `Site center · ${data.radius_miles} mi radius`,
          })
        );

        const bounds = new g.LatLngBounds();
        bounds.extend(data.center);
        [...data.drive_route, ...data.best_locations, ...data.weak_zones, ...data.suggested_verify].forEach(
          (p) => bounds.extend({ lat: p.latitude, lng: p.longitude })
        );
        map.fitBounds(bounds, 48);

        if (!cancelled) setReady(true);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Map failed to load");
      }
    })();

    return () => {
      cancelled = true;
      overlays.forEach((o) => {
        if ("setMap" in o) o.setMap(null);
      });
    };
  }, [apiKey, data]);

  const top = data.best_locations[0];
  const routeStart = data.drive_route[0];

  return (
    <div
      style={{
        marginTop: 12,
        width: "100%",
        minWidth: 280,
        maxWidth: 900,
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

      {error ? (
        <div style={{ padding: 16, fontSize: 13, color: "#b45309", lineHeight: 1.5 }}>
          <p style={{ margin: "0 0 8px" }}>{error}</p>
          <p style={{ margin: 0, color: "#64748b" }}>
            Enable <strong>Maps JavaScript API</strong> in Google Cloud Console, add the key to Vercel as{" "}
            <code>NEXT_PUBLIC_GOOGLE_MAPS_API_KEY</code>, and redeploy.
          </p>
          {top && (
            <p style={{ margin: "10px 0 0" }}>
              <a href={mapsUrl(top.latitude, top.longitude)} target="_blank" rel="noreferrer">
                Open best UE location in Google Maps
              </a>
            </p>
          )}
        </div>
      ) : (
        <>
          <div ref={mapRef} style={{ width: "100%", height: 420, background: "#f1f5f9" }} />
          {!ready && (
            <div style={{ padding: 8, fontSize: 12, color: "#64748b", textAlign: "center" }}>
              Loading Google Maps…
            </div>
          )}
        </>
      )}

      <div
        style={{
          padding: "10px 12px",
          fontSize: 12,
          color: "#475569",
          borderTop: "1px solid #e5e7eb",
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          alignItems: "center",
        }}
      >
        <span>● Gray route = drive path</span>
        <span style={{ color: "#16a34a" }}>● Green #1–5 = best UE</span>
        <span style={{ color: "#dc2626" }}>● Red = weak</span>
        <span style={{ color: "#2563eb" }}>● Blue = verify</span>
        <span style={{ color: "#7c3aed" }}>● Purple = site</span>
        {top && routeStart && (
          <a
            href={directionsUrl(routeStart, top)}
            target="_blank"
            rel="noreferrer"
            style={{ marginLeft: "auto", color: "#2563eb", fontWeight: 600 }}
          >
            Driving directions: route start → best UE
          </a>
        )}
        {top && (
          <a href={mapsUrl(top.latitude, top.longitude)} target="_blank" rel="noreferrer" style={{ color: "#2563eb" }}>
            Open #1 in Google Maps
          </a>
        )}
      </div>
    </div>
  );
}
