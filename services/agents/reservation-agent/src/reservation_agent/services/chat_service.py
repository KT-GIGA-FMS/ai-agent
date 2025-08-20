import uuid
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

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
        "created_at": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat()
    }
    
    # Redis에 세션 데이터 저장 (TTL: 1시간)
    session_key = f"agent:sess:{session_id}:data"
    client.setex(session_key, 3600, json.dumps(session_data))
    
    # 세션 목록에 추가 (세션 관리용)
    client.sadd("agent:sessions:active", session_id)
    client.expire("agent:sessions:active", 3600)
    
    return session_id


def get_session(session_id: str) -> SessionInfo:
    """Redis에서 세션 정보 조회"""
    client = get_client()
    session_key = f"agent:sess:{session_id}:data"
    
    session_data = client.get(session_key)
    if not session_data:
        raise ValueError(f"Session {session_id} not found or expired")
    
    try:
        data = json.loads(session_data)
        return SessionInfo(**data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid session data format: {e}")
    except Exception as e:
        raise ValueError(f"Session data error: {e}")


def update_session_activity(session_id: str):
    """세션 활동 시간 업데이트 및 TTL 갱신"""
    client = get_client()
    session_key = f"agent:sess:{session_id}:data"
    
    session_data = client.get(session_key)
    if not session_data:
        return False
    
    data = json.loads(session_data)
    data["last_activity"] = datetime.utcnow().isoformat()
    
    # TTL 갱신 (1시간)
    client.setex(session_key, 3600, json.dumps(data))
    return True


def update_session_chat_history(session_id: str, user_input: str, ai_response: str):
    """세션의 채팅 히스토리 업데이트"""
    client = get_client()
    session_key = f"agent:sess:{session_id}:data"
    
    session_data = client.get(session_key)
    if not session_data:
        return False
    
    data = json.loads(session_data)
    
    # 채팅 히스토리 추가
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
    
    # 마지막 활동 시간 업데이트
    data["last_activity"] = datetime.utcnow().isoformat()
    
    # Redis TTL 갱신
    client.setex(session_key, 3600, json.dumps(data))
    return True


def get_chat_history_for_langchain(session_id: str) -> List[tuple]:
    """LangChain용 채팅 히스토리 형식으로 변환"""
    try:
        session_info = get_session(session_id)
        history = []
        
        for i in range(0, len(session_info.chat_history), 2):
            if i + 1 < len(session_info.chat_history):
                user_msg = session_info.chat_history[i]
                ai_msg = session_info.chat_history[i + 1]
                
                if user_msg["role"] == "user" and ai_msg["role"] == "assistant":
                    # LangChain 형식: ("human", "user message"), ("ai", "assistant message")
                    history.append(("human", user_msg["content"]))
                    history.append(("ai", ai_msg["content"]))
        
        return history
    except Exception:
        return []


def delete_session(session_id: str) -> bool:
    """세션 삭제"""
    client = get_client()
    session_key = f"agent:sess:{session_id}:data"
    
    # 세션 데이터 삭제
    deleted = client.delete(session_key)
    
    # 활성 세션 목록에서 제거
    client.srem("agent:sessions:active", session_id)
    
    return deleted > 0


def get_active_sessions() -> List[str]:
    """활성 세션 목록 조회"""
    client = get_client()
    return list(client.smembers("agent:sessions:active"))


def process_chat(chat_in: ChatIn) -> ChatOut:
    """채팅 메시지 처리 및 AI 응답 생성"""
    try:
        # 세션 유효성 확인 및 활동 시간 업데이트
        session_info = get_session(chat_in.session_id)
        update_session_activity(chat_in.session_id)
        
        # Redis에서 채팅 히스토리 로드
        chat_history = get_chat_history_for_langchain(chat_in.session_id)
        
        # LangChain 에이전트 호출
        result = executor.invoke({
            "input": chat_in.message,
            "chat_history": chat_history
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
