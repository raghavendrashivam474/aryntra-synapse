"""
app/core/config.py

Aryntra Synapse — Sprint 0.2 / Sprint 1
Centralised application settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "Aryntra Synapse"
    app_version: str = "0.2.0"

    # Knowledge Source
    sample_document: str = "data/sample.txt"

    # Retrieval / Chunking
    chunk_size: int = 512
    chunk_overlap: int = 64
    embedding_model: str = "all-MiniLM-L6-v2"
    top_k: int = 3

    # LLM
    llm_model: str = "mistral"
    ollama_host: str = "http://localhost:11434"

    # Context Representation (S1)
    context_representation: str = "flat"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
