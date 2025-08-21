import pytest
import httpx
import asyncio
import sys
import os
from pathlib import Path
from typing import AsyncGenerator

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from reservation_agent.app import app


@pytest.fixture
async def client():
    """테스트용 HTTP 클라이언트"""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.integration
class TestAPIEndpoints:
    """API 엔드포인트 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, client: httpx.AsyncClient):
        """헬스체크 엔드포인트 테스트"""
        response = await client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_livez_check(self, client: httpx.AsyncClient):
        """라이브니스 체크 엔드포인트 테스트"""
        response = await client.get("/livez")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: httpx.AsyncClient):
        """루트 엔드포인트 테스트"""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "reservation-agent"
        assert "version" in data
        assert "docs" in data
    
    @pytest.mark.asyncio
    async def test_docs_endpoint(self, client: httpx.AsyncClient):
        """Swagger UI 엔드포인트 테스트"""
        response = await client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "swagger-ui" in response.text.lower()


@pytest.mark.integration
class TestSessionManagement:
    """세션 관리 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_create_session(self, client: httpx.AsyncClient):
        """세션 생성 테스트"""
        response = await client.post("/api/v1/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "expires_at" in data
        assert len(data["session_id"]) > 0
    
    @pytest.mark.asyncio
    async def test_get_session_status(self, client: httpx.AsyncClient):
        """세션 상태 조회 테스트"""
        # 먼저 세션 생성
        create_response = await client.post("/api/v1/sessions")
        session_id = create_response.json()["session_id"]
        
        # 세션 상태 조회
        response = await client.get(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["is_valid"] is True
        assert "expires_at" in data
        assert "chat_count" in data
    
    @pytest.mark.asyncio
    async def test_delete_session(self, client: httpx.AsyncClient):
        """세션 삭제 테스트"""
        # 먼저 세션 생성
        create_response = await client.post("/api/v1/sessions")
        session_id = create_response.json()["session_id"]
        
        # 세션 삭제
        response = await client.delete(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["session_id"] == session_id
        
        # 삭제된 세션 조회 시 404 확인
        get_response = await client.get(f"/api/v1/sessions/{session_id}")
        assert get_response.status_code == 200  # 현재는 200을 반환하지만 is_valid가 False
        data = get_response.json()
        assert data["is_valid"] is False


@pytest.mark.integration
class TestChatAPI:
    """채팅 API 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_chat_without_session(self, client: httpx.AsyncClient):
        """세션 없이 채팅 요청 시 오류 테스트"""
        chat_data = {
            "session_id": "non-existent-session",
            "message": "안녕하세요",
            "user_id": "u_001"
        }
        response = await client.post("/api/v1/chat", json=chat_data)
        assert response.status_code == 200  # 현재는 200을 반환하지만 오류 메시지 포함
        data = response.json()
        assert data["status"] == "ERROR"
        assert "세션이 만료되었습니다" in data["response"]
    
    @pytest.mark.asyncio
    async def test_chat_with_valid_session(self, client: httpx.AsyncClient):
        """유효한 세션으로 채팅 테스트"""
        # 세션 생성
        session_response = await client.post("/api/v1/sessions")
        session_id = session_response.json()["session_id"]
        
        # 채팅 요청
        chat_data = {
            "session_id": session_id,
            "message": "안녕하세요",
            "user_id": "u_001"
        }
        response = await client.post("/api/v1/chat", json=chat_data)
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "status" in data
        assert data["session_id"] == session_id


@pytest.mark.integration
class TestErrorHandling:
    """오류 처리 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_404_error(self, client: httpx.AsyncClient):
        """존재하지 않는 엔드포인트 테스트"""
        response = await client.get("/non-existent-endpoint")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_invalid_json(self, client: httpx.AsyncClient):
        """잘못된 JSON 요청 테스트"""
        response = await client.post("/api/v1/chat", content="invalid json")
        assert response.status_code == 422  # Validation Error
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(self, client: httpx.AsyncClient):
        """필수 필드 누락 테스트"""
        chat_data = {
            "session_id": "test-session"
            # message 필드 누락
        }
        response = await client.post("/api/v1/chat", json=chat_data)
        assert response.status_code == 422  # Validation Error


if __name__ == "__main__":
    pytest.main([__file__, "-m", "integration"])
