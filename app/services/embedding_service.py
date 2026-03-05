"""임베딩 서비스 — all-MiniLM-L6-v2 로컬 모델로 벡터 임베딩 생성

무료 오픈소스 모델을 사용하여 384차원 임베딩을 생성합니다.
OpenAI API 호출 없이 로컬에서 처리하므로 비용 $0.
"""
import logging

from sentence_transformers import SentenceTransformer

from app.config import Settings

logger = logging.getLogger(__name__)

# 모델 싱글톤 (서버 시작 시 1회 로딩, 이후 재사용)
_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """all-MiniLM-L6-v2 모델을 싱글톤으로 로딩 (~80MB, 최초 1회 다운로드)"""
    global _model
    if _model is None:
        logger.info("임베딩 모델 로딩 — all-MiniLM-L6-v2")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("✅ 임베딩 모델 로딩 완료")
    return _model


def generate_embedding(settings: Settings, text: str) -> list[float]:
    """
    텍스트를 384차원 벡터 임베딩으로 변환

    Args:
        settings: 환경변수 설정 객체
        text: 임베딩할 텍스트 (보통 LLM이 생성한 summary)

    Returns:
        384차원 float 벡터
    """
    model = get_embedding_model()
    embedding = model.encode(text).tolist()
    logger.info(f"임베딩 생성 완료 — 차원: {len(embedding)}")
    return embedding
