from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "Aryntra Synapse"
    app_version: str = "0.9.0"

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
    # flat | structured_v1 | compressed_v1 | progressive_v1 |
    # evidence_workspace_v1 | selective_v1 |
    # semantic_v1 | blended_v1          <-- S6 modes
    context_representation: str = "selective_v1"

    # S3 Progressive Parameters (retained)
    max_expansion_steps: int = 2
    initial_chunk_count: int = 1

    # S4 Evidence Workspace Parameters (retained)
    max_active_chunks: int = 3
    reuse_ollama_context: bool = False

    # S5 Sufficiency Parameters (retained, frozen)
    sufficiency_score_threshold: float = 0.45
    sufficiency_coverage_threshold: float = 0.25

    # S6 Semantic Sufficiency Parameters (calibrated)
    semantic_sufficiency_threshold: float = 0.60
    semantic_sufficiency_mode: str = "blended"

    # S7 Evidence Reuse Parameters
    evidence_reuse_enabled: bool = True

    # S8 Evidence Priority Parameters
    enable_priority_routing: bool = True
    priority_semantic_weight: float = 0.50
    priority_lexical_weight: float = 0.30
    priority_reuse_weight: float = 0.20
    priority_high_threshold: float = 0.60
    priority_medium_threshold: float = 0.30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

