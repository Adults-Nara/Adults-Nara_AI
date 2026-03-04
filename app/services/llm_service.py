import json
import logging

from openai import OpenAI

from app.config import Settings

logger = logging.getLogger(__name__)

# 허용 태그 목록 — 이 목록에 있는 태그만 LLM이 선택할 수 있음
# core-api에서 사용 중인 태그와 동기화 필요
ALLOWED_TAGS = [
    "코미디", "액션", "로맨스", "드라마", "공포", "스릴러", "다큐멘터리",
    "먹방", "브이로그", "리뷰", "뷰티", "패션", "게임", "음악", "댄스",
    "스포츠", "여행", "교육", "과학", "기술", "뉴스", "정치", "경제",
    "요리", "건강", "운동", "자동차", "반려동물", "키즈", "ASMR",
    "인터뷰", "토크쇼", "챌린지", "일상", "힐링", "자기계발",
]


def get_openai_client(settings: Settings) -> OpenAI:
    """OpenAI 클라이언트 생성"""
    return OpenAI(api_key=settings.openai_api_key)


def extract_tags_and_summary(settings: Settings, transcript: str) -> dict:
    """
    GPT-4o-mini를 사용하여 영상 스크립트에서 요약과 태그를 추출

    Args:
        settings: 환경변수 설정 객체
        transcript: STT(transcribe_video)로 추출한 전체 음성 텍스트

    Returns:
        {"summary": "영상 요약 텍스트", "tags": ["태그1", "태그2", ...]}

    핵심 설계:
        - response_format={"type": "json_object"} → LLM이 반드시 JSON으로 응답
        - 허용 태그 목록(ALLOWED_TAGS)을 프롬프트에 주입 → 무분별한 태그 생성 방지
        - 응답 후 한 번 더 필터링 → LLM이 목록 밖 태그를 생성해도 제거
    """
    client = get_openai_client(settings)

    logger.info(f"LLM 요약+태그 추출 시작 — 텍스트 길이: {len(transcript)}자")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},  # JSON 응답 강제
        messages=[
            {
                "role": "system",
                "content": "당신은 영상 콘텐츠 분석 전문가입니다. 반드시 JSON 형식으로 응답하세요.",
            },
            {
                "role": "user",
                "content": f"""다음은 영상의 음성 스크립트입니다:
---
{transcript}
---
아래 작업을 수행하고 JSON으로 응답하세요:
1. "summary": 이 영상의 핵심 내용을 2~3문장으로 요약
2. "tags": 아래 허용된 태그 목록에서 이 영상에 가장 적합한 태그를 3~5개 선택

허용된 태그 목록: {ALLOWED_TAGS}

응답 형식:
{{"summary": "...", "tags": ["태그1", "태그2", ...]}}

중요:
- 반드시 허용된 태그 목록에 있는 태그만 선택하세요
- 음성 내용이 없거나 의미 없는 경우, summary는 "(내용 없음)"으로, tags는 빈 배열로 응답하세요
""",
            },
        ],
    )

    # JSON 파싱
    raw_content = response.choices[0].message.content
    result = json.loads(raw_content)

    # 안전장치: LLM이 ALLOWED_TAGS 밖의 태그를 생성했을 경우 필터링
    filtered_tags = [tag for tag in result.get("tags", []) if tag in ALLOWED_TAGS]
    result["tags"] = filtered_tags

    logger.info(f"LLM 결과 — 요약: {result['summary'][:50]}..., 태그: {result['tags']}")

    return result
