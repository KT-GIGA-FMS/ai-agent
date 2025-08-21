import pytest
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from reservation_agent.core.config import settings
from reservation_agent.schemas.chat import ChatIn, ChatOut
from reservation_agent.schemas.sessions import NewSessionOut, SessionStatus


class TestConfig:
    """설정 관련 단위 테스트"""
    
    def test_settings_initialization(self):
        """설정 객체가 정상적으로 초기화되는지 테스트"""
        assert hasattr(settings, 'DATABASE_URL')
        assert hasattr(settings, 'REDIS_URL')
        assert hasattr(settings, 'AZURE_OPENAI_API_KEY')
        assert hasattr(settings, 'AZURE_OPENAI_ENDPOINT')
        assert hasattr(settings, 'AZURE_OPENAI_DEPLOYMENT')
        assert hasattr(settings, 'AZURE_OPENAI_API_VERSION')


class TestSchemas:
    """스키마 관련 단위 테스트"""
    
    def test_chat_in_schema(self):
        """ChatIn 스키마 테스트"""
        chat_data = {
            "session_id": "test-session-123",
            "message": "안녕하세요",
            "user_id": "u_001"
        }
        chat_in = ChatIn(**chat_data)
        assert chat_in.session_id == "test-session-123"
        assert chat_in.message == "안녕하세요"
        assert chat_in.user_id == "u_001"
    
    def test_chat_out_schema(self):
        """ChatOut 스키마 테스트"""
        chat_out_data = {
            "response": "안녕하세요! 무엇을 도와드릴까요?",
            "status": "CONTINUE",
            "session_id": "test-session-123",
            "missing_info": ["start_at", "end_at"],
            "next_question": "언제부터 언제까지 예약하시겠습니까?",
            "filled_slots": {"user_id": "u_001"}
        }
        chat_out = ChatOut(**chat_out_data)
        assert chat_out.response == "안녕하세요! 무엇을 도와드릴까요?"
        assert chat_out.status == "CONTINUE"
        assert chat_out.session_id == "test-session-123"
        assert "start_at" in chat_out.missing_info
        assert "end_at" in chat_out.missing_info
    
    def test_new_session_out_schema(self):
        """NewSessionOut 스키마 테스트"""
        session_data = {
            "session_id": "new-session-456",
            "expires_at": "2025-01-15T20:00:00"
        }
        session_out = NewSessionOut(**session_data)
        assert session_out.session_id == "new-session-456"
        assert session_out.expires_at == "2025-01-15T20:00:00"
    
    def test_session_status_schema(self):
        """SessionStatus 스키마 테스트"""
        status_data = {
            "session_id": "test-session-123",
            "is_valid": True,
            "expires_at": "2025-01-15T20:00:00",
            "chat_count": 5
        }
        status = SessionStatus(**status_data)
        assert status.session_id == "test-session-123"
        assert status.is_valid is True
        assert status.expires_at == "2025-01-15T20:00:00"
        assert status.chat_count == 5


class TestUtilities:
    """유틸리티 함수 단위 테스트"""
    
    def test_uuid_generation(self):
        """UUID 생성 테스트"""
        import uuid
        test_uuid = str(uuid.uuid4())
        assert len(test_uuid) == 36
        assert test_uuid.count('-') == 4
    
    def test_json_serialization(self):
        """JSON 직렬화 테스트"""
        import json
        test_data = {
            "session_id": "test-123",
            "message": "안녕하세요",
            "timestamp": "2025-01-15T10:00:00"
        }
        json_str = json.dumps(test_data)
        parsed_data = json.loads(json_str)
        assert parsed_data["session_id"] == "test-123"
        assert parsed_data["message"] == "안녕하세요"


if __name__ == "__main__":
    pytest.main([__file__])
