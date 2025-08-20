from pydantic import BaseModel
from datetime import datetime


class NewSessionOut(BaseModel):
    session_id: str
    expires_at: str


class SessionStatus(BaseModel):
    session_id: str
    is_valid: bool
    expires_at: str
    chat_count: int = 0
