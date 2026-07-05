"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from tnic.api.routes.upload import router as upload_router
from tnic.api.routes.analyze import router as analyze_router
from tnic.api.routes.coverage import router as coverage_router
from tnic.api.routes.datasets import router as datasets_router
from tnic.api.routes.health import router as health_router
from tnic.api.routes.incidents import router as incidents_router
from tnic.config import get_settings
from tnic.db.session import init_db
from tnic.exceptions import register_exception_handlers
from tnic.logging_config import setup_logging
from tnic.rag.retriever import get_rag_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    init_db()
    if settings.enable_chroma:
        count = get_rag_store().load_seed_documents()
        from tnic.logging_config import get_logger
        get_logger(__name__).info("RAG seed documents loaded: %d", count)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="XYZ Telecom Network Intelligence Copilot — multi-agent 5G RCA platform",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    prefix = settings.api_prefix
    app.include_router(health_router, prefix=prefix)
    app.include_router(analyze_router, prefix=prefix)
    app.include_router(coverage_router, prefix=prefix)
    app.include_router(incidents_router, prefix=prefix)
    app.include_router(datasets_router, prefix=prefix)
    app.include_router(upload_router, prefix=prefix)

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/docs")

    return app


app = create_app()
