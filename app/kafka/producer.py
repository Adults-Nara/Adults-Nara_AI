"""Kafka Producer — video-ai-analysis-completed 토픽에 AI 분석 결과를 발행"""

import json
import logging

from aiokafka import AIOKafkaProducer

from app.config import Settings
from app.kafka.dto import VideoAiAnalysisCompletedEvent

logger = logging.getLogger(__name__)


class KafkaProducerService:
    """AI 분석 완료 결과를 core-api로 전달하는 Kafka Producer"""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._producer: AIOKafkaProducer | None = None

    async def start(self):
        """Producer 시작 — 서버 기동 시 1회 호출"""
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._settings.kafka_bootstrap_servers,
            # dict → JSON bytes 자동 변환
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self._producer.start()
        logger.info("Kafka Producer 시작")

    async def stop(self):
        """Producer 종료 — 서버 종료 시 1회 호출"""
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka Producer 종료")

    async def send_result(self, event: VideoAiAnalysisCompletedEvent):
        """
        AI 분석 완료/실패 결과를 Kafka에 발행

        Args:
            event: VideoAiAnalysisCompletedEvent DTO

        흐름:
            Pydantic 모델 → dict(None 필드 제외) → JSON bytes → Kafka
        """
        message = event.model_dump(exclude_none=True)
        await self._producer.send_and_wait(
            self._settings.kafka_topic_result, value=message
        )
        logger.info(
            f"📤 결과 발행 — videoId: {event.videoId}, status: {event.status}"
        )
