"""
app/core/config.py

Aryntra Synapse — Sprint 0.2
Central configuration for the baseline RAG system.

All tuneable parameters live here.
Implementation files import from this module.
Nothing else should contain magic numbers or hardcoded strings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # -------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------
    app_name: str = "Aryntra Synapse"
    app_version: str = "0.2.0"
    debug: bool = False

    # -------------------------------------------------------------------
    # Data
    # -------------------------------------------------------------------
    data_dir: str = "data"
    sample_document: str = "data/sample.txt"

    # -------------------------------------------------------------------
    # Chunking
    # -------------------------------------------------------------------
    chunk_size: int = 512        # characters per chunk
    chunk_overlap: int = 64      # character overlap between chunks

    # -------------------------------------------------------------------
    # Embedding
    # -------------------------------------------------------------------
    embedding_model: str = "all-MiniLM-L6-v2"

    # -------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------
    top_k: int = 3               # default number of chunks to retrieve

    # -------------------------------------------------------------------
    # LLM
    # -------------------------------------------------------------------
    llm_model: str = "mistral"
    ollama_host: str = "http://localhost:11434"


# Single shared instance imported by all modules
settings = Settings()
