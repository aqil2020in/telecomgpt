"""FastAPI routes for CSV / log analytics."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, Form, UploadFile

from .charts import ChartType, chart_from_csv, level_counts_chart
from .csv_tools import csv_summary, load_csv_bytes
from .log_tools import log_summary

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.post("/csv/summary")
async def analyze_csv_summary(file: UploadFile = File(...)):
    raw = await file.read()
    df = load_csv_bytes(raw)
    return {"filename": file.filename, "summary": csv_summary(df)}


@router.post("/csv/chart")
async def analyze_csv_chart(
    file: UploadFile = File(...),
    chart_type: ChartType = Form("line"),
    x: str | None = Form(None),
    y: str | None = Form(None),
    color: str | None = Form(None),
):
    raw = await file.read()
    df = load_csv_bytes(raw)
    fig_json = chart_from_csv(df, chart_type=chart_type, x=x or None, y=y or None, color=color or None)
    return {
        "filename": file.filename,
        "chart_type": chart_type,
        "plotly_json": fig_json,
    }


@router.post("/logs/analyze")
async def analyze_log(file: UploadFile = File(...)):
    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")
    summary = log_summary(text)
    chart = None
    if summary["level_counts"]:
        chart = level_counts_chart(summary["level_counts"]).to_json()
    return {
        "filename": file.filename,
        "summary": summary,
        "plotly_json": chart,
    }
