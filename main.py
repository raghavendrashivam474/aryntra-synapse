"""
main.py

Aryntra Synapse — Sprint 0.2
Application entry point.

Run with:
    uvicorn main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes import router, initialise_retriever
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: load documents and build FAISS index.
    Shutdown: nothing to clean up at this stage.
    """
    print(f"[Synapse] Starting {settings.app_name} v{settings.app_version}")
    print(f"[Synapse] Loading documents and building index...")
    initialise_retriever()
    print(f"[Synapse] Retriever ready.")
    yield
    print(f"[Synapse] Shutting down.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(router)
