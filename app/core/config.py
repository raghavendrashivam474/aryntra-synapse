from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "Aryntra Synapse"
    app_version: str = "0.5.0"

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

    # Context Representation
    # flat | structured_v1 | compressed_v1 | progressive_v1 | evidence_workspace_v1
    context_representation: str = "evidence_workspace_v1"

    # S3 Progressive Parameters (retained)
    max_expansion_steps: int = 2
    initial_chunk_count: int = 1

    # S4 Evidence Workspace Parameters
    max_active_chunks: int = 3
    reuse_ollama_context: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()