"""SQLAlchemy database layer."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class CellSnapshot(Base):
    __tablename__ = "cell_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cell_id = Column(String(64), index=True, nullable=False)
    pci = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    kpis = Column(JSON, nullable=False, default=dict)
    health_score = Column(Float, nullable=True)
    grade = Column(String(16), nullable=True)


class PMCounterRecord(Base):
    __tablename__ = "pm_counter_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cell_id = Column(String(64), index=True, nullable=False)
    counter_name = Column(String(128), index=True, nullable=False)
    counter_value = Column(Float, nullable=False)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    vendor = Column(String(32), default="generic")
    meta = Column(JSON, default=dict)


class IncidentRecord(Base):
    __tablename__ = "incident_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(64), unique=True, index=True)
    complaint_text = Column(Text, nullable=True)
    issue_type = Column(String(64), index=True)
    root_cause = Column(Text, nullable=True)
    resolution = Column(Text, nullable=True)
    kpis = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class RCAReportRecord(Base):
    __tablename__ = "rca_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(Text, nullable=False)
    issue_type = Column(String(64))
    report_json = Column(JSON, nullable=False)
    narrative = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.effective_database_url
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


def get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
