# 🎬 Adults-Nara AI Server

> Kafka 이벤트 기반 AI 영상 분석 파이프라인 — Python / FastAPI

영상이 업로드되면 **자동으로 음성 인식 → 자막 생성 → 요약·태그 추출 → 벡터 임베딩**까지 수행하고,
결과를 Kafka를 통해 Core API에 전달합니다.

---

## 📁 디렉토리 구조

```
ASN_AI/
├── app/
│   ├── main.py                  # FastAPI 앱 진입점 & 라이프사이클 관리
│   ├── config.py                # Pydantic 기반 환경변수 설정
│   ├── kafka/
│   │   ├── consumer.py          # Kafka Consumer (이벤트 수신 + 자동 재시작)
│   │   ├── producer.py          # Kafka Producer (분석 결과 발행)
│   │   └── dto.py               # 요청/응답 이벤트 DTO
│   ├── services/
│   │   ├── s3_service.py        # S3 영상 다운로드 / 자막 업로드
│   │   ├── stt_service.py       # Whisper STT + WebVTT 자막 생성
│   │   ├── llm_service.py       # GPT-4o-mini 요약·태그 추출
│   │   └── embedding_service.py # OpenAI 텍스트 임베딩
│   └── worker/
│       └── video_processor.py   # 메인 파이프라인 오케스트레이터
├── tests/                       # pytest 테스트
├── .github/
│   ├── workflows/
│   │   ├── deploy.yml           # CI/CD (ECR → EC2 자동 배포)
│   │   ├── create-jira-issue.yml
│   │   ├── close-jira-issue.yml
│   │   └── pr-jira-title.yml
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── pytest.ini
```

---

## 🔄 영상 분석 파이프라인

Core API가 `video-ai-analysis-requested` 토픽에 이벤트를 발행하면,
아래 6단계가 순차적으로 실행됩니다.

```
┌─────────────────────────────────────────────────────────────┐
│                  Kafka Consumer (수신)                       │
│         video-ai-analysis-requested 토픽 구독               │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
         ┌─────────────────────────┐
         │  1. S3 영상 다운로드     │  videos/{videoId}/source/source.mp4
         └────────────┬────────────┘
                      ▼
         ┌─────────────────────────┐
         │  2. STT 음성 추출       │  faster-whisper (medium/large-v3)
         └────────────┬────────────┘
                      ▼
         ┌─────────────────────────┐
         │  3. WebVTT 자막 생성    │  자막 파일 → S3 업로드
         └────────────┬────────────┘
                      ▼
         ┌─────────────────────────┐
         │  4. 요약 + 태그 추출     │  GPT-4o-mini
         └────────────┬────────────┘
                      ▼
         ┌─────────────────────────┐
         │  5. 벡터 임베딩 생성     │  text-embedding-3-small
         └────────────┬────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  Kafka Producer (발행)                       │
│         video-ai-analysis-completed 토픽 발행                │
│         (COMPLETED / FAILED 상태 포함)                       │
└─────────────────────────────────────────────────────────────┘
```

| 단계 | 담당 서비스 | 사용 기술 |
|:---:|:---|:---|
| 1 | `s3_service.py` | AWS S3 (boto3) |
| 2 | `stt_service.py` | faster-whisper (CTranslate2) |
| 3 | `stt_service.py` | WebVTT 포맷 생성 → S3 업로드 |
| 4 | `llm_service.py` | OpenAI GPT-4o-mini |
| 5 | `embedding_service.py` | OpenAI text-embedding-3-small |
| 6 | `video_processor.py` | Kafka Producer 결과 발행 |

> **실패 처리**: 파이프라인 중 에러 발생 시 `FAILED` 상태의 이벤트를 Kafka로 발행하여
> Core API가 영상 상태를 업데이트할 수 있도록 합니다.

---

## 🚀 기대효과

- **영상 검색 고도화** — 벡터 임베딩을 통한 의미 기반 유사 영상 검색 (PGVector)
- **자동 자막 제공** — Whisper 기반 한국어 음성 인식으로 별도 자막 작업 없이 WebVTT 자막 자동 생성
- **콘텐츠 자동 분류** — GPT가 영상 내용을 분석하여 태그와 요약을 자동 생성, 운영 비용 절감
- **이벤트 기반 비동기 처리** — Kafka 메시지 큐를 통해 Core API와 완전 분리된 비동기 파이프라인 운영
- **확장 가능한 아키텍처** — Consumer 인스턴스를 수평 확장하여 대량 영상 동시 처리 가능