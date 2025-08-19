from langchain_openai import AzureChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools.render import render_text_description
from .tools.agent_tools import check_availability, create_reservation

from dotenv import load_dotenv, find_dotenv
# 프로젝트 루트에서 가장 가까운 .env.local 찾아 로드
load_dotenv(find_dotenv(".env.local"))

llm = AzureChatOpenAI(azure_deployment="o4-mini", api_version="2024-12-01-preview")
tools = [check_availability, create_reservation]

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "너는 차량 예약 에이전트다. 가능한 한 간결히 한국어로 답한다. "
     "필요하면 도구를 사용한다. 사용 가능한 도구 목록:\n{tools}"),
    MessagesPlaceholder("chat_history"),      # 쓰려면 invoke에 chat_history 전달
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),  # 필수
])

# ⬇️ tools 문자열을 프롬프트에 바인딩(버전 이슈 대비)
prompt = prompt.partial(tools=render_text_description(tools))

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

if __name__ == "__main__":
    out = executor.invoke({
        "input": "2025-08-20T10:00:00Z부터 14:00:00Z까지 차량 예약해줘. 차량 종류는 상관없어. 내 아이디는 u_001이야.",
        "chat_history": []  # ⬅ 없으면 MessagesPlaceholder 지우기
    })
    print(out["output"])