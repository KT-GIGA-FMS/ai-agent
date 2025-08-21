#!/bin/bash

# CI/CD 테스트 스크립트
# GitHub Actions에서 실행되는 테스트 스크립트

set -e  # 오류 발생 시 스크립트 중단

echo "🚀 CI/CD 테스트 시작"
echo "=================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Python 경로 설정
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"

# 1. 코드 품질 검사
log_info "1️⃣ 코드 품질 검사 시작"

log_info "🔍 flake8 실행..."
if ! flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics; then
    log_error "flake8 오류 발견"
    exit 1
fi

if ! flake8 src/ --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics; then
    log_warn "flake8 스타일 경고 발견"
fi

log_info "🎨 black 포맷팅 검사..."
if ! black --check src/; then
    log_error "black 포맷팅 오류 발견"
    exit 1
fi

log_info "📦 isort 임포트 정렬 검사..."
if ! isort --check-only src/; then
    log_error "isort 임포트 정렬 오류 발견"
    exit 1
fi

log_info "✅ 코드 품질 검사 완료"

# 2. 단위 테스트
log_info "2️⃣ 단위 테스트 시작"

log_info "📋 pytest 실행..."
if ! python -m pytest tests/test_unit.py -v --cov=src --cov-report=term-missing; then
    log_error "단위 테스트 실패"
    exit 1
fi

log_info "✅ 단위 테스트 완료"

# 3. Docker 빌드 테스트
log_info "3️⃣ Docker 빌드 테스트 시작"

log_info "🐳 Docker 이미지 빌드..."
if ! docker build -t reservation-agent:test .; then
    log_error "Docker 빌드 실패"
    exit 1
fi

log_info "🐳 Docker 컨테이너 테스트..."
if ! docker run --rm -d --name test-container reservation-agent:test; then
    log_error "Docker 컨테이너 시작 실패"
    exit 1
fi

# 컨테이너가 정상적으로 시작되는지 확인
sleep 10
if ! docker logs test-container; then
    log_error "Docker 컨테이너 로그 확인 실패"
    docker stop test-container || true
    exit 1
fi

# 컨테이너 정리
docker stop test-container || true

log_info "✅ Docker 빌드 테스트 완료"

# 4. 보안 스캔 (Trivy)
log_info "4️⃣ 보안 스캔 시작"

if command -v trivy &> /dev/null; then
    log_info "🔒 Trivy 보안 스캔 실행..."
    if ! trivy image --severity HIGH,CRITICAL reservation-agent:test; then
        log_warn "보안 취약점 발견"
    fi
else
    log_warn "Trivy가 설치되지 않음 - 보안 스캔 건너뜀"
fi

log_info "✅ 보안 스캔 완료"

# 5. 통합 테스트 (선택사항)
if [ "$RUN_INTEGRATION_TESTS" = "true" ]; then
    log_info "5️⃣ 통합 테스트 시작"
    
    # PostgreSQL 및 Redis 서비스 시작 (Docker Compose 사용)
    log_info "🗄️ 테스트 데이터베이스 시작..."
    docker-compose up -d postgres redis
    
    # 데이터베이스 준비 대기
    sleep 15
    
    # 환경변수 설정
    export DATABASE_URL="postgresql://reservation_user:reservation_password@localhost:5432/reservation_db"
    export REDIS_URL="redis://localhost:6379/0"
    export AZURE_OPENAI_API_KEY="test-key"
    export AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/"
    export AZURE_OPENAI_DEPLOYMENT="test-deployment"
    export AZURE_OPENAI_API_VERSION="2024-02-15-preview"
    
    log_info "🧪 통합 테스트 실행..."
    if ! python -m pytest tests/test_integration.py -v -m "integration"; then
        log_error "통합 테스트 실패"
        docker-compose down
        exit 1
    fi
    
    # 서비스 정리
    docker-compose down
    
    log_info "✅ 통합 테스트 완료"
else
    log_info "⏭️ 통합 테스트 건너뜀 (RUN_INTEGRATION_TESTS=false)"
fi

# 6. 최종 결과
log_info "🎉 모든 CI/CD 테스트 완료!"
log_info "📊 테스트 결과 요약:"
echo "   - 코드 품질 검사: ✅ 통과"
echo "   - 단위 테스트: ✅ 통과"
echo "   - Docker 빌드: ✅ 통과"
echo "   - 보안 스캔: ✅ 완료"
if [ "$RUN_INTEGRATION_TESTS" = "true" ]; then
    echo "   - 통합 테스트: ✅ 통과"
fi

echo ""
log_info "🚀 배포 준비 완료!"
