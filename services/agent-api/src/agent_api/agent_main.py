from langchain_openai import AzureChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools.render import render_text_description
from tools.agent_tools import check_availability, create_reservation

from dotenv import load_dotenv, find_dotenv
import os
# 프로젝트 루트에서 가장 가까운 .env.local 찾아 로드
load_dotenv(find_dotenv(".env.local"))
# dotenv 파일에서 모델 찾아서 가져오기

# 성능 최적화된 LLM 설정
llm = AzureChatOpenAI(
    # azure_deployment="o4-mini", 
    

    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    # 응답 품질 최적화
    # temperature=0.1,  # 낮은 temperature로 일관된 응답
    top_p=0.9,  # 토큰 선택 다양성 조절
    
    # 성능 최적화
    max_tokens=400,  # 차량 예약 응답에 적합한 길이
    request_timeout=8,  # 5초 이내 응답을 위한 적절한 타임아웃
    
    # 안정성 향상
    max_retries=2,  # 네트워크 오류 시 재시도
    # retry_delay=1,  # 재시도 간격
    
    # 비용 최적화
    streaming=False,  # 배치 처리를 위해 스트리밍 비활성화
)

tools = [check_availability, create_reservation]

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "너는 법인 차량 예약 시스템의 친근하고 지능적인 AI 에이전트다.\n\n"
     "## 핵심 원칙\n"
     "- 사용자 친화적이고 자연스러운 대화\n"
     "- 지능적인 정보 추론 및 변환\n"
     "- 명확하고 간결한 응답\n\n"
     "## 지능적 정보 처리\n"
     "사용자가 다양한 형식으로 정보를 제공할 수 있다:\n"
     "- 시간: '내일 오후 2시', '2025-01-16T14:00:00Z', '오후 3시부터 5시까지'\n"
     "- 사용자 ID: 'u001', 'u_001', '001' → 모두 'u_001'로 정규화\n"
     "- 날짜: '내일', '다음주 월요일', '2025-01-16' → 적절한 날짜로 변환\n\n"
     "## 도구 사용 규칙\n"
     "1. **check_availability**: 가용 차량 확인 시 차량 정보 전체를 반환받음\n"
     "2. **create_reservation**: vehicle_id는 반드시 차량의 실제 ID(예: 'uuid-1')를 사용\n"
     "   - 차량 이름(예: 'Avante')이 아닌 ID를 사용해야 함\n"
     "   - check_availability에서 반환된 차량의 'id' 필드를 사용\n\n"
     "## 처리 순서\n"
     "1. check_availability로 가용 차량 확인\n"
     "2. 반환된 차량 정보에서 'id' 필드를 추출\n"
     "3. create_reservation 호출 시 해당 'id'를 vehicle_id로 사용\n\n"
     "## 대화 상태 관리\n"
     "매 응답 끝에 다음 형식으로 상태를 표시하라:\n"
     "---STATUS: [상태]---\n"
     "상태 옵션:\n"
     "- CONTINUE: 추가 정보가 필요하거나 대화를 계속해야 함\n"
     "- RESERVATION_COMPLETE: 예약이 성공적으로 완료됨\n"
     "- USER_CANCELLED: 사용자가 예약을 원하지 않음\n"
     "- ERROR: 오류가 발생함\n\n"
     "사용 가능한 도구:\n{tools}"),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

# ⬇️ tools 문자열을 프롬프트에 바인딩(버전 이슈 대비)
prompt = prompt.partial(tools=render_text_description(tools))

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

class ReservationSession:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.user_id = None
        self.vehicle_preferences = {}  # fuel_type, car_type 등
        self.chat_history = []
    
    def is_complete(self):
        """예약에 필요한 모든 정보가 있는지 확인"""
        return all([self.start_time, self.end_time, self.user_id])
    
    def get_missing_info(self):
        """누락된 정보 목록 반환"""
        missing = []
        if not self.start_time:
            missing.append("시작 시간")
        if not self.end_time:
            missing.append("종료 시간")
        if not self.user_id:
            missing.append("사용자 ID")
        return missing
    
    def get_current_info(self):
        """현재 입력된 정보 요약"""
        info = []
        if self.start_time:
            info.append(f"시작 시간: {self.start_time}")
        if self.end_time:
            info.append(f"종료 시간: {self.end_time}")
        if self.user_id:
            info.append(f"사용자 ID: {self.user_id}")
        if self.vehicle_preferences:
            prefs = []
            if 'fuel_type' in self.vehicle_preferences:
                prefs.append(f"연료: {self.vehicle_preferences['fuel_type']}")
            if 'car_type' in self.vehicle_preferences:
                prefs.append(f"차량 타입: {self.vehicle_preferences['car_type']}")
            if prefs:
                info.append(f"선호사항: {', '.join(prefs)}")
        return info
    
    def extract_info_from_message(self, message):
        """메시지에서 예약 정보 추출"""
        # 시간 정보 추출 (간단한 패턴 매칭)
        import re
        from datetime import datetime
        
        # ISO8601 형식 시간 찾기
        time_pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z'
        times = re.findall(time_pattern, message)
        
        if len(times) >= 2 and not self.start_time and not self.end_time:
            self.start_time = times[0]
            self.end_time = times[1]
        
        # 사용자 ID 추출
        user_pattern = r'u_\d+'
        user_match = re.search(user_pattern, message)
        if user_match and not self.user_id:
            self.user_id = user_match.group()
        
        # 차량 선호도 추출
        if '전기차' in message or 'electric' in message.lower():
            self.vehicle_preferences['fuel_type'] = 'electric'
        if 'SUV' in message or 'suv' in message.lower():
            self.vehicle_preferences['car_type'] = 'suv'

def parse_conversation_status(response: str) -> str:
    """응답에서 대화 상태를 파싱하는 함수"""
    import re
    
    # 상태 패턴 찾기
    status_pattern = r'---STATUS:\s*(\w+)---'
    match = re.search(status_pattern, response)
    
    if match:
        return match.group(1)
    
    # 기본값
    return "CONTINUE"

def clean_response(response: str) -> str:
    """상태 표시를 제거한 깔끔한 응답 반환"""
    import re
    
    # 상태 표시 제거
    cleaned = re.sub(r'---STATUS:\s*\w+---', '', response)
    return cleaned.strip()

def run_reservation_chat():
    """대화형 예약 시스템"""
    session = ReservationSession()
    
    print("�� 차량 예약 시스템에 오신 것을 환영합니다!")
    print("언제부터 언제까지 차량을 사용하실 건가요?")
    print("(입력된 정보 확인: '확인', 예약 취소: '취소')")
    
    while not session.is_complete():
        user_input = input("사용자: ").strip()
        
        if user_input.lower() in ['quit', 'exit', '종료', '취소']:
            print("예약이 취소되었습니다.")
            return
        
        # 현재 정보 확인 요청
        if user_input.lower() in ['확인', 'check', 'info', '정보']:
            current_info = session.get_current_info()
            if current_info:
                print("📋 현재 입력된 정보:")
                for info in current_info:
                    print(f"   {info}")
            else:
                print("📋 아직 입력된 정보가 없습니다.")
            
            missing = session.get_missing_info()
            if missing:
                print(f"❌ 누락된 정보: {', '.join(missing)}")
            print()  # 빈 줄 추가
            continue
        
        # 메시지에서 정보 추출
        session.extract_info_from_message(user_input)
        
        # 누락된 정보 확인
        missing = session.get_missing_info()
        
        if missing:
            # 현재 정보 표시
            current_info = session.get_current_info()
            if current_info:
                print("📋 현재 입력된 정보:")
                for info in current_info:
                    print(f"   {info}")
                print()
            
            # 누락된 정보 요청
            if len(missing) == 1:
                print(f"❌ {missing[0]}을(를) 알려주세요.")
            else:
                print(f"❌ {', '.join(missing[:-1])}과(와) {missing[-1]}을(를) 알려주세요.")
            
            # 구체적인 안내
            if "시작 시간" in missing or "종료 시간" in missing:
                print("   �� 시간 형식: 2025-01-15T10:00:00Z (예시)")
            if "사용자 ID" in missing:
                print("   �� 사용자 ID 형식: u_001 (예시)")
            print()
        else:
            # 모든 정보가 있으면 예약 진행
            break
    
    # 최종 확인
    print("�� 예약 정보 최종 확인:")
    current_info = session.get_current_info()
    for info in current_info:
        print(f"   {info}")
    
    confirm = input("\n예약을 진행하시겠습니까? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes', '예', '네']:
        print("예약이 취소되었습니다.")
        return
    
    # 예약 실행
    print("\n🔄 예약을 진행하겠습니다...")
    
    try:
        # 가용성 확인
        availability_result = check_availability(
            from_time=session.start_time,
            to_time=session.end_time,
            fuel_type=session.vehicle_preferences.get('fuel_type'),
            car_type=session.vehicle_preferences.get('car_type')
        )
        
        if not availability_result:
            print("❌ 죄송합니다. 해당 시간에 사용 가능한 차량이 없습니다.")
            print("다른 시간대나 차량 타입을 시도해보시겠어요?")
            return
        
        # 예약 생성
        reservation_result = create_reservation(
            user_id=session.user_id,
            vehicle_id=availability_result[0]['id'],
            from_time=session.start_time,
            to_time=session.end_time
        )
        
        if 'error' in reservation_result:
            print(f"❌ 예약에 실패했습니다. {reservation_result['error']}")
        else:
            print(f"✅ 예약이 완료되었습니다!")
            print(f"   🚗 차량: {availability_result[0]['car_model_name']}")
            print(f"   ⏰ 시간: {session.start_time} ~ {session.end_time}")
            print(f"   📝 예약 번호: {reservation_result['id']}")
    
    except Exception as e:
        print(f"❌ 예약 중 오류가 발생했습니다. {str(e)}")

def run_reservation_chat_with_agent():
    """LangChain 에이전트를 사용한 대화형 예약 시스템"""
    chat_history = []
    
    print(" 차량 예약 시스템에 오신 것을 환영합니다!")
    print("자연어로 예약 요청을 해주세요. (예: '내일 오후 2시부터 6시까지 차량 예약하고 싶어. u_001이야')")
    print("(종료: 'quit', 'exit', '종료', '취소')")
    
    while True:
        user_input = input("사용자: ").strip()
        
        if user_input.lower() in ['quit', 'exit', '종료', '취소']:
            print("예약이 취소되었습니다.")
            break
        
        try:
            print("🤖 AI 에이전트가 처리 중...")
            
            # LangChain 에이전트 호출
            result = executor.invoke({
                "input": user_input,
                "chat_history": chat_history
            })
            
            response = result["output"]
            
            # 상태 파싱
            status = parse_conversation_status(response)
            clean_response_text = clean_response(response)
            
            print(f"에이전트: {clean_response_text}")
            
            # 대화 히스토리 업데이트 (깔끔한 응답만 저장)
            chat_history.append(("human", user_input))
            chat_history.append(("ai", clean_response_text))
            
            # 상태에 따른 처리
            if status == "RESERVATION_COMPLETE":
                print("\n🎉 예약이 완료되었습니다. 시스템을 종료합니다.")
                break
            elif status == "USER_CANCELLED":
                print("\n👋 예약이 취소되었습니다. 시스템을 종료합니다.")
                break
            elif status == "ERROR":
                print("\n❌ 오류가 발생했습니다. 시스템을 종료합니다.")
                break
            # CONTINUE 상태는 계속 진행
            
        except Exception as e:
            print(f"❌ 오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    # LangChain 에이전트 사용
    run_reservation_chat_with_agent()
    
    # 또는 기존 방식 사용
    # run_reservation_chat()