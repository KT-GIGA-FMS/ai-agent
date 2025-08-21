#!/bin/bash

# 차량 예약 AI 에이전트 빠른 테스트 스크립트

BASE_URL="http://localhost:8000"

echo "🚗 차량 예약 AI 에이전트 빠른 테스트"
echo "=================================="

# 1. 헬스체크
echo -e "\n1️⃣ 서비스 상태 확인"
curl -s "${BASE_URL}/healthz" | jq '.'

# 2. 새 세션 생성
echo -e "\n2️⃣ 새 세션 생성"
SESSION_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/sessions")
echo $SESSION_RESPONSE | jq '.'

# 세션 ID 추출
SESSION_ID=$(echo $SESSION_RESPONSE | jq -r '.session_id')
echo "생성된 세션 ID: $SESSION_ID"

# 3. 첫 번째 메시지 (예약 시작)
echo -e "\n3️⃣ 예약 시작 메시지"
curl -s -X POST "${BASE_URL}/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"message\": \"내일 오후 2시부터 6시까지 차량 예약하고 싶어. u_001이야\",
    \"user_id\": \"u_001\"
  }" | jq '.'

# 잠시 대기
sleep 2

# 4. 두 번째 메시지 (차량 선택)
echo -e "\n4️⃣ 차량 선택 메시지"
curl -s -X POST "${BASE_URL}/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"message\": \"아반떼로 예약하고 싶어\",
    \"user_id\": \"u_001\"
  }" | jq '.'

# 잠시 대기
sleep 2

# 5. 세 번째 메시지 (예약 완료)
echo -e "\n5️⃣ 예약 완료 메시지"
curl -s -X POST "${BASE_URL}/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"message\": \"예약 완료해줘\",
    \"user_id\": \"u_001\"
  }" | jq '.'

# 6. 세션 정리
echo -e "\n6️⃣ 세션 정리"
curl -s -X DELETE "${BASE_URL}/api/v1/sessions/$SESSION_ID" | jq '.'

echo -e "\n✅ 테스트 완료!"
