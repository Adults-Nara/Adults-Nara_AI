"""Kafka Consumer — video-ai-analysis-requested 토픽을 구독하여 AI 분석 실행"""

import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import Settings
from app.kafka.dto import VideoAiAnalysisRequestedEvent
from app.kafka.producer import KafkaProducerService
from app.worker.video_processor import process_video

logger = logging.getLogger(__name__)


class KafkaConsumerService:
    """
    core-api가 발행한 video-ai-analysis-requested 이벤트를 수신하여
    AI 영상 분석 파이프라인(process_video)을 실행하는 Consumer

    설정:
        - auto_offset_reset="earliest": 그룹 최초 참여 시 처음부터 읽음
        - enable_auto_commit=False: 처리 완료 후 수동 커밋 (메시지 유실 방지)
    """

    def __init__(self, settings: Settings, producer: KafkaProducerService):
        self._settings = settings
        self._producer = producer
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self):
        """Consumer 시작 → 메시지 수신 루프 실행"""
        self._consumer = AIOKafkaConsumer(
            self._settings.kafka_topic_request,
            bootstrap_servers=self._settings.kafka_bootstrap_servers,
            group_id=self._settings.kafka_consumer_group,
            # value_deserializer에서 파싱 에러가 나면 Consumer 태스크가 죽어버리므로, 순수 bytes로 받아서 루프 내부에서 파싱
            value_deserializer=lambda m: m, 
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )

        await self._consumer.start()
        self._running = True
        logger.info(
            f"Kafka Consumer 시작 — 토픽: {self._settings.kafka_topic_request}, "
            f"그룹: {self._settings.kafka_consumer_group}"
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
                        await self._consumer.commit()
                        continue

                    # 2. JSON → DTO 변환
                    event = VideoAiAnalysisRequestedEvent(**parsed_value)
                    logger.info(f"📩 메시지 수신 — videoId: {event.videoId}")

                    # 전체 파이프라인 실행 (S3 → STT → VTT → LLM → 임베딩 → Kafka 발행)
                    await process_video(event, self._settings, self._producer)

                    # 처리 완료 후 오프셋 커밋
                    await self._consumer.commit()
                    logger.info(f"✅ 오프셋 커밋 — offset: {msg.offset}")

                except Exception as e:
                    logger.error(f"❌ 메시지 처리 실패: {e}", exc_info=True)
                    # 실패해도 커밋 (video_processor에서 FAILED 이벤트를 Kafka로 발행)
                    await self._consumer.commit()

        except Exception as e:
            if self._running:
                logger.error(f"❌ Consumer 에러: {e}", exc_info=True)
        finally:
            await self._consumer.stop()

    async def stop(self):
        """Consumer 종료 요청"""
        self._running = False
        logger.info("Kafka Consumer 종료 요청")
