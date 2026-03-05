"""메인 파이프라인 — S3 → STT → VTT → LLM → 임베딩 → Kafka 결과 발행

Kafka Consumer가 video-ai-analysis-requested 이벤트를 수신하면
이 함수가 호출되어 전체 AI 분석 파이프라인을 실행합니다.
"""

import logging
import os

from app.config import Settings
from app.kafka.dto import VideoAiAnalysisRequestedEvent, VideoAiAnalysisCompletedEvent
from app.kafka.producer import KafkaProducerService
from app.services.s3_service import download_video, upload_subtitle
from app.services.stt_service import transcribe_video, generate_vtt
from app.services.llm_service import extract_tags_and_summary
from app.services.embedding_service import generate_embedding

logger = logging.getLogger(__name__)


async def process_video(
    event: VideoAiAnalysisRequestedEvent,
    settings: Settings,
    producer: KafkaProducerService,
):
    """
    AI 영상 분석 파이프라인

    Args:
        event: core-api가 발행한 분석 요청 이벤트
        settings: 환경변수 설정
        producer: Kafka Producer (결과 발행용)

    파이프라인:
        ① S3 영상 다운로드
        ② STT 음성 추출 (faster-whisper)
        ③ 자막 VTT 생성 + S3 업로드
        ④ 텍스트 요약 + 태그 추출 (GPT-4o-mini)
        ⑤ 벡터 임베딩 생성 (text-embedding-3-small)
        ⑥ 결과를 Kafka로 발행 (video-ai-analysis-completed)
    """
    video_id = event.videoId
    local_path = None

    try:
        logger.info(f"[{video_id}] ── 파이프라인 시작 ──")

        # ① S3에서 영상 다운로드
        local_path = download_video(settings, event.s3Bucket, event.s3Key, video_id)

        # ② STT 음성 추출
        transcript, subtitle_segments = transcribe_video(settings, local_path)
        if not transcript.strip():
            transcript = "(음성 없음)"
            logger.warning(f"[{video_id}] 음성이 감지되지 않음")

        # ③ 자막 VTT 생성 + S3 업로드
        vtt_content = generate_vtt(subtitle_segments)
        subtitle_url = upload_subtitle(settings, vtt_content, video_id)

        # ④ 텍스트 요약 + 태그 추출
        llm_result = extract_tags_and_summary(settings, transcript)

        # ⑤ 벡터 임베딩 생성 (요약 텍스트 → 1536차원)
        embedding = generate_embedding(settings, llm_result["summary"])

        # ⑥ 성공 결과를 Kafka로 발행
        await producer.send_result(VideoAiAnalysisCompletedEvent(
            videoId=video_id,
            status="COMPLETED",
            aiTags=llm_result["tags"],
            summary=llm_result["summary"],
            subtitleUrl=subtitle_url,
            embedding=embedding,
        ))

        logger.info(f"[{video_id}] ✅ 파이프라인 완료")

    except Exception as e:
        logger.error(f"[{video_id}] ❌ 처리 실패: {e}", exc_info=True)

        # 실패 결과도 Kafka로 발행 → core-api가 상태 업데이트 가능
        try:
            await producer.send_result(VideoAiAnalysisCompletedEvent(
                videoId=video_id,
                status="FAILED",
                error=str(e),
            ))
        except Exception as pub_err:
            logger.error(f"[{video_id}] ❌ 실패 결과 발행 실패: {pub_err}", exc_info=True)

    finally:
        # 임시 파일 정리
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
            logger.debug(f"[{video_id}] 임시 파일 삭제: {local_path}")
