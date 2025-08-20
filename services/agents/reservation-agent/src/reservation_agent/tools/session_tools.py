import json
from typing import Optional, Dict, Any

from langchain.tools import tool

from reservation_agent.core.redis_client import get_client
from reservation_agent.schemas.sessions import ReservationSlots


def _slots_key(session_id: str) -> str:
    return f"agent:sess:{session_id}:slots"


def _load_slots(session_id: str) -> ReservationSlots:
    client = get_client()
    raw = client.get(_slots_key(session_id))
    if not raw:
        return ReservationSlots()
    try:
        data = json.loads(raw)
        return ReservationSlots(**data)
    except Exception:
        return ReservationSlots()


def _save_slots(session_id: str, slots: ReservationSlots):
    client = get_client()
    client.setex(_slots_key(session_id), 3600, json.dumps(slots.dict()))


@tool
def update_slots(
    session_id: str,
    user_id: Optional[str] = None,
    start_at: Optional[str] = None,
    end_at: Optional[str] = None,
    vehicle_id: Optional[str] = None,
) -> Dict[str, Any]:
    """세션의 예약 슬롯을 업데이트한다.

    규칙:
    - user_id는 'u_###' 형태로 정규화하여 전달할 것.
    - 시간은 ISO8601(예: 2025-01-15T14:00:00)로 전달할 것.
    - 제공된 값만 덮어쓴다(None은 무시).
    반환: { slots, missing_info, is_complete }
    """
    slots = _load_slots(session_id)
    if user_id:
        slots.user_id = user_id
    if start_at:
        slots.start_at = start_at
    if end_at:
        slots.end_at = end_at
    if vehicle_id:
        slots.vehicle_id = vehicle_id

    _save_slots(session_id, slots)

    missing = slots.get_missing_slots()
    return {
        "slots": slots.to_dict(),
        "missing_info": missing,
        "is_complete": len(missing) == 0,
    }


@tool
def get_slots(session_id: str) -> Dict[str, Any]:
    """현재 세션의 슬롯 상태를 조회한다. 반환: { slots, missing_info, is_complete }"""
    slots = _load_slots(session_id)
    missing = slots.get_missing_slots()
    return {
        "slots": slots.to_dict(),
        "missing_info": missing,
        "is_complete": len(missing) == 0,
    }


