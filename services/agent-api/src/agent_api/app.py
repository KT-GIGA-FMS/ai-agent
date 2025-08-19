# 최소 확인용: FastAPI + LangChain(툴콜 2개)
from dotenv import load_dotenv; 
load_dotenv(".env.local")  # 없으면 무시

import os
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from pydantic import BaseModel

from langchain_openai import AzureChatOpenAI
from langchain.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

KST = timezone(timedelta(hours=9))

# ---- (1) 아주 간단한 툴 2개 ----
@tool("ping", return_direct=False)
def ping(text: str) -> str:
    """에이전트가 툴을 부를 수 있는지 확인용. 입력을 그대로 되돌린다."""
    return f"pong: {text}"

@tool("now_kst", return_direct=False)
def now_kst() -> str:
    """현재 한국시간(KST)을 ISO-8601로 반환한다."""
    return datetime.now(tz=KST).isoformat()

TOOLS = [ping, now_kst]

# ---- (2) LLM & 에이전트 구성 ----
SYSTEM = """너는 테스트용 보조 에이전트다.
- 사용자가 '핑'이라고 하면 ping 툴을 호출해라.
- 사용자가 '현재 시간'을 물으면 now_kst 툴을 호출해라.
- 한국어로 간단히 답하라.
"""

def build_agent() -> AgentExecutor:
    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),  # 배포 이름
        temperature=0,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM + "\n\n[사용 가능한 도구]\n{tools}"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),   # ← 필수
    ])
    agent = create_tool_calling_agent(llm, TOOLS, prompt)
    executor = AgentExecutor(agent=agent, tools=TOOLS, verbose=True)

    return AgentExecutor(agent=agent, tools=TOOLS, verbose=True)

app = FastAPI(title="Agent API (smoke test)")
AGENT = build_agent()

class InvokeIn(BaseModel):
    input: str

@app.post("/agent/invoke")
def invoke(body: InvokeIn):
    out = AGENT.invoke({"input": body.input})
    return {"answer": out["output"]}

@app.get("/health")
def health():
    return {"ok": True, "tools": [t.name for t in TOOLS]}

@app.get("/debug/env")
def debug_env():
    keys = ["AZURE_OPENAI_ENDPOINT","AZURE_OPENAI_API_KEY","AZURE_OPENAI_DEPLOYMENT","AZURE_OPENAI_API_VERSION"]
    def mask(v): return (v[:6] + "…") if v else None
    return {k: mask(os.getenv(k)) for k in keys}

@app.get("/debug/llm")
def debug_llm():
    try:
        llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION","2024-02-01"),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            temperature=0,
        )
        resp = llm.invoke("한국어로 'pong' 한 단어만 답해.")
        return {"ok": True, "content": resp.content}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})