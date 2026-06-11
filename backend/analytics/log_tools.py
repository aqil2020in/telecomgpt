"""Log file parsing and aggregation."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

_LEVEL_RE = re.compile(r"\b(TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\b", re.I)
_TS_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}|\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})"
)


def parse_log_text(text: str, *, max_lines: int = 50_000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines()[:max_lines], start=1):
        line = line.rstrip("\n\r")
        if not line.strip():
            continue
        level_m = _LEVEL_RE.search(line)
        ts_m = _TS_RE.search(line)
        rows.append(
            {
                "line_no": i,
                "timestamp": ts_m.group(1) if ts_m else None,
                "level": level_m.group(1).upper() if level_m else "UNKNOWN",
                "message": line,
            }
        )
    return rows


def log_summary(text: str) -> dict[str, Any]:
    rows = parse_log_text(text)
    levels = Counter(r["level"] for r in rows)
    errors = [r for r in rows if r["level"] in ("ERROR", "FATAL", "CRITICAL")]

    # Simple error fingerprint: strip timestamps and numbers for grouping
    fingerprints: Counter[str] = Counter()
    for r in errors[:5000]:
        fp = re.sub(r"\d+", "#", r["message"])
        fp = re.sub(r"\s+", " ", fp).strip()[:120]
        fingerprints[fp] += 1

    return {
        "total_lines": len(rows),
        "level_counts": dict(levels),
        "error_count": len(errors),
        "top_errors": [
            {"message": msg, "count": cnt}
            for msg, cnt in fingerprints.most_common(10)
        ],
        "sample_errors": errors[:20],
        "has_timestamps": sum(1 for r in rows if r["timestamp"]),
    }
