from fastapi import FastAPI, Response, HTTPException
from reservation_agent.core.db import healthcheck as db_ok
from reservation_agent.core.redis_client import healthcheck as redis_ok
from reservation_agent.core.config import settings
from reservation_agent.services.chat_service import create_session, process_chat, get_session, delete_session, get_active_sessions
from reservation_agent.schemas.chat import ChatIn, ChatOut
from reservation_agent.schemas.sessions import NewSessionOut, SessionStatus
from datetime import datetime

app = FastAPI(title="Reservation Agent API", version="0.1.0")

@app.get("/")
def root():
    return {"status": "ok", "service": "reservation-agent"}

@app.get("/livez")
def livez():
    return {"status": "alive"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz(response: Response):
    missing_env = [k for k in ["DATABASE_URL", "REDIS_URL"] if not getattr(settings, k)]
    ok_db = db_ok()
    ok_redis = redis_ok()
    if missing_env or not (ok_db and ok_redis):
        response.status_code = 503
        return {"status": "not_ready", "missing_env": missing_env, "db_ok": ok_db, "redis_ok": ok_redis}
    return {"status": "ready"}

@app.post("/sessions", response_model=NewSessionOut)
def new_session():
    """새 세션 생성"""
    try:
        session_id = create_session()
        session_info = get_session(session_id)
        return NewSessionOut(
            session_id=session_id,
            expires_at=session_info.expires_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 생성 실패: {str(e)}")

@app.get("/sessions/{session_id}", response_model=SessionStatus)
def get_session_status(session_id: str):
    """세션 상태 조회"""
    try:
        session_info = get_session(session_id)
        return SessionStatus(
            session_id=session_id,
            is_valid=True,
            expires_at=session_info.expires_at,
            chat_count=len(session_info.chat_history) // 2  # user/assistant 쌍으로 계산
        )
    except ValueError:
        return SessionStatus(
            session_id=session_id,
            is_valid=False,
            expires_at="",
            chat_count=0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 조회 실패: {str(e)}")

@app.delete("/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    """세션 삭제"""
    try:
        success = delete_session(session_id)
        if success:
            return {"message": "세션이 삭제되었습니다.", "session_id": session_id}
        else:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 삭제 실패: {str(e)}")

@app.get("/sessions")
def list_active_sessions():
    """활성 세션 목록 조회"""
    try:
        active_sessions = get_active_sessions()
        return {
            "active_sessions": active_sessions,
            "count": len(active_sessions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 목록 조회 실패: {str(e)}")

@app.post("/chat", response_model=ChatOut)
def chat(chat_in: ChatIn):
    """채팅 메시지 처리"""
    try:
        return process_chat(chat_in)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 처리 실패: {str(e)}")