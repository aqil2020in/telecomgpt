"""FastAPI entrypoint for `uvicorn backend.main:app`."""

from tnic.main import app, create_app

__all__ = ["app", "create_app"]
