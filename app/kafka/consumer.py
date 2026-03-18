"""Kafka Consumer — video-ai-analysis-requested 토픽을 구독하여 AI 분석 실행"""

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import Settings
from app.kafka.dto import VideoAiAnalysisRequestedEvent
from app.kafka.producer import KafkaProducerService
from app.worker.video_processor import process_video

logger = logging.getLogger(__name__)

# Consumer 재시작 시 대기 시간 (초)
_RESTART_DELAY_SEC = 5
# 최대 연속 재시작 횟수 (무한 루프 방지)
_MAX_RESTART_ATTEMPTS = 10


class KafkaConsumerService:
    """
    core-api가 발행한 video-ai-analysis-requested 이벤트를 수신하여
    AI 영상 분석 파이프라인(process_video)을 실행하는 Consumer

    설정:
        - auto_offset_reset="earliest": 그룹 최초 참여 시 처음부터 읽음
        - enable_auto_commit=False: 처리 완료 후 수동 커밋 (메시지 유실 방지)
        - max_poll_interval_ms: 영상 분석 처리 시간 고려하여 충분히 설정
    """

    def __init__(self, settings: Settings, producer: KafkaProducerService):
        self._settings = settings
        self._producer = producer
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False
        self._restart_count = 0

    async def start(self):
        """Consumer 시작 → 메시지 수신 루프 실행 (에러 시 자동 재시작)"""
        self._consumer = AIOKafkaConsumer(
            self._settings.kafka_topic_request,
            bootstrap_servers=self._settings.kafka_bootstrap_servers,
            group_id=self._settings.kafka_consumer_group,
            # value_deserializer에서 파싱 에러가 나면 Consumer 태스크가 죽어버리므로, 순수 bytes로 받아서 루프 내부에서 파싱
            value_deserializer=lambda m: m,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            max_poll_interval_ms=self._settings.kafka_max_poll_interval_ms,
            session_timeout_ms=self._settings.kafka_session_timeout_ms,
            heartbeat_interval_ms=self._settings.kafka_heartbeat_interval_ms,
        )

        try:
            await self._consumer.start()
        except Exception as e:
            logger.error(f"❌ Consumer 시작 실패 (Kafka 연결 에러 등): {e}", exc_info=True)
            self._running = False
            return

        self._running = True
        self._restart_count = 0  # 정상 시작 시 재시작 카운터 초기화
        logger.info(
            f"Kafka Consumer 시작 — 토픽: {self._settings.kafka_topic_request}, "
            f"그룹: {self._settings.kafka_consumer_group}, "
            f"max_poll_interval_ms: {self._settings.kafka_max_poll_interval_ms}"
        )

        try:
            async for msg in self._consumer:
                if not self._running:
                    break
                try:
                    # 1. raw bytes → JSON 파싱
                    try:
                        raw_value = msg.value.decode("utf-8")
                        parsed_value = json.loads(raw_value)
                    except Exception as json_err:
                        logger.error(f"❌ JSON 파싱 실패 (메시지 무시): {json_err}, 원본: {msg.value}")
                        # 파싱 실패한 불량 메시지도 다시 읽지 않도록 커밋
                        await self._safe_commit("JSON 파싱 실패 후 커밋")
                        continue

                    # 2. JSON → DTO 변환
                    event = VideoAiAnalysisRequestedEvent(**parsed_value)
                    logger.info(f"📩 메시지 수신 — videoId: {event.videoId}")

                    # 전체 파이프라인 실행 (S3 → STT → VTT → LLM → 임베딩 → Kafka 발행)
                    await process_video(event, self._settings, self._producer)

                    # 처리 완료 후 오프셋 커밋
                    await self._safe_commit(f"offset: {msg.offset}")

                except Exception as e:
                    logger.error(f"❌ 메시지 처리 실패: {e}", exc_info=True)
                    # 실패해도 커밋 (video_processor에서 FAILED 이벤트를 Kafka로 발행)
                    await self._safe_commit("메시지 처리 실패 후 커밋")

        except Exception as e:
            if self._running:
                logger.error(f"❌ Consumer 루프 에러: {e}", exc_info=True)
                await self._safe_stop()
                await self._try_restart()
                return
        finally:
            await self._safe_stop()

    async def _safe_commit(self, context: str = ""):
        """커밋 시도 — CommitFailedError 등 발생해도 루프를 죽이지 않음"""
        try:
            await self._consumer.commit()
            if context:
                logger.info(f"✅ 오프셋 커밋 — {context}")
        except Exception as commit_err:
            logger.warning(f"⚠️ 오프셋 커밋 실패 (리밸런스 등, 계속 진행): {commit_err}")

    async def _safe_stop(self):
        """Consumer 안전 종료"""
        try:
            if self._consumer:
                await self._consumer.stop()
        except Exception as e:
            logger.warning(f"⚠️ Consumer 종료 중 에러 (무시): {e}")

    async def _try_restart(self):
        """Consumer 에러 시 자동 재시작 (최대 횟수 제한)"""
        if not self._running:
            return

        self._restart_count += 1
        if self._restart_count > _MAX_RESTART_ATTEMPTS:
            logger.error(
                f"❌ Consumer 재시작 {_MAX_RESTART_ATTEMPTS}회 초과 — 재시작 중단. "
                f"서버 재배포가 필요합니다."
            )
            return

        logger.info(
            f"🔄 Consumer 재시작 시도 ({self._restart_count}/{_MAX_RESTART_ATTEMPTS}), "
            f"{_RESTART_DELAY_SEC}초 후 재시작..."
        )
        await asyncio.sleep(_RESTART_DELAY_SEC)
        await self.start()

    async def stop(self):
        """Consumer 종료 요청"""
        self._running = False
        logger.info("Kafka Consumer 종료 요청")
