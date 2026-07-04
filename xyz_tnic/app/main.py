"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analyze import router as analyze_router
from app.api.routes.health import router as health_router
from app.config import get_settings
from app.db.session import init_db
from app.logging_config import setup_logging
from app.rag.retriever import get_rag_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    init_db()
    if settings.enable_chroma:
        get_rag_store().load_seed_documents()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="XYZ Telecom Network Intelligence Copilot — multi-agent 5G RCA platform",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    prefix = settings.api_prefix
    app.include_router(health_router, prefix=prefix)
    app.include_router(analyze_router, prefix=prefix)
    return app


app = create_app()
