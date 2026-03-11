import logging

from faster_whisper import WhisperModel

from app.config import Settings

logger = logging.getLogger(__name__)

# Whisper 모델 싱글톤 (한 번 로딩 후 메모리에 상주)
_whisper_model: WhisperModel | None = None

# Whisper 모델을 싱글톤으로 로딩
def get_whisper_model(settings: Settings) -> WhisperModel:
    """

    왜 싱글톤인가?
    - medium 모델은 RAM ~2.5GB를 차지함
    - 매 요청마다 로딩하면 30초씩 소요되므로, 서버 시작 시 한 번만 로딩하고 재사용
    - compute_type="int8"은 양자화로 메모리를 절반으로 줄여줌
    """
    global _whisper_model
    if _whisper_model is None:
        logger.info(
            f"Whisper 모델 로딩 — 크기: {settings.whisper_model_size}, "
            f"양자화: {settings.whisper_compute_type}"
        )
        _whisper_model = WhisperModel(
            settings.whisper_model_size,   # "medium" 또는 "large-v3"
            device="cpu",                  # EC2 c6i는 CPU만 사용
            compute_type=settings.whisper_compute_type,  # "int8" 양자화
        )
        logger.info("✅ Whisper 모델 로딩 완료")
    return _whisper_model


def transcribe_video(settings: Settings, video_path: str) -> tuple[str, list[dict]]:
    """
    영상 파일에서 음성을 추출하고 텍스트로 변환

    Args:
        settings: 환경변수 설정 객체
        video_path: 영상 파일 경로 (예: "/tmp/123.mp4")

    Returns:
        (full_transcript, subtitle_segments)
        - full_transcript: 전체 음성 텍스트 (한 덩어리)
        - subtitle_segments: 타임스탬프별 세그먼트 리스트
          [{"start": 0.0, "end": 2.5, "text": "안녕하세요"}, ...]

    핵심 로직:
        - faster-whisper는 영상에서 자동으로 오디오를 추출 (ffmpeg 내장)
        - 각 세그먼트에 no_speech_prob(음성 없음 확률)이 붙음
        - no_speech_prob >= 0.7이면 BGM/노이즈로 간주하고 무시 (환각 방지)
    """
    model = get_whisper_model(settings)

    logger.info(f"STT 시작 — {video_path}")
    # model.transcribe()는 제너레이터를 반환 (메모리 효율적)
    segments, info = model.transcribe(video_path, language=settings.whisper_language)

    transcript_parts = []
    subtitle_segments = []

    try:
        for seg in segments:
            # 환각 방지: 음성이 없는(BGM/노이즈) 구간 필터링
            if seg.no_speech_prob >= 0.7:
                logger.debug(
                    f"세그먼트 무시 (no_speech_prob={seg.no_speech_prob:.2f}): {seg.text}"
                )
                continue

            transcript_parts.append(seg.text)
            subtitle_segments.append({
                "start": seg.start,  # 시작 시간 (초)
                "end": seg.end,      # 끝 시간 (초)
                "text": seg.text.strip(),
            })
    except IndexError as e:
        # faster-whisper(내부 PyAV)가 오디오 트랙이 없는 영상(무음)을 디코딩하려 할 때 발생하는 에러 방어
        logger.warning(f"영상에 오디오 트랙이 없거나 손상되었습니다 (무음 처리): {e}")
    except Exception as e:
        logger.error(f"STT 처리 중 에러 발생 (무음 처리): {e}", exc_info=True)

    full_transcript = " ".join(transcript_parts)
    logger.info(
        f"STT 완료 — 세그먼트: {len(subtitle_segments)}개, "
        f"텍스트 길이: {len(full_transcript)}자"
    )

    return full_transcript, subtitle_segments


# 타임스탬프 세그먼트를 WebVTT 자막 포맷으로 변환
def generate_vtt(subtitle_segments: list[dict]) -> str:
    """
    Args:
        subtitle_segments: [{"start": 0.0, "end": 2.5, "text": "안녕하세요"}, ...]

    Returns:
        WebVTT 형식 문자열. 예시:
            WEBVTT

            1
            00:00:00.000 --> 00:00:02.500
            안녕하세요

    WebVTT 포맷 규칙:
        - 첫 줄은 반드시 "WEBVTT"
        - 각 큐(cue)는 번호, 타임코드, 텍스트, 빈 줄로 구성
        - 타임코드 형식: HH:MM:SS.mmm --> HH:MM:SS.mmm
    """
    lines = ["WEBVTT", ""]
    for i, seg in enumerate(subtitle_segments, 1):
        start = _format_vtt_time(seg["start"])
        end = _format_vtt_time(seg["end"])
        lines.append(str(i))                  # 큐 번호
        lines.append(f"{start} --> {end}")     # 타임코드
        lines.append(seg["text"])              # 자막 텍스트
        lines.append("")                       # 빈 줄 (구분자)
    return "\n".join(lines)


def _format_vtt_time(seconds: float) -> str:
    """
    초(float)를 VTT 타임코드 형식(HH:MM:SS.mmm)으로 변환

    예시: 65.123 → "00:01:05.123"
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

