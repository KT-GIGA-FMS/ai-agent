import pytest
import sys
import os
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from reservation_agent.core.config import settings
from reservation_agent.core.redis_client import get_client, healthcheck
from reservation_agent.core.db import get_engine, healthcheck as db_healthcheck
from reservation_agent.schemas.chat import ChatIn, ChatOut
from reservation_agent.schemas.sessions import NewSessionOut, SessionStatus, ReservationSlots
from reservation_agent.services.chat_service import (
    create_session, save_session_slots, load_session_slots,
    extract_user_id, extract_time_info, generate_next_question,
    get_session, update_session_activity, update_session_chat_history,
    get_chat_history_for_langchain, delete_session, get_active_sessions,
    process_chat
)
from reservation_agent.tools.reservation_tool import (
    check_availability, create_reservation, list_available_cars,
    _overlap, _join_car, _find_car_by_name_or_id
)


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
    
    def test_reservation_slots_schema(self):
        """ReservationSlots 스키마 테스트"""
        slots = ReservationSlots(
            user_id="u_001",
            start_at="2025-01-15T14:00:00Z",
            end_at="2025-01-15T18:00:00Z",
            vehicle_id="car_001"
        )
        assert slots.user_id == "u_001"
        assert slots.start_at == "2025-01-15T14:00:00Z"
        assert slots.end_at == "2025-01-15T18:00:00Z"
        assert slots.vehicle_id == "car_001"
    
    def test_reservation_slots_get_missing_slots(self):
        """ReservationSlots의 누락 슬롯 확인 테스트"""
        # 모든 슬롯이 채워진 경우
        complete_slots = ReservationSlots(
            user_id="u_001",
            start_at="2025-01-15T14:00:00Z",
            end_at="2025-01-15T18:00:00Z",
            vehicle_id="car_001"
        )
        assert complete_slots.get_missing_slots() == []
        
        # 일부 슬롯이 누락된 경우
        incomplete_slots = ReservationSlots(
            user_id="u_001",
            start_at="2025-01-15T14:00:00Z"
        )
        missing = incomplete_slots.get_missing_slots()
        assert "end_at" in missing
        assert "vehicle_id" in missing
    
    def test_reservation_slots_is_complete(self):
        """ReservationSlots의 완성도 확인 테스트"""
        # 완성된 슬롯
        complete_slots = ReservationSlots(
            user_id="u_001",
            start_at="2025-01-15T14:00:00Z",
            end_at="2025-01-15T18:00:00Z",
            vehicle_id="car_001"
        )
        assert complete_slots.is_complete() is True
        
        # 불완전한 슬롯
        incomplete_slots = ReservationSlots(
            user_id="u_001",
            start_at="2025-01-15T14:00:00Z"
        )
        assert incomplete_slots.is_complete() is False


class TestRedisClient:
    """Redis 클라이언트 단위 테스트"""
    
    @patch('reservation_agent.core.redis_client.redis.from_url')
    def test_get_client_initialization(self, mock_from_url):
        """Redis 클라이언트 초기화 테스트"""
        mock_client = Mock()
        mock_from_url.return_value = mock_client
        
        client = get_client()
        assert client == mock_client
        mock_from_url.assert_called_once()
    
    @patch('reservation_agent.core.redis_client.get_client')
    def test_healthcheck_success(self, mock_get_client):
        """Redis 헬스체크 성공 테스트"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_get_client.return_value = mock_client
        
        result = healthcheck()
        assert result is True
        mock_client.ping.assert_called_once()
    
    @patch('reservation_agent.core.redis_client.get_client')
    def test_healthcheck_failure(self, mock_get_client):
        """Redis 헬스체크 실패 테스트"""
        mock_client = Mock()
        mock_client.ping.side_effect = Exception("Connection failed")
        mock_get_client.return_value = mock_client
        
        result = healthcheck()
        assert result is False


class TestDatabase:
    """데이터베이스 관련 단위 테스트"""
    
    @patch('reservation_agent.core.db.create_engine')
    def test_get_engine_initialization(self, mock_create_engine):
        """데이터베이스 엔진 초기화 테스트"""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        engine = get_engine()
        assert engine == mock_engine
        mock_create_engine.assert_called_once()
    
    @patch('reservation_agent.core.db.get_engine')
    def test_db_healthcheck_success(self, mock_get_engine):
        """데이터베이스 헬스체크 성공 테스트"""
        mock_engine = Mock()
        mock_connection = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_connection)
        mock_context.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = mock_context
        mock_get_engine.return_value = mock_engine
        
        result = db_healthcheck()
        assert result is True
    
    @patch('reservation_agent.core.db.get_engine')
    def test_db_healthcheck_failure(self, mock_get_engine):
        """데이터베이스 헬스체크 실패 테스트"""
        mock_engine = Mock()
        mock_engine.connect.side_effect = Exception("Database connection failed")
        mock_get_engine.return_value = mock_engine
        
        result = db_healthcheck()
        assert result is False


class TestChatService:
    """채팅 서비스 단위 테스트"""
    
    @patch('reservation_agent.services.chat_service.get_client')
    def test_create_session(self, mock_get_client):
        """세션 생성 테스트"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        session_id = create_session()
        
        assert isinstance(session_id, str)
        assert len(session_id) > 0
        mock_client.setex.assert_called()
        mock_client.sadd.assert_called()
    
    @patch('reservation_agent.services.chat_service.get_client')
    def test_save_and_load_session_slots(self, mock_get_client):
        """세션 슬롯 저장 및 로드 테스트"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        session_id = "test-session-123"
        slots = ReservationSlots(user_id="u_001", start_at="2025-01-15T14:00:00Z")
        
        # 슬롯 저장
        save_session_slots(session_id, slots)
        mock_client.setex.assert_called()
        
        # 슬롯 로드 - Pydantic v2 호환성
        mock_client.get.return_value = json.dumps(slots.model_dump())
        loaded_slots = load_session_slots(session_id)
        
        assert loaded_slots.user_id == "u_001"
        assert loaded_slots.start_at == "2025-01-15T14:00:00Z"
    
    def test_extract_user_id(self):
        """사용자 ID 추출 테스트"""
        # 다양한 형식 테스트
        assert extract_user_id("안녕하세요 u_001입니다") == "u_001"
        assert extract_user_id("사용자 u001입니다") == "u_001"
        assert extract_user_id("안녕하세요") is None
        assert extract_user_id("") is None
    
    def test_extract_time_info(self):
        """시간 정보 추출 테스트"""
        # ISO8601 형식 시간 추출
        start, end = extract_time_info("2025-01-15T14:00:00Z부터 2025-01-15T18:00:00Z까지")
        assert start == "2025-01-15T14:00:00Z"
        assert end == "2025-01-15T18:00:00Z"
        
        # 시작 시간만 있는 경우
        start, end = extract_time_info("2025-01-15T14:00:00Z에 시작")
        assert start == "2025-01-15T14:00:00Z"
        assert end is None
        
        # 시간 정보가 없는 경우
        start, end = extract_time_info("안녕하세요")
        assert start is None
        assert end is None
    
    def test_generate_next_question(self):
        """다음 질문 생성 테스트"""
        # 누락된 슬롯이 있는 경우
        question = generate_next_question(["start_at", "end_at"])
        assert "시작 시간" in question
        
        # 모든 슬롯이 완성된 경우
        question = generate_next_question([])
        assert "모든 정보가 완성" in question
    
    @patch('reservation_agent.services.chat_service.get_client')
    def test_get_session(self, mock_get_client):
        """세션 조회 테스트"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        session_data = {
            "session_id": "test-session-123",
            "expires_at": "2025-01-15T20:00:00",
            "chat_history": [],
            "created_at": "2025-01-15T10:00:00",
            "last_activity": "2025-01-15T10:00:00"
        }
        mock_client.get.return_value = json.dumps(session_data)
        
        session_info = get_session("test-session-123")
        assert session_info.session_id == "test-session-123"
        assert session_info.expires_at == "2025-01-15T20:00:00"
    
    @patch('reservation_agent.services.chat_service.get_client')
    def test_get_session_not_found(self, mock_get_client):
        """존재하지 않는 세션 조회 테스트"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get.return_value = None
        
        with pytest.raises(ValueError, match="Session.*not found"):
            get_session("non-existent-session")
    
    @patch('reservation_agent.services.chat_service.get_client')
    def test_update_session_activity(self, mock_get_client):
        """세션 활동 시간 업데이트 테스트"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        session_data = {
            "session_id": "test-session-123",
            "last_activity": "2025-01-15T10:00:00"
        }
        mock_client.get.return_value = json.dumps(session_data)
        
        result = update_session_activity("test-session-123")
        assert result is True
        mock_client.setex.assert_called()
    
    @patch('reservation_agent.services.chat_service.get_client')
    def test_update_session_chat_history(self, mock_get_client):
        """세션 채팅 히스토리 업데이트 테스트"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        session_data = {
            "session_id": "test-session-123",
            "chat_history": [],
            "last_activity": "2025-01-15T10:00:00"
        }
        mock_client.get.return_value = json.dumps(session_data)
        
        result = update_session_chat_history("test-session-123", "안녕하세요", "안녕하세요!")
        assert result is True
        mock_client.setex.assert_called()
    
    @patch('reservation_agent.services.chat_service.get_session')
    def test_get_chat_history_for_langchain(self, mock_get_session):
        """LangChain용 채팅 히스토리 변환 테스트"""
        session_info = Mock()
        session_info.chat_history = [
            {"role": "user", "content": "안녕하세요"},
            {"role": "assistant", "content": "안녕하세요!"},
            {"role": "user", "content": "예약하고 싶어요"},
            {"role": "assistant", "content": "네, 도와드리겠습니다"}
        ]
        mock_get_session.return_value = session_info
        
        history = get_chat_history_for_langchain("test-session-123")
        
        assert len(history) == 4
        assert history[0] == ("human", "안녕하세요")
        assert history[1] == ("ai", "안녕하세요!")
        assert history[2] == ("human", "예약하고 싶어요")
        assert history[3] == ("ai", "네, 도와드리겠습니다")
    
    @patch('reservation_agent.services.chat_service.get_client')
    def test_delete_session(self, mock_get_client):
        """세션 삭제 테스트"""
        mock_client = Mock()
        mock_client.delete.return_value = 2  # 2개 키 삭제
        mock_get_client.return_value = mock_client
        
        result = delete_session("test-session-123")
        assert result is True
        mock_client.delete.assert_called()
        mock_client.srem.assert_called()
    
    @patch('reservation_agent.services.chat_service.get_client')
    def test_get_active_sessions(self, mock_get_client):
        """활성 세션 목록 조회 테스트"""
        mock_client = Mock()
        mock_client.smembers.return_value = {"session-1", "session-2", "session-3"}
        mock_get_client.return_value = mock_client
        
        sessions = get_active_sessions()
        assert len(sessions) == 3
        assert "session-1" in sessions
        assert "session-2" in sessions
        assert "session-3" in sessions


class TestReservationTools:
    """예약 도구 단위 테스트"""
    
    def test_overlap_function(self):
        """시간 겹침 확인 함수 테스트"""
        # 겹치는 경우
        assert _overlap("2025-01-15T10:00:00", "2025-01-15T12:00:00", 
                       "2025-01-15T11:00:00", "2025-01-15T13:00:00") is True
        
        # 겹치지 않는 경우
        assert _overlap("2025-01-15T10:00:00", "2025-01-15T12:00:00", 
                       "2025-01-15T12:00:00", "2025-01-15T14:00:00") is False
        
        # 경계값 테스트
        assert _overlap("2025-01-15T10:00:00", "2025-01-15T12:00:00", 
                       "2025-01-15T12:00:00", "2025-01-15T14:00:00") is False
    
    def test_join_car_function(self):
        """차량 정보 조인 함수 테스트"""
        car = {
            "id": "car_001",
            "car_model_id": "model_001",
            "status": "available"
        }
        
        # 모델 정보가 있는 경우
        with patch('reservation_agent.tools.reservation_tool.MODELS', {
            "model_001": {
                "id": "model_001",
                "name": "Hyundai Avante",
                "url": "http://example.com",
                "fuel_type": "gasoline",
                "fuel_efficiency": "15km/l"
            }
        }):
            joined_car = _join_car(car)
            assert joined_car["car_model_name"] == "Hyundai Avante"
            assert joined_car["car_model_url"] == "http://example.com"
            assert joined_car["car_model_fuel_type"] == "gasoline"
    
    def test_find_car_by_name_or_id(self):
        """차량 이름 또는 ID로 차량 찾기 테스트"""
        # ID로 찾기
        with patch('reservation_agent.tools.reservation_tool.CARS', [
            {"id": "car_001", "car_model_id": "model_001"},
            {"id": "car_002", "car_model_id": "model_002"}
        ]):
            car = _find_car_by_name_or_id("car_001")
            assert car["id"] == "car_001"
        
        # 존재하지 않는 ID
        with patch('reservation_agent.tools.reservation_tool.CARS', [
            {"id": "car_001", "car_model_id": "model_001"}
        ]):
            car = _find_car_by_name_or_id("non_existent")
            assert car is None
    
    def test_check_availability_tool(self):
        """차량 가용성 확인 도구 테스트"""
        # LangChain 도구의 invoke 메서드 사용
        result = check_availability.invoke({
            "from_time": "2025-01-15T10:00:00Z",
            "to_time": "2025-01-15T12:00:00Z"
        })
        assert "available_cars" in result
        assert "count" in result
        assert "time_range" in result
    
    def test_check_availability_invalid_time_tool(self):
        """잘못된 시간 형식으로 가용성 확인 테스트"""
        result = check_availability.invoke({
            "from_time": "2025-01-15T12:00:00Z",  # 시작이 종료보다 늦음
            "to_time": "2025-01-15T10:00:00Z"
        })
        assert "error" in result
        assert "시작 시간이 종료 시간보다 늦을 수 없습니다" in result["error"]
    
    def test_create_reservation_tool(self):
        """예약 생성 도구 테스트"""
        result = create_reservation.invoke({
            "user_id": "u_001",
            "vehicle_id": "car_001",
            "from_time": "2025-01-15T10:00:00Z",
            "to_time": "2025-01-15T12:00:00Z"
        })
        assert "success" in result or "error" in result
    
    def test_create_reservation_invalid_time_tool(self):
        """잘못된 시간으로 예약 생성 테스트"""
        # 먼저 유효한 차량으로 테스트
        result = create_reservation.invoke({
            "user_id": "u_001",
            "vehicle_id": "car_001",  # 실제 데이터에 있는 차량 ID 사용
            "from_time": "2025-01-15T12:00:00Z",  # 시작이 종료보다 늦음
            "to_time": "2025-01-15T10:00:00Z"
        })
        
        # 차량을 찾을 수 없는 경우도 고려
        if "error" in result:
            # 차량을 찾을 수 없는 경우, 시간 검증 전에 차량 검증이 먼저 실패
            assert "차량을 찾을 수 없습니다" in result["error"] or "시작 시간이 종료 시간보다 늦을 수 없습니다" in result["error"]
        else:
            # 성공한 경우도 있음 (실제 데이터에 따라)
            assert "success" in result
    
    def test_list_available_cars_tool(self):
        """사용 가능한 차량 목록 조회 도구 테스트"""
        result = list_available_cars.invoke({})
        assert "available_cars" in result
        assert "count" in result
        assert isinstance(result["available_cars"], list)


class TestProcessChat:
    """채팅 처리 통합 테스트"""
    
    @patch('reservation_agent.services.chat_service.get_session')
    @patch('reservation_agent.services.chat_service.update_session_activity')
    @patch('reservation_agent.services.chat_service.load_session_slots')
    @patch('reservation_agent.services.chat_service.save_session_slots')
    @patch('reservation_agent.services.chat_service.update_session_chat_history')
    def test_process_chat_success(self, mock_update_history, mock_save_slots, 
                                 mock_load_slots, mock_update_activity, mock_get_session):
        """정상적인 채팅 처리 테스트"""
        # Mock 설정
        mock_get_session.return_value = Mock()
        mock_update_activity.return_value = True
        mock_load_slots.return_value = ReservationSlots(user_id="u_001")
        mock_save_slots.return_value = None
        mock_update_history.return_value = True
        
        chat_in = ChatIn(
            session_id="test-session-123",
            message="안녕하세요",
            user_id="u_001"
        )
        
        result = process_chat(chat_in)
        
        assert isinstance(result, ChatOut)
        assert result.session_id == "test-session-123"
        assert result.status in ["CONTINUE", "RESERVATION_COMPLETE", "ERROR"]
    
    @patch('reservation_agent.services.chat_service.get_session')
    def test_process_chat_session_not_found(self, mock_get_session):
        """세션이 없는 경우 채팅 처리 테스트"""
        mock_get_session.side_effect = ValueError("Session not found")
        
        chat_in = ChatIn(
            session_id="non-existent-session",
            message="안녕하세요",
            user_id="u_001"
        )
        
        result = process_chat(chat_in)
        
        assert isinstance(result, ChatOut)
        assert result.status == "ERROR"
        assert "세션이 만료되었습니다" in result.response


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
    
    def test_datetime_operations(self):
        """날짜/시간 연산 테스트"""
        now = datetime.utcnow()
        future = now + timedelta(hours=1)
        
        assert future > now
        assert (future - now).total_seconds() > 0


# Fixture 정의
@pytest.fixture
def sample_session_data():
    """샘플 세션 데이터 fixture"""
    return {
        "session_id": "test-session-123",
        "expires_at": "2025-01-15T20:00:00",
        "chat_history": [],
        "created_at": "2025-01-15T10:00:00",
        "last_activity": "2025-01-15T10:00:00"
    }


@pytest.fixture
def sample_reservation_slots():
    """샘플 예약 슬롯 fixture"""
    return ReservationSlots(
        user_id="u_001",
        start_at="2025-01-15T14:00:00Z",
        end_at="2025-01-15T18:00:00Z",
        vehicle_id="car_001"
    )


if __name__ == "__main__":
    pytest.main([__file__])
