# Adults-Nara AI Server

AI 영상 분석 서버 (Python/FastAPI) — 영상 자동 분석 파이프라인

## 기능

- **STT (음성→텍스트)**: faster-whisper (medium/large-v3)
- **자막 생성**: WebVTT 자동 생성 → S3 업로드
- **요약 + 태그**: GPT-4o-mini로 영상 내용 분석
- **벡터 임베딩**: text-embedding-3-small → PGVector 저장
- **Kafka 연동**: `video-ai-analysis-requested` 수신 → `video-ai-analysis-completed` 발행

## 프로젝트 구조

```
app/
├── main.py              # FastAPI 앱 진입점
├── config.py            # 환경변수 설정
├── kafka/
│   ├── consumer.py      # Kafka Consumer
│   └── producer.py      # Kafka Producer
├── services/
│   ├── s3_service.py    # S3 다운로드/업로드
│   ├── stt_service.py   # STT + VTT 생성
│   ├── llm_service.py   # GPT 요약 + 태그
│   └── embedding_service.py  # 임베딩 + PGVector
└── worker/
    └── video_processor.py    # 메인 파이프라인
```

## 실행 방법

### 로컬 개발 (Docker Compose)
```bash
cp .env.example .env
# .env 파일에 실제 값 입력
docker-compose up --build
```

### 프로덕션 (EC2)
GitHub Actions가 `main` push 시 자동 배포 (ECR → SSM)

## 환경변수

| 변수 | 설명 | 기본값 |
|:---|:---|:---|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka 브로커 주소 | `localhost:9092` |
| `S3_BUCKET_NAME` | S3 버킷명 | `asn-s3-bucket` |
| `OPENAI_API_KEY` | OpenAI API 키 | — |
| `DATABASE_URL` | PostgreSQL 연결 URL | — |
| `WHISPER_MODEL_SIZE` | Whisper 모델 크기 | `medium` |
| `WHISPER_COMPUTE_TYPE` | 양자화 타입 | `int8` |

## 테스트
```bash
pip install -r requirements.txt
pytest tests/ -v
```