"""Kafka 메시지 DTO 정의

core-api ↔ ai-server 간 Kafka 메시지 형식
"""
from pydantic import BaseModel


# core-api → ai-server (토픽: video-ai-analysis-requested)
class VideoAiAnalysisRequestedEvent(BaseModel):
    videoId: int       # 영상 ID
    s3Bucket: str      # S3 버킷명
    s3Key: str         # S3 객체 키 (예: "videos/123/source/source.mp4")


# ai-server → core-api (토픽: video-ai-analysis-completed)
class VideoAiAnalysisCompletedEvent(BaseModel):
    videoId: int                         # 영상 ID
    status: str                          # "COMPLETED" 또는 "FAILED"
    aiTags: list[str] = []               # AI 추출 태그
    summary: str = ""                    # AI 요약
    subtitleUrl: str = ""                # S3 자막 경로
    embedding: list[float] = []          # 384차원 벡터 임베딩 (core-api가 ES에 저장)
    error: str | None = None             # 실패 시 에러 메시지
