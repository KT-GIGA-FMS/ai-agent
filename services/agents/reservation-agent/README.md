# Reservation Agent API

차량 예약을 위한 AI 에이전트 API 서비스입니다.

## 기능

- **세션 기반 대화**: Redis를 통한 세션 관리 (TTL: 1시간)
- **자연어 처리**: LangChain 기반 AI 에이전트로 자연어 예약 요청 처리
- **상태 관리**: 예약 진행 상태 추적 (CONTINUE, RESERVATION_COMPLETE, USER_CANCELLED, ERROR)
- **헬스체크**: 서비스 상태 및 의존성 확인

## API 엔드포인트

### 헬스체크
- `GET /healthz` - 기본 헬스체크
- `GET /livez` - 프로세스 생존 확인
- `GET /readyz` - 의존성(DB, Redis) 상태 확인

### 세션 관리
- `POST /sessions` - 새 세션 생성
- `GET /sessions/{session_id}` - 세션 상태 조회

### 채팅
- `POST /chat` - 채팅 메시지 처리

## 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
cp .env.example .env.local
# .env.local 파일에서 실제 값으로 설정
```

필수 환경변수:
- `DATABASE_URL`: PostgreSQL 연결 문자열
- `REDIS_URL`: Redis 연결 문자열
- `AZURE_OPENAI_DEPLOYMENT`: Azure OpenAI 배포명
- `AZURE_OPENAI_API_VERSION`: Azure OpenAI API 버전
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API 키
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI 엔드포인트

### 3. 개발 서버 실행
```bash
# 프로젝트 루트에서
PYTHONPATH=services/agents/reservation-agent/src uvicorn reservation_agent.app:app --host 0.0.0.0 --port 8000 --reload
```

### 4. API 테스트
```bash
# tests/e2e.http 파일을 REST Client로 실행
# 또는 curl 사용
curl -X POST http://localhost:8000/sessions
```

## 사용 예시

### 1. 세션 생성
```bash
curl -X POST http://localhost:8000/sessions
```

응답:
```json
{
  "session_id": "uuid-here",
  "expires_at": "2025-01-15T20:00:00"
}
```

### 2. 채팅 요청
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "uuid-here",
    "message": "내일 오후 2시부터 6시까지 차량 예약하고 싶어. u_001이야"
  }'
```

응답:
```json
{
  "response": "안녕하세요! 차량 예약을 도와드리겠습니다...",
  "status": "CONTINUE",
  "missing_info": ["시작 시간", "종료 시간"],
  "session_id": "uuid-here"
}
```

## 개발

### 프로젝트 구조
```
src/reservation_agent/
├── app.py                 # FastAPI 엔트리포인트
├── agent_runner.py        # LangChain 에이전트 초기화
├── core/                  # 인프라 계층
│   ├── config.py         # 환경변수 설정
│   ├── db.py             # PostgreSQL 연결
│   └── redis_client.py   # Redis 클라이언트
├── services/             # 비즈니스 로직
│   └── chat_service.py   # 채팅 처리 서비스
├── schemas/              # Pydantic 모델
│   ├── chat.py          # 채팅 API 스키마
│   └── sessions.py      # 세션 API 스키마
└── tools/               # LangChain 도구
    └── reservation_tool.py  # 예약 관련 도구
```

### 테스트
```bash
# REST Client (VS Code Extension) 사용
# tests/e2e.http 파일 실행
```

## 상태 코드

- `CONTINUE`: 대화 계속 (추가 정보 필요)
- `RESERVATION_COMPLETE`: 예약 완료
- `USER_CANCELLED`: 사용자 취소
- `ERROR`: 오류 발생
