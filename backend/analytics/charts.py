"""Plotly chart builders — return JSON for API or Figure for Streamlit."""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ChartType = Literal["line", "bar", "histogram", "scatter", "box"]


def chart_from_csv(
    df: pd.DataFrame,
    *,
    chart_type: ChartType,
    x: str | None = None,
    y: str | None = None,
    color: str | None = None,
    bins: int = 30,
) -> dict[str, Any]:
    numeric = [str(c) for c in df.select_dtypes(include="number").columns]
    cols = [str(c) for c in df.columns]

    if chart_type == "histogram":
        col = y or x or (numeric[0] if numeric else cols[0])
        fig = px.histogram(df, x=col, nbins=bins, title=f"Histogram: {col}")
    elif chart_type == "line":
        x = x or cols[0]
        y = y or (numeric[0] if numeric else cols[-1])
        fig = px.line(df, x=x, y=y, color=color, title=f"{y} over {x}")
    elif chart_type == "bar":
        x = x or cols[0]
        y = y or (numeric[0] if numeric else None)
        if y:
            fig = px.bar(df, x=x, y=y, color=color, title=f"{y} by {x}")
        else:
            counts = df[x].astype(str).value_counts().head(30).reset_index()
            counts.columns = [x, "count"]
            fig = px.bar(counts, x=x, y="count", title=f"Count by {x}")
    elif chart_type == "scatter":
        x = x or (numeric[0] if numeric else cols[0])
        y = y or (numeric[1] if len(numeric) > 1 else numeric[0] if numeric else cols[-1])
        fig = px.scatter(df, x=x, y=y, color=color, title=f"{y} vs {x}")
    elif chart_type == "box":
        y = y or (numeric[0] if numeric else cols[-1])
        fig = px.box(df, y=y, x=x, color=color, title=f"Box plot: {y}")
    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")

    fig.update_layout(margin=dict(l=40, r=20, t=50, b=40), height=480)
    return fig.to_json()


def level_counts_chart(level_counts: dict[str, int]) -> go.Figure:
    labels = list(level_counts.keys())
    values = [level_counts[k] for k in labels]
    fig = px.bar(x=labels, y=values, labels={"x": "Level", "y": "Count"}, title="Log levels")
    fig.update_layout(margin=dict(l=40, r=20, t=50, b=40), height=400)
    return fig
