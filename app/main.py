import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import get_settings
from app.services.llm_service import extract_tags_and_summary
from app.services.s3_service import download_video, upload_subtitle
from app.services.stt_service import transcribe_video, generate_vtt

logger = logging.getLogger(__name__)


# 테스트용 요청 모델
class TestLlmRequest(BaseModel):
    transcript: str  # 테스트할 음성 텍스트


class TestPipelineRequest(BaseModel):
    s3_bucket: str   # S3 버킷명 (예: "asn-s3-bucket")
    s3_key: str      # S3 객체 키 (예: "original/123.mp4")
    video_id: int    # 영상 ID


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

    # 임시 테스트 엔드포인트 — LLM만
    @app.post("/test/llm")
    async def test_llm(request: TestLlmRequest):
        """텍스트를 넣으면 GPT-4o-mini가 요약+태그를 반환"""
        result = extract_tags_and_summary(settings, request.transcript)
        return result

    # 임시 테스트 엔드포인트 — S3 + STT + LLM 전체
    @app.post("/test/pipeline")
    async def test_pipeline(request: TestPipelineRequest):
        """S3에서 영상 다운로드 → STT 음성 추출 → 자막 생성 → LLM 요약+태그"""
        local_path = None
        try:
            # 1. S3 다운로드
            local_path = download_video(
                settings, request.s3_bucket, request.s3_key, request.video_id
            )

            # 2. STT 음성 추출
            transcript, subtitle_segments = transcribe_video(settings, local_path)
            if not transcript.strip():
                transcript = "(음성 없음)"

            # 3. VTT 자막 생성 + S3 업로드
            vtt_content = generate_vtt(subtitle_segments)
            subtitle_url = upload_subtitle(settings, vtt_content, request.video_id)

            # 4. LLM 요약 + 태그
            llm_result = extract_tags_and_summary(settings, transcript)

            return {
                "video_id": request.video_id,
                "transcript": transcript[:500],  # 너무 길면 잘라서 반환
                "subtitle_segments_count": len(subtitle_segments),
                "subtitle_url": subtitle_url,
                "summary": llm_result["summary"],
                "tags": llm_result["tags"],
            }
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)

    return app


app = create_app()
