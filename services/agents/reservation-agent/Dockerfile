# 멀티스테이지 빌드: 개발 및 프로덕션 환경 분리
FROM python:3.11-slim as builder

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 파일 복사
COPY requirements.txt .

# 가상환경 생성 및 의존성 설치
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 프로덕션 이미지
FROM python:3.11-slim as production

# 보안을 위한 비root 사용자 생성
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 작업 디렉토리 설정
WORKDIR /app

# 가상환경 복사
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 애플리케이션 코드 복사
COPY src/ ./src/
COPY db/ ./db/

# Python 경로 설정
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# 권한 설정
RUN chown -R appuser:appuser /app
USER appuser

# 포트 노출
EXPOSE 8000

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# 애플리케이션 실행
CMD ["uvicorn", "reservation_agent.app:app", "--host", "0.0.0.0", "--port", "8000"]
