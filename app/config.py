from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """환경변수 기반 애플리케이션 설정"""

    # ── Kafka ──
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "ai-video-processor"
    kafka_topic_request: str = "video-ai-analysis-requested"
    kafka_topic_result: str = "video-ai-analysis-completed"
    kafka_session_timeout_ms: int = 300000      # 5분 (기본 10초)
    kafka_heartbeat_interval_ms: int = 10000    # 10초 (기본 3초)
    kafka_max_poll_interval_ms: int = 600000    # 10분 (기본 5분)

    # ── AWS S3 ──
    s3_bucket_name: str = "asn-s3-bucket"
    aws_default_region: str = "ap-northeast-2"

    # ── OpenAI ──
    openai_api_key: str = ""

    # ── PostgreSQL (PGVector) ──
    database_url: str = "postgresql://postgres:password@localhost:5432/postgres"

    # ── Whisper STT ──
    whisper_model_size: str = "medium"
    whisper_compute_type: str = "int8"
    whisper_language: str = "ko"

    # ── Server ──
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
