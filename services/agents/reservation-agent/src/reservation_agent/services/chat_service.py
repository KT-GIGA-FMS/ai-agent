import uuid
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

from reservation_agent.core.redis_client import get_client
from reservation_agent.schemas.chat import ChatIn, ChatOut, SessionInfo
from reservation_agent.agent_runner import executor, parse_conversation_status, clean_response


def create_session() -> str:
    """새 세션 생성 및 Redis에 저장"""
    session_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    client = get_client()
    session_data = {
        "session_id": session_id,
        "expires_at": expires_at.isoformat(),
        "chat_history": [],
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Redis에 세션 데이터 저장 (TTL: 1시간)
    client.setex(
        f"agent:sess:{session_id}:data", 
        3600, 
        json.dumps(session_data)
    )
    
    return session_id


def get_session(session_id: str) -> SessionInfo:
    """Redis에서 세션 정보 조회"""
    client = get_client()
    session_key = f"agent:sess:{session_id}:data"
    
    session_data = client.get(session_key)
    if not session_data:
        raise ValueError(f"Session {session_id} not found or expired")
    
    data = json.loads(session_data)
    return SessionInfo(**data)


def update_session_chat_history(session_id: str, user_input: str, ai_response: str):
    """세션의 채팅 히스토리 업데이트"""
    client = get_client()
    session_key = f"agent:sess:{session_id}:data"
    
    session_data = client.get(session_key)
    if not session_data:
        return
    
    data = json.loads(session_data)
    data["chat_history"].append({
        "role": "user",
        "content": user_input,
        "timestamp": datetime.utcnow().isoformat()
    })
    data["chat_history"].append({
        "role": "assistant", 
        "content": ai_response,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Redis TTL 갱신
    client.setex(session_key, 3600, json.dumps(data))


def process_chat(chat_in: ChatIn) -> ChatOut:
    """채팅 메시지 처리 및 AI 응답 생성"""
    try:
        # 세션 유효성 확인
        session_info = get_session(chat_in.session_id)
        
        # LangChain 에이전트 호출
        result = executor.invoke({
            "input": chat_in.message,
            "chat_history": []  # TODO: Redis에서 히스토리 로드
        })
        
        response = result["output"]
        
        # 상태 파싱
        status = parse_conversation_status(response)
        clean_response_text = clean_response(response)
        
        # 세션 히스토리 업데이트
        update_session_chat_history(chat_in.session_id, chat_in.message, clean_response_text)
        
        return ChatOut(
            response=clean_response_text,
            status=status,
            session_id=chat_in.session_id,
            missing_info=[]  # TODO: 슬롯 분석 로직 추가
        )
        
    except ValueError as e:
        # 세션 만료/없음
        return ChatOut(
            response="세션이 만료되었습니다. 새로운 세션을 시작해주세요.",
            status="ERROR",
            session_id=chat_in.session_id
        )
    except Exception as e:
        # 기타 오류
        return ChatOut(
            response=f"오류가 발생했습니다: {str(e)}",
            status="ERROR", 
            session_id=chat_in.session_id
        )
