from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class ChatIn(BaseModel):
    session_id: str
    message: str


class ChatOut(BaseModel):
    response: str
    status: str  # CONTINUE, RESERVATION_COMPLETE, USER_CANCELLED, ERROR
    missing_info: List[str] = []
    session_id: str
    next_question: Optional[str] = None
    filled_slots: Dict[str, Any] = {}


class SessionInfo(BaseModel):
    session_id: str
    expires_at: str
    chat_history: List[dict] = []
