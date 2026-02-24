from pydantic_settings import BaseSettings
from pydantic import AliasChoices, Field


class Settings(BaseSettings):
    hf_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "HF_TOKEN",
            "HUGGING_FACE_HUB_TOKEN",
            "HUGGINGFACEHUB_API_TOKEN",
            "OPD_HF_TOKEN",
        ),
    )

    # External MedGemma/OpenAI-compatible server
    medgemma_base_url: str = "http://127.0.0.1:11424/v1"
    medgemma_model: str = "google/medgemma-4b-it"
    medgemma_api_key: str = "EMPTY"
    medgemma_max_tokens: int = 1024
    medgemma_temperature: float = 0.3
    medgemma_request_timeout_seconds: float = 20.0
    medgemma_max_retries: int = 2
    medgemma_retry_backoff_seconds: float = 0.5
    medgemma_parse_retry_enabled: bool = True
    medgemma_log_enabled: bool = False
    medgemma_log_path: str = "logs/medgemma_calls.jsonl"

    # MedASR
    medasr_model_id: str = "google/medasr"
    medasr_device: str = "cpu"
    medasr_local_dir: str = "models/medasr"
    model_cache_dir: str = "models/hf_cache"

    # Audio buffering
    audio_sample_rate: int = 16000
    audio_chunk_min_seconds: float = 2.0
    audio_overlap_seconds: float = 0.5
    live_transcript_enabled: bool = True

    # MedGemma pipeline cadence (periodic trigger interval)
    pipeline_debounce_seconds: float = 5.0
    demographics_pipeline_debounce_seconds: float | None = None
    chief_complaint_pipeline_debounce_seconds: float | None = None
    keywords_pipeline_debounce_seconds: float | None = None
    symptom_pipeline_debounce_seconds: float | None = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Concurrency
    medgemma_max_concurrent_calls: int = 4

    # Feature toggles
    enable_demographics_extraction: bool = True
    enable_symptom_pipeline: bool = True
    max_symptom_calls_per_cycle: int | None = None

    # Thresholds
    question_similarity_threshold: float = 0.75

    model_config = {"env_prefix": "OPD_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
