"""CSV, log analysis, and chart generation for TelecomGPT.

Import submodules directly (e.g. ``from analytics.csv_tools import csv_summary``).
Avoid eager imports here — plotly is optional on lean deployments and must not
break ``/ask`` or TNIC paths that only need csv/log helpers.
"""

__all__ = [
    "load_csv_bytes",
    "csv_summary",
    "chart_from_csv",
    "parse_log_text",
    "log_summary",
]
