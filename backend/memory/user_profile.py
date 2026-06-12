"""Per-session user profile (bands, devices, role)."""

from __future__ import annotations

import json
import re
from pathlib import Path

_PROFILE_DIR = Path(__file__).resolve().parent.parent / "data" / "memory" / "profiles"


class UserProfile:
    def __init__(self, session_id: str = "default") -> None:
        self.session_id = session_id
        _PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self.path = _PROFILE_DIR / f"{session_id}.json"

    def load(self) -> dict:
        if not self.path.exists():
            return {"session_id": self.session_id, "bands": [], "devices": [], "notes": ""}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"session_id": self.session_id, "bands": [], "devices": [], "notes": ""}

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def update_from_query(self, query: str) -> dict:
        data = self.load()
        ql = query.lower()
        for m in re.finditer(r"\bn(\d{1,3})\b", ql):
            band = m.group(1)
            if band not in data["bands"]:
                data["bands"].append(band)
        for dev in ("s23", "s24", "s25", "iphone 16", "iphone 17", "pixel"):
            if dev in ql and dev not in data["devices"]:
                data["devices"].append(dev)
        if "i work on" in ql or "my device" in ql:
            data["notes"] = query[:300]
        self.save(data)
        return data

    def context_line(self) -> str:
        p = self.load()
        parts = []
        if p.get("bands"):
            parts.append(f"User bands: {', '.join(p['bands'])}")
        if p.get("devices"):
            parts.append(f"User devices: {', '.join(p['devices'])}")
        if p.get("notes"):
            parts.append(f"Notes: {p['notes'][:200]}")
        return " | ".join(parts)
