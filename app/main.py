import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import get_settings
from app.services.llm_service import extract_tags_and_summary

logger = logging.getLogger(__name__)


# 테스트용 요청 모델
class TestLlmRequest(BaseModel):
    transcript: str  # 테스트할 음성 텍스트


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

    # 임시 테스트 엔드포인트
    @app.post("/test/llm")
    async def test_llm(request: TestLlmRequest):
        """텍스트를 넣으면 GPT-4o-mini가 요약+태그를 반환"""
        result = extract_tags_and_summary(settings, request.transcript)
        return result

    return app


app = create_app()
