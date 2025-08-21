from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class NewSessionOut(BaseModel):
    session_id: str
    expires_at: str


class SessionStatus(BaseModel):
    session_id: str
    is_valid: bool
    expires_at: str
    chat_count: int = 0


class ReservationSlots(BaseModel):
    """예약에 필요한 슬롯 정보"""

    user_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None

    def is_complete(self) -> bool:
        """모든 필수 슬롯이 채워졌는지 확인"""
        return all(
            [
                self.user_id is not None,
                self.vehicle_id is not None,
                self.start_at is not None,
                self.end_at is not None,
            ]
        )

    def get_missing_slots(self) -> List[str]:
        """누락된 슬롯 목록 반환"""
        missing = []
        if not self.user_id:
            missing.append("user_id")
        if not self.vehicle_id:
            missing.append("vehicle_id")
        if not self.start_at:
            missing.append("start_at")
        if not self.end_at:
            missing.append("end_at")
        return missing

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (None 값 제외)"""
        return {k: v for k, v in self.dict().items() if v is not None}
