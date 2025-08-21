from datetime import datetime

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

from reservation_agent.core.config import settings
from reservation_agent.core.db import healthcheck as db_ok
from reservation_agent.core.redis_client import healthcheck as redis_ok
from reservation_agent.schemas.chat import ChatIn, ChatOut
from reservation_agent.schemas.sessions import NewSessionOut, SessionStatus
from reservation_agent.services.chat_service import (
    create_session,
    delete_session,
    get_active_sessions,
    get_session,
    process_chat,
)

app = FastAPI(
    title="차량 예약 Agent API",
    description="""
    ## 차량 예약 Agent API
    
    법인 차량 예약을 위한 AI 에이전트 API입니다.
    
    ### 주요 기능
    - 🤖 LLM 기반 자연어 대화 처리
    - 🚗 차량 가용성 확인 및 예약
    - 💬 세션 기반 대화 관리
    - ⏰ 한국어 자연어 시간 처리
    
    ### 사용 예시
    1. 세션 생성: `POST /api/v1/sessions`
    2. 대화 시작: `POST /api/v1/chat` (예: "내일 오후 2시부터 6시까지 차량 예약하고 싶어. u_001이야")
    3. 차량 선택: "아반떼로 예약하고 싶어"
    4. 예약 완료: "예약 완료해줘"
    
    ### 환경 변수
    - `AZURE_OPENAI_API_KEY`: Azure OpenAI API 키
    - `AZURE_OPENAI_ENDPOINT`: Azure OpenAI 엔드포인트
    - `AZURE_OPENAI_DEPLOYMENT`: 배포 모델명
    - `REDIS_URL`: Redis 연결 URL
    - `DATABASE_URL`: PostgreSQL 연결 URL
    """,
    version="0.1.0",
    contact={
        "name": "차량 예약 Agent Team",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    docs_url=None,  # 기본 docs 비활성화
    redoc_url=None,  # 기본 redoc 비활성화
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 커스텀 Swagger UI 설정
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "defaultModelExpandDepth": 3,
            "displayRequestDuration": True,
            "docExpansion": "list",
            "filter": True,
            "showExtensions": True,
            "showCommonExtensions": True,
            "tryItOutEnabled": True,
        },
    )


# 커스텀 OpenAPI 스키마
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # 서버 정보 추가
    openapi_schema["servers"] = [
        {"url": "http://localhost:8000", "description": "개발 서버"},
        {"url": "https://api.example.com", "description": "프로덕션 서버"},
    ]

    # 태그 정보 추가
    openapi_schema["tags"] = [
        {"name": "세션 관리", "description": "대화 세션 생성, 조회, 삭제 관련 API"},
        {"name": "대화", "description": "AI 에이전트와의 자연어 대화 처리 API"},
        {"name": "API v1", "description": "API 버전 1.0 엔드포인트"},
    ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/")
def root():
    """루트 엔드포인트 - 서비스 상태 확인"""
    return {
        "status": "ok",
        "service": "reservation-agent",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/livez")
def livez():
    """라이브니스 체크 - 컨테이너가 살아있는지 확인"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@app.get("/healthz")
def healthz():
    """헬스체크 - 기본 서비스 상태 확인"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/readyz")
def readyz(response: Response):
    """레디니스 체크 - 의존성 서비스 연결 상태 확인"""
    missing_env = [k for k in ["DATABASE_URL", "REDIS_URL"] if not getattr(settings, k)]
    ok_db = db_ok()
    ok_redis = redis_ok()

    if missing_env or not (ok_db and ok_redis):
        response.status_code = 503
        return {
            "status": "not_ready",
            "missing_env": missing_env,
            "db_ok": ok_db,
            "redis_ok": ok_redis,
            "timestamp": datetime.utcnow().isoformat(),
        }

    return {
        "status": "ready",
        "dependencies": {"database": ok_db, "redis": ok_redis},
        "timestamp": datetime.utcnow().isoformat(),
    }


# API v1 라우터
from fastapi import APIRouter

api_v1_router = APIRouter(prefix="/api/v1", tags=["API v1"])


@api_v1_router.post("/sessions", response_model=NewSessionOut, tags=["세션 관리"])
def new_session():
    """
    새 대화 세션 생성

    - **세션 ID**: 고유한 세션 식별자
    - **만료 시간**: 1시간 후 자동 만료
    - **사용법**: 대화 시작 전에 먼저 호출
    """
    try:
        session_id = create_session()
        session_info = get_session(session_id)
        return NewSessionOut(session_id=session_id, expires_at=session_info.expires_at)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 생성 실패: {str(e)}")


@api_v1_router.get(
    "/sessions/{session_id}", response_model=SessionStatus, tags=["세션 관리"]
)
def get_session_status(session_id: str):
    """
    세션 상태 조회

    - **세션 ID**: 조회할 세션의 ID
    - **응답**: 세션 유효성, 만료 시간, 대화 횟수
    """
    try:
        session_info = get_session(session_id)
        return SessionStatus(
            session_id=session_id,
            is_valid=True,
            expires_at=session_info.expires_at,
            chat_count=len(session_info.chat_history)
            // 2,  # user/assistant 쌍으로 계산
        )
    except ValueError:
        return SessionStatus(
            session_id=session_id, is_valid=False, expires_at="", chat_count=0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 조회 실패: {str(e)}")


@api_v1_router.delete("/sessions/{session_id}", tags=["세션 관리"])
def delete_session_endpoint(session_id: str):
    """
    세션 삭제

    - **세션 ID**: 삭제할 세션의 ID
    - **결과**: 세션과 관련된 모든 데이터 삭제
    """
    try:
        success = delete_session(session_id)
        if success:
            return {"message": "세션이 삭제되었습니다.", "session_id": session_id}
        else:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 삭제 실패: {str(e)}")


@api_v1_router.get("/sessions", tags=["세션 관리"])
def list_active_sessions():
    """
    활성 세션 목록 조회

    - **응답**: 현재 활성 상태인 모든 세션 ID 목록
    - **용도**: 디버깅 및 모니터링
    """
    try:
        active_sessions = get_active_sessions()
        return {
            "active_sessions": active_sessions,
            "count": len(active_sessions),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 목록 조회 실패: {str(e)}")


@api_v1_router.post("/chat", response_model=ChatOut, tags=["대화"])
def chat(chat_in: ChatIn):
    """
    채팅 메시지 처리

    ### 사용 예시

    **1. 예약 시작 (사용자 ID 포함)**
    ```json
    {
      "session_id": "your-session-id",
      "message": "내일 오후 2시부터 6시까지 차량 예약하고 싶어",
      "user_id": "u_001"
    }
    ```

    **2. 차량 선택**
    ```json
    {
      "session_id": "your-session-id",
      "message": "아반떼로 예약하고 싶어",
      "user_id": "u_001"
    }
    ```

    **3. 예약 완료**
    ```json
    {
      "session_id": "your-session-id",
      "message": "예약 완료해줘",
      "user_id": "u_001"
    }
    ```

    ### 요청 필드
    - **session_id**: 대화 세션 ID (필수)
    - **message**: 사용자 메시지 (필수)
    - **user_id**: 사용자 ID (선택, 프론트엔드에서 전송 시 우선 사용)

    ### 응답 필드
    - **response**: AI 에이전트의 응답 메시지
    - **status**: 대화 상태 (CONTINUE, RESERVATION_COMPLETE, ERROR)
    - **missing_info**: 누락된 정보 목록
    - **next_question**: 다음에 물어볼 질문
    - **filled_slots**: 현재 채워진 슬롯 정보
    """
    try:
        return process_chat(chat_in)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 처리 실패: {str(e)}")


# API v1 라우터를 앱에 포함
app.include_router(api_v1_router)


# 에러 핸들러
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {
        "error": "리소스를 찾을 수 없습니다",
        "detail": str(exc),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {
        "error": "내부 서버 오류",
        "detail": str(exc),
        "timestamp": datetime.utcnow().isoformat(),
    }
