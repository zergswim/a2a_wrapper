**a2a_wrapper** 는 복잡한 Agent2Agent (A2A) SDK를 간결화하여, 개발자가 비즈니스 로직에만 집중할 수 있도록 돕는 Python 라이브러리입니다.

* 본 라이브러리는 .env 파일과 아래와 같은 패키지를 필요로 합니다.

* API 키 설정 복사
```bash
cp .env_sample .env
```

* 필수 패키지 설치
```bash
pip install a2a-sdk
pip install asynco
```

* 테스트용 에이전트
[test_agent.py]
```Python
import asyncio
import uvicorn
import a2a_wrapper
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

async def main():

    agent_url = "http://localhost"
    agent_host = "localhost"
    agent_port = 9999
    agent_name = "test_agent"
    agent_model = "gemini-2.5-flash-preview-05-20"
    agent_instruction = "테스트 호출 결과를 반환합니다."
    agent_list = [
        # "http://localhost:8001/",
    ] # (a2a 연결을 위한) 다른 에이전트 url

    agent_card = AgentCard(
        name=agent_name,
        description=agent_instruction,
        skills=[],
        defaultInputModes=["text", "text/plain"],
        defaultOutputModes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        version="1.0.0",                
        url=f"{agent_url}:{agent_port}", # 이 에이전트의 주소
    )

    # 테스트용 함수
    async def call_test_function(prompt: str):
        """테스트 호출 결과를 반환합니다."""
        try:
            rtn = f"[PROMPT]: {prompt}"
            return rtn
        except Exception as e:
            return f"[ERROR]: {e.stderr}"
        
    app = await a2a_wrapper.create_agent_a2a_server2(agent_name, agent_model, agent_instruction, agent_list, agent_card, [call_test_function])

    config = uvicorn.Config(app.build(), host=agent_host, port=agent_port, log_level="info")
    uvicorn_server = uvicorn.Server(config)

    print(f"Host (A2A Server) starting on {agent_url}:{agent_port}")
    print(f"Agent Card will be available at {agent_url}:{agent_port}/.well-known/agent.json")
    await uvicorn_server.serve()    

if __name__ == "__main__":
    asyncio.run(main())

```

* 테스트용 에이전트 호출코드
[test.py]
```Python
import asyncio
import a2a_wrapper

async def main():
    HOST_AGENT_URL = "http://localhost:9999"  # A2A Host Agent URL
    question = "너의 스킬을 알려주고, 테스트 함수를 호출해줘"

    result = await a2a_wrapper.run_requester_agent(HOST_AGENT_URL, question)
    print("[Host Agent Result]")
    print(result.root.result.artifacts[0].parts[0].root.text)

if __name__ == "__main__":
    asyncio.run(main())
```