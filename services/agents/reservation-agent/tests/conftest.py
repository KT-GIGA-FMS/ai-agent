import pytest
import os
from unittest.mock import Mock


class FakeLLM:
    """테스트용 가짜 LLM"""
    
    def invoke(self, *args, **kwargs):
        """가짜 응답 반환"""
        return {"output": "테스트 환경입니다. 이것은 모킹된 응답입니다."}


class FakeExecutor:
    """테스트용 가짜 Executor"""
    
    def invoke(self, *args, **kwargs):
        """가짜 응답 반환"""
        return {"output": "테스트 환경입니다. 이것은 모킹된 응답입니다."}


@pytest.fixture(autouse=True)
def patch_llm_and_executor(monkeypatch):
    """테스트 환경에서 LLM과 Executor를 모킹"""
    # 테스트 환경인지 확인
    if os.getenv("TESTING") == "true" or os.getenv("PYTEST_CURRENT_TEST"):
        # agent_runner 모듈의 get_llm과 get_executor 함수를 모킹
        monkeypatch.setattr("reservation_agent.agent_runner.get_llm", lambda: FakeLLM())
        monkeypatch.setattr("reservation_agent.agent_runner.get_executor", lambda: FakeExecutor())
        
        # 전역 변수도 모킹
        monkeypatch.setattr("reservation_agent.agent_runner.llm", FakeLLM())
        monkeypatch.setattr("reservation_agent.agent_runner.executor", FakeExecutor())


@pytest.fixture
def mock_redis(monkeypatch):
    """Redis 모킹"""
    mock_client = Mock()
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.delete.return_value = 1
    mock_client.sadd.return_value = 1
    mock_client.srem.return_value = 1
    mock_client.smembers.return_value = set()
    
    monkeypatch.setattr("reservation_agent.core.redis_client.get_client", lambda: mock_client)
    return mock_client


@pytest.fixture
def mock_database(monkeypatch):
    """데이터베이스 모킹"""
    mock_engine = Mock()
    mock_session = Mock()
    
    monkeypatch.setattr("reservation_agent.core.db.get_engine", lambda: mock_engine)
    monkeypatch.setattr("reservation_agent.core.db.get_session", lambda: mock_session)
    
    return mock_engine, mock_session
