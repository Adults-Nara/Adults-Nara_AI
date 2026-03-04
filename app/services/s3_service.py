import logging
import os

import boto3

from app.config import Settings

logger = logging.getLogger(__name__)


def get_s3_client(settings: Settings):
    #boto3는 AWS SDK로, Python에서 S3에 접근
    return boto3.client("s3", region_name=settings.aws_default_region)

#S3에서 영상 파일을 다운로드
def download_video(settings: Settings, bucket: str, key: str, video_id: int) -> str:
    """
    Args:
        settings: 환경변수 설정 객체
        bucket: S3 버킷명 (예: "asn-s3-bucket")
        key: S3 객체 키 (예: "original/123.mp4")
        video_id: 영상 ID

    Returns:
        다운로드된 로컬 파일 경로 (예: "/tmp/123.mp4")
    """
    # boto3 S3 클라이언트 생성
    s3 = get_s3_client(settings)
    local_path = f"/tmp/{video_id}.mp4"

    # S3에서 파일을 /tmp/{videoId}.mp4 경로로 다운로드
    logger.info(f"[{video_id}] S3 다운로드 시작 — s3://{bucket}/{key}")
    s3.download_file(bucket, key, local_path)
    
    #파일 크기를 로깅하여 정상 다운로드 확인
    file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
    logger.info(f"[{video_id}] S3 다운로드 완료 — {file_size_mb:.1f}MB → {local_path}")

    return local_path

#생성된 VTT 자막 파일을 S3에 업로드
def upload_subtitle(settings: Settings, vtt_content: str, video_id: int) -> str:
    """
    Args:
        settings: 환경변수 설정 객체
        vtt_content: WebVTT 형식의 자막 문자열
        video_id: 영상 ID

    Returns:
        업로드된 S3 객체 키 (예: "subtitles/123.vtt")
    """
    #자막 키를 "subtitles/{videoId}.vtt" 형태로 결정
    s3 = get_s3_client(settings)
    key = f"subtitles/{video_id}.vtt"

    #put_object로 문자열을 UTF-8 바이트로 변환하여 업로드
    #ContentType을 "text/vtt"로 설정하여 브라우저에서 바로 로딩 가능하게 함
    s3.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=vtt_content.encode("utf-8"),
        ContentType="text/vtt",
    )

    logger.info(f"[{video_id}] 자막 업로드 완료 — s3://{settings.s3_bucket_name}/{key}")
    return key
