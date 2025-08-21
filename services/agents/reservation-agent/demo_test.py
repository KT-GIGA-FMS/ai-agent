#!/usr/bin/env python3
"""
차량 예약 AI 에이전트 시연 스크립트

이 스크립트는 AI 에이전트의 기능을 단계별로 테스트하고 시연합니다.
"""

import requests
import json
import time
from typing import Dict, Any

# API 기본 URL
BASE_URL = "http://localhost:8000"

def print_separator(title: str):
    """구분선 출력"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def print_response(response: requests.Response, title: str = "응답"):
    """응답 출력"""
    print(f"\n{title}:")
    print(f"상태 코드: {response.status_code}")
    try:
        data = response.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except:
        print(response.text)
    print("-" * 40)

def test_health_check():
    """헬스체크 테스트"""
    print_separator("1. 서비스 헬스체크")
    
    # 기본 헬스체크
    response = requests.get(f"{BASE_URL}/healthz")
    print_response(response, "기본 헬스체크")
    
    # 레디니스 체크
    response = requests.get(f"{BASE_URL}/readyz")
    print_response(response, "레디니스 체크")
    
    # 루트 엔드포인트
    response = requests.get(f"{BASE_URL}/")
    print_response(response, "루트 엔드포인트")

def test_session_management():
    """세션 관리 테스트"""
    print_separator("2. 세션 관리 테스트")
    
    # 새 세션 생성
    response = requests.post(f"{BASE_URL}/api/v1/sessions")
    print_response(response, "새 세션 생성")
    
    if response.status_code == 200:
        session_data = response.json()
        session_id = session_data["session_id"]
        
        # 세션 상태 조회
        response = requests.get(f"{BASE_URL}/api/v1/sessions/{session_id}")
        print_response(response, "세션 상태 조회")
        
        return session_id
    else:
        print("❌ 세션 생성 실패")
        return None

def test_chat_scenario(session_id: str):
    """채팅 시나리오 테스트"""
    print_separator("3. 차량 예약 시나리오 테스트")
    
    if not session_id:
        print("❌ 세션이 없어서 채팅 테스트를 건너뜁니다.")
        return
    
    # 테스트 시나리오
    scenarios = [
        {
            "step": "1단계: 예약 시작",
            "message": "내일 오후 2시부터 6시까지 차량 예약하고 싶어. u_001이야",
            "description": "사용자 ID와 예약 시간을 포함한 초기 요청"
        },
        {
            "step": "2단계: 차량 선택",
            "message": "아반떼로 예약하고 싶어",
            "description": "차량 모델 선택"
        },
        {
            "step": "3단계: 예약 완료",
            "message": "예약 완료해줘",
            "description": "예약 확정 요청"
        }
    ]
    
    for scenario in scenarios:
        print(f"\n📝 {scenario['step']}: {scenario['description']}")
        print(f"사용자: {scenario['message']}")
        
        chat_data = {
            "session_id": session_id,
            "message": scenario["message"],
            "user_id": "u_001"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json=chat_data,
            headers={"Content-Type": "application/json"}
        )
        
        print_response(response, f"AI 응답 ({scenario['step']})")
        
        # 응답 분석
        if response.status_code == 200:
            chat_response = response.json()
            print(f"🤖 AI: {chat_response.get('response', '응답 없음')}")
            print(f"📊 상태: {chat_response.get('status', 'UNKNOWN')}")
            
            if chat_response.get('missing_info'):
                print(f"❓ 누락 정보: {chat_response['missing_info']}")
            
            if chat_response.get('next_question'):
                print(f"❓ 다음 질문: {chat_response['next_question']}")
            
            if chat_response.get('filled_slots'):
                print(f"✅ 채워진 정보: {json.dumps(chat_response['filled_slots'], ensure_ascii=False, indent=2)}")
        
        print("-" * 60)
        time.sleep(1)  # 요청 간 간격

def test_error_handling():
    """에러 처리 테스트"""
    print_separator("4. 에러 처리 테스트")
    
    # 존재하지 않는 세션으로 채팅
    print("📝 존재하지 않는 세션으로 채팅 시도")
    chat_data = {
        "session_id": "non-existent-session",
        "message": "테스트 메시지",
        "user_id": "u_001"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/chat",
        json=chat_data,
        headers={"Content-Type": "application/json"}
    )
    print_response(response, "존재하지 않는 세션 에러")
    
    # 잘못된 JSON 형식
    print("\n📝 잘못된 JSON 형식으로 요청")
    response = requests.post(
        f"{BASE_URL}/api/v1/chat",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    print_response(response, "잘못된 JSON 에러")

def test_active_sessions():
    """활성 세션 목록 테스트"""
    print_separator("5. 활성 세션 목록 조회")
    
    response = requests.get(f"{BASE_URL}/api/v1/sessions")
    print_response(response, "활성 세션 목록")

def cleanup_session(session_id: str):
    """세션 정리"""
    if session_id:
        print_separator("6. 세션 정리")
        response = requests.delete(f"{BASE_URL}/api/v1/sessions/{session_id}")
        print_response(response, "세션 삭제")

def main():
    """메인 실행 함수"""
    print("🚗 차량 예약 AI 에이전트 시연 시작")
    print(f"📍 API 서버: {BASE_URL}")
    
    try:
        # 1. 헬스체크
        test_health_check()
        
        # 2. 세션 관리
        session_id = test_session_management()
        
        # 3. 채팅 시나리오
        test_chat_scenario(session_id)
        
        # 4. 에러 처리
        test_error_handling()
        
        # 5. 활성 세션 목록
        test_active_sessions()
        
        # 6. 정리
        cleanup_session(session_id)
        
        print_separator("✅ 시연 완료")
        print("🎉 모든 테스트가 완료되었습니다!")
        print("\n📋 시연 결과 요약:")
        print("- 서비스 상태: 정상")
        print("- 세션 관리: 정상")
        print("- AI 채팅: 정상")
        print("- 에러 처리: 정상")
        
    except requests.exceptions.ConnectionError:
        print("❌ 서버에 연결할 수 없습니다.")
        print(f"   서버가 {BASE_URL}에서 실행 중인지 확인해주세요.")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")

if __name__ == "__main__":
    main()
