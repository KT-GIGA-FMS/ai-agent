#!/bin/bash

# 차량 예약 Agent 시작 스크립트

set -e

echo "🚗 차량 예약 Agent 시작 중..."

# 환경 변수 파일 확인
if [ ! -f .env.local ]; then
    echo "❌ .env.local 파일이 없습니다."
    echo "다음 환경 변수들을 설정해주세요:"
    echo "AZURE_OPENAI_API_KEY=your_api_key"
    echo "AZURE_OPENAI_ENDPOINT=your_endpoint"
    echo "AZURE_OPENAI_DEPLOYMENT=your_deployment"
    echo "AZURE_OPENAI_API_VERSION=2024-02-15-preview"
    exit 1
fi

# Docker Compose로 서비스 시작
echo "📦 Docker 컨테이너 시작 중..."
docker-compose up -d

# 서비스 상태 확인
echo "⏳ 서비스 상태 확인 중..."
sleep 10

# 헬스체크
echo "🏥 헬스체크 수행 중..."
if curl -f http://localhost:8000/healthz > /dev/null 2>&1; then
    echo "✅ Reservation Agent가 정상적으로 시작되었습니다!"
    
    # IP 주소 확인
    LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
    
    echo ""
    echo "🌐 접속 정보:"
    echo "📱 로컬 접속:"
    echo "   API 서버: http://localhost:8000"
    echo "   API 문서: http://localhost:8000/docs"
    echo "   OpenAPI JSON: http://localhost:8000/openapi.json"
    echo ""
    echo "🌍 네트워크 접속 (다른 사람과 공유):"
    echo "   API 서버: http://${LOCAL_IP}:8000"
    echo "   API 문서: http://${LOCAL_IP}:8000/docs"
    echo "   OpenAPI JSON: http://${LOCAL_IP}:8000/openapi.json"
    echo ""
    echo "🔍 모니터링 도구:"
    echo "   Redis Commander: http://localhost:8081 (모니터링 모드)"
    echo "   pgAdmin: http://localhost:8082 (모니터링 모드)"
else
    echo "❌ 서비스 시작에 실패했습니다."
    echo "로그를 확인해주세요: docker-compose logs reservation-agent"
    exit 1
fi

echo ""
echo "🎯 테스트 방법:"
echo "1. API 문서: http://localhost:8000/docs"
echo "2. 테스트 파일: tests/e2e.http"
echo "3. 로그 확인: docker-compose logs -f reservation-agent"
echo ""
echo "📤 다른 사람과 공유하는 방법:"
echo "1. 같은 네트워크에 연결된 사람에게 위의 네트워크 접속 URL 공유"
echo "2. ngrok 사용: ngrok http 8000 (외부 접속용)"
echo "3. 포트포워딩 설정 (라우터에서 8000번 포트 개방)"
echo ""
echo "🛑 서비스 중지: docker-compose down"
