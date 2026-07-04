"""Health and status endpoints."""

from fastapi import APIRouter

from app.config import get_settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    settings = get_settings()
    pg = "unknown"
    try:
        from sqlalchemy import text
        from app.db.session import get_engine
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        pg = "ok"
    except Exception as e:
        pg = f"error: {str(e)[:80]}"

    chroma = "disabled"
    if settings.enable_chroma:
        try:
            from app.rag.retriever import get_rag_store
            get_rag_store()
            chroma = "ok"
        except Exception as e:
            chroma = f"error: {str(e)[:80]}"

    openai_status = "configured" if settings.openai_api_key else "not_configured"
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        postgres=pg,
        chroma=chroma,
        openai=openai_status,
    )
