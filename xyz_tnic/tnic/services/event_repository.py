"""Event repository — persist normalized events and upload manifests."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tnic.config import get_settings
from tnic.models.normalized_event import NormalizedEvent
from tnic.models.upload_models import UploadManifest


def uploads_root() -> Path:
    root = get_settings().data_dir / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _index_path() -> Path:
    return uploads_root() / "index.json"


def _load_index() -> list[dict[str, Any]]:
    p = _index_path()
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def _save_index(entries: list[dict[str, Any]]) -> None:
    _index_path().write_text(json.dumps(entries, indent=2), encoding="utf-8")


def create_upload_dir(filename: str) -> tuple[str, Path]:
    upload_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    dest = uploads_root() / upload_id
    dest.mkdir(parents=True, exist_ok=True)
    return upload_id, dest


def save_upload_file(upload_id: str, filename: str, content: bytes) -> Path:
    dest = uploads_root() / upload_id / Path(filename).name
    dest.write_bytes(content)
    return dest


def save_events(upload_id: str, events: list[NormalizedEvent]) -> Path:
    dest = uploads_root() / upload_id / "events.jsonl"
    with dest.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev.to_dict()) + "\n")
    return dest


def save_manifest(upload_id: str, manifest: UploadManifest) -> Path:
    dest = uploads_root() / upload_id / "manifest.json"
    dest.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    entries = _load_index()
    entries = [e for e in entries if e.get("upload_id") != upload_id]
    entries.insert(0, manifest.model_dump())
    _save_index(entries[:200])
    return dest


def load_manifest(upload_id: str) -> UploadManifest | None:
    p = uploads_root() / upload_id / "manifest.json"
    if not p.exists():
        return None
    return UploadManifest.model_validate_json(p.read_text(encoding="utf-8"))


def load_events(
    upload_id: str,
    *,
    cell_id: str | None = None,
    ue_id: str | None = None,
    failures_only: bool = False,
) -> list[NormalizedEvent]:
    p = uploads_root() / upload_id / "events.jsonl"
    if not p.exists():
        return []
    events: list[NormalizedEvent] = []
    cid = cell_id.upper() if cell_id else None
    uid = ue_id.upper() if ue_id else None
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = NormalizedEvent.model_validate(json.loads(line))
        if cid and ev.cell_id and ev.cell_id != cid:
            continue
        if uid and ev.ue_id and ev.ue_id != uid:
            continue
        if failures_only and not ev.is_failure():
            continue
        events.append(ev)
    return events


def list_uploads(limit: int = 50) -> list[UploadManifest]:
    entries = _load_index()[:limit]
    out: list[UploadManifest] = []
    for e in entries:
        try:
            out.append(UploadManifest.model_validate(e))
        except Exception:
            continue
    return out


def get_stored_file_path(upload_id: str) -> Path | None:
    folder = uploads_root() / upload_id
    if not folder.exists():
        return None
    for p in folder.iterdir():
        if p.name not in ("events.jsonl", "manifest.json") and p.is_file():
            return p
    return None
