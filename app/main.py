import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 수명주기: 시작/종료 로직"""
    settings = get_settings()
    logger.info("✅ AI 서버 시작")
    # TODO: Kafka Consumer/Producer 시작
    yield
    logger.info("🛑 AI 서버 종료")
    # TODO: Kafka Consumer/Producer 종료


def create_app() -> FastAPI:
    """FastAPI 앱 팩토리"""
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = FastAPI(
        title="Adults-Nara AI Server",
        description="AI 영상 분석 서버 (STT, 태그 추출, 벡터 임베딩)",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()
