"""Session memory — persist conversation turns per session."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_SESSION_DIR = Path(__file__).resolve().parent.parent / "data" / "memory" / "sessions"


class SessionMemory:
    def __init__(self, session_id: str = "default") -> None:
        self.session_id = session_id
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        self.path = _SESSION_DIR / f"{session_id}.json"

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def save_turn(self, role: str, content: str, metadata: dict | None = None) -> None:
        turns = self.load()
        turns.append(
            {
                "role": role,
                "content": content,
                "ts": datetime.now(timezone.utc).isoformat(),
                **(metadata or {}),
            }
        )
        self.path.write_text(json.dumps(turns[-100:], indent=2), encoding="utf-8")

    def summary_context(self, max_turns: int = 10) -> str:
        turns = self.load()[-max_turns:]
        if not turns:
            return ""
        lines = [f"{t['role']}: {t['content'][:500]}" for t in turns]
        return "Recent session history:\n" + "\n".join(lines)
