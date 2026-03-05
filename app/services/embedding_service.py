"""임베딩 서비스 — OpenAI text-embedding-3-small로 벡터 임베딩 생성

AI 서버에서 생성한 임베딩을 Kafka로 core-api에 전달하면,
core-api가 ES에 dense_vector 필드로 저장합니다.
"""
import logging

from openai import OpenAI

from app.config import Settings

logger = logging.getLogger(__name__)


def get_openai_client(settings: Settings) -> OpenAI:
    """OpenAI 클라이언트 생성"""
    return OpenAI(api_key=settings.openai_api_key)


def generate_embedding(settings: Settings, text: str) -> list[float]:
    """
    텍스트를 1536차원 벡터 임베딩으로 변환

    Args:
        settings: 환경변수 설정 객체
        text: 임베딩할 텍스트 (보통 LLM이 생성한 summary)

    Returns:
        1536차원 float 벡터 (text-embedding-3-small 기본 차원)

    용도:
        - core-api가 이 벡터를 ES의 dense_vector 필드에 저장

    """
    client = get_openai_client(settings)

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )

    embedding = response.data[0].embedding
    logger.info(f"임베딩 생성 완료 — 차원: {len(embedding)}")
    return embedding
