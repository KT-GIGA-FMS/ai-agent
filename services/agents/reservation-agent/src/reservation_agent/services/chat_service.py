import uuid
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from reservation_agent.core.redis_client import get_client
from reservation_agent.schemas.chat import ChatIn, ChatOut, SessionInfo
from reservation_agent.schemas.sessions import ReservationSlots
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
    
    # 초기 슬롯 상태 생성
    initial_slots = ReservationSlots()
    save_session_slots(session_id, initial_slots)
    
    return session_id


def save_session_slots(session_id: str, slots: ReservationSlots):
    """세션 슬롯 상태를 Redis에 저장"""
    client = get_client()
    slots_key = f"agent:sess:{session_id}:slots"
    client.setex(slots_key, 3600, json.dumps(slots.dict()))


def load_session_slots(session_id: str) -> ReservationSlots:
    """Redis에서 세션 슬롯 상태 로드"""
    client = get_client()
    slots_key = f"agent:sess:{session_id}:slots"
    
    slots_data = client.get(slots_key)
    if not slots_data:
        return ReservationSlots()
    
    try:
        data = json.loads(slots_data)
        return ReservationSlots(**data)
    except Exception:
        return ReservationSlots()


def extract_user_id(message: str) -> Optional[str]:
    """메시지에서 사용자 ID 추출"""
    # 다양한 형식 지원: u_001, u001, 001 등
    patterns = [
        r'u_(\d+)',
        r'u(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            user_num = match.group(1)
            return f"u_{user_num}"
    
    return None


def extract_time_info(message: str) -> tuple[Optional[str], Optional[str]]:
    """메시지에서 시간 정보 추출"""
    # ISO8601 형식 시간 찾기
    iso_pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z'
    times = re.findall(iso_pattern, message)
    
    if len(times) >= 2:
        return times[0], times[1]
    elif len(times) == 1:
        return times[0], None
    
    return None, None


def generate_next_question(missing_slots: List[str]) -> str:
    """누락된 슬롯에 따른 다음 질문 생성"""
    questions = {
        "user_id": "예약자 ID를 알려주세요. (예: u_001)",
        "start_at": "시작 시간을 알려주세요. (예: 2025-01-15T14:00:00Z)",
        "end_at": "종료 시간을 알려주세요. (예: 2025-01-15T18:00:00Z)",
        "vehicle_id": "차량을 선택해주세요."
    }
    
    if not missing_slots:
        return "모든 정보가 완성되었습니다. 예약을 진행하시겠습니까?"
    
    # 첫 번째 누락 슬롯에 대한 질문
    first_missing = missing_slots[0]
    return questions.get(first_missing, f"{first_missing} 정보가 필요합니다.")


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
    slots_key = f"agent:sess:{session_id}:slots"
    
    # 세션 데이터 삭제
    deleted = client.delete(session_key, slots_key)
    
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
        
        # 현재 슬롯 상태 로드
        current_slots = load_session_slots(chat_in.session_id)
        
        # 메시지에서 정보 추출
        extracted_user_id = extract_user_id(chat_in.message)
        extracted_start, extracted_end = extract_time_info(chat_in.message)
        
        # 슬롯 업데이트
        # user_id는 최초 1회만 설정하고 이후 메시지로 덮어쓰지 않음
        if extracted_user_id and current_slots.user_id is None:
            current_slots.user_id = extracted_user_id
        if extracted_start:
            current_slots.start_at = extracted_start
        if extracted_end:
            current_slots.end_at = extracted_end
        
        # 슬롯 상태 저장
        save_session_slots(chat_in.session_id, current_slots)
        
        # 누락된 슬롯 확인
        missing_slots = current_slots.get_missing_slots()
        next_question = generate_next_question(missing_slots)
        
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
        
        # 상태 결정 로직
        if missing_slots:
            status = "CONTINUE"
        elif status == "CONTINUE" and current_slots.is_complete():
            status = "RESERVATION_COMPLETE"
        
        return ChatOut(
            response=clean_response_text,
            status=status,
            session_id=chat_in.session_id,
            missing_info=missing_slots,
            next_question=next_question,
            filled_slots=current_slots.to_dict()
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
