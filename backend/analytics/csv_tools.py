"""CSV loading and summary statistics."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd


def load_csv_bytes(raw: bytes, *, encoding: str = "utf-8") -> pd.DataFrame:
    for enc in (encoding, "utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(io.BytesIO(raw), encoding=encoding, errors="replace")


def load_csv_path(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def csv_summary(df: pd.DataFrame, *, sample_rows: int = 5) -> dict[str, Any]:
    numeric = df.select_dtypes(include="number")
    describe = numeric.describe().round(4).to_dict() if not numeric.empty else {}

    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": list(df.columns.astype(str)),
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
        "null_counts": {str(c): int(v) for c, v in df.isna().sum().items()},
        "numeric_summary": describe,
        "preview": df.head(sample_rows).astype(str).to_dict(orient="records"),
        "numeric_columns": [str(c) for c in numeric.columns],
        "categorical_columns": [
            str(c) for c in df.columns if c not in numeric.columns
        ],
    }
