from langchain_openai import AzureChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools.render import render_text_description
from .tools.agent_tools import check_availability, create_reservation

from dotenv import load_dotenv, find_dotenv
# 프로젝트 루트에서 가장 가까운 .env.local 찾아 로드
load_dotenv(find_dotenv(".env.local"))

# 성능 최적화된 LLM 설정
llm = AzureChatOpenAI(
    azure_deployment="o4-mini", 
    api_version="2024-12-01-preview",
    
    # 응답 품질 최적화
    temperature=0.1,  # 낮은 temperature로 일관된 응답
    top_p=0.9,  # 토큰 선택 다양성 조절
    
    # 성능 최적화
    max_tokens=400,  # 차량 예약 응답에 적합한 길이
    request_timeout=8,  # 5초 이내 응답을 위한 적절한 타임아웃
    
    # 안정성 향상
    max_retries=2,  # 네트워크 오류 시 재시도
    retry_delay=1,  # 재시도 간격
    
    # 비용 최적화
    streaming=False,  # 배치 처리를 위해 스트리밍 비활성화
)

tools = [check_availability, create_reservation]

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "너는 법인 차량 예약 시스템의 전문 AI 에이전트다.\n\n"
     "## 역할과 규칙\n"
     "- 차량 예약 관련 요청만 처리한다\n"
     "- 한국어로 간결하고 명확하게 응답한다\n"
     "- 시간은 반드시 ISO8601 형식(YYYY-MM-DDTHH:MM:SSZ)으로 처리한다\n"
     "- 예약 전에는 반드시 가용성을 먼저 확인한다\n"
     "- 사용자 ID는 'u_'로 시작하는 형식이어야 한다\n\n"
     "## 필수 파라미터 확인\n"
     "예약 요청 시 다음 정보가 모두 필요하다:\n"
     "1. **시작 시간** (YYYY-MM-DDTHH:MM:SSZ 형식)\n"
     "2. **종료 시간** (YYYY-MM-DDTHH:MM:SSZ 형식)\n"
     "3. **사용자 ID** (u_xxx 형식)\n\n"
     "**누락된 정보가 있으면 도구를 호출하지 말고, 친근하게 빠진 정보를 요청한다.**\n"
     "예시: '예약하려면 시작 시간, 종료 시간, 사용자 ID가 필요해요. 언제부터 언제까지 사용하실 건가요?'\n\n"
     "## 처리 순서\n"
     "1. **필수 파라미터 완전성 검증** (빠진 것이 있으면 여기서 중단하고 요청)\n"
     "2. 사용자 요청 파악 (시간, 차량 조건, 사용자 ID)\n"
     "3. check_availability로 가용 차량 확인\n"
     "4. 적절한 차량이 있으면 create_reservation으로 예약 생성\n"
     "5. 결과를 명확하게 사용자에게 안내\n\n"
     "## 에러 대응\n"
     "- **필수 정보 누락**: 도구 호출 없이 친근하게 빠진 정보 요청\n"
     "- **시간 형식 오류**: 올바른 형식 예시와 함께 재입력 요청\n"
     "- **사용자 ID 형식 오류**: 'u_001' 같은 형식으로 안내\n"
     "- **과거 시간 요청**: '과거 시간으로는 예약할 수 없어요' 안내\n"
     "- **가용 차량 없음**: 다른 시간대나 차량 타입 제안\n"
     "- **예약 실패**: 구체적인 사유와 대안 제시\n\n"
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

def run_reservation_chat():
    """대화형 예약 시스템"""
    session = ReservationSession()
    
    print("🚗 차량 예약 시스템에 오신 것을 환영합니다!")
    print("언제부터 언제까지 차량을 사용하실 건가요?")
    
    while not session.is_complete():
        user_input = input("사용자: ").strip()
        
        if user_input.lower() in ['quit', 'exit', '종료', '취소']:
            print("예약이 취소되었습니다.")
            return
        
        # 메시지에서 정보 추출
        session.extract_info_from_message(user_input)
        
        # 누락된 정보 확인
        missing = session.get_missing_info()
        
        if missing:
            # 누락된 정보 요청
            if len(missing) == 1:
                print(f"에이전트: {missing[0]}을(를) 알려주세요.")
            else:
                print(f"에이전트: {', '.join(missing[:-1])}과(와) {missing[-1]}을(를) 알려주세요.")
            
            # 구체적인 안내
            if "시작 시간" in missing or "종료 시간" in missing:
                print("   시간 형식: 2025-01-15T10:00:00Z (예시)")
            if "사용자 ID" in missing:
                print("   사용자 ID 형식: u_001 (예시)")
        else:
            # 모든 정보가 있으면 예약 진행
            break
    
    # 예약 실행
    print("에이전트: 예약을 진행하겠습니다...")
    
    try:
        # 가용성 확인
        availability_result = check_availability(
            from_time=session.start_time,
            to_time=session.end_time,
            fuel_type=session.vehicle_preferences.get('fuel_type'),
            car_type=session.vehicle_preferences.get('car_type')
        )
        
        if not availability_result:
            print("에이전트: 죄송합니다. 해당 시간에 사용 가능한 차량이 없습니다.")
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
            print(f"에이전트: 예약에 실패했습니다. {reservation_result['error']}")
        else:
            print(f"에이전트: 예약이 완료되었습니다!")
            print(f"   차량: {availability_result[0]['car_model_name']}")
            print(f"   시간: {session.start_time} ~ {session.end_time}")
            print(f"   예약 번호: {reservation_result['id']}")
    
    except Exception as e:
        print(f"에이전트: 예약 중 오류가 발생했습니다. {str(e)}")

if __name__ == "__main__":
    run_reservation_chat()