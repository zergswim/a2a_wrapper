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
        # "http://localhost:8002/",
        # "http://localhost:8003/"
    ]

    agent_card = AgentCard(
        name=agent_name,
        description=agent_instruction,
        skills=[],
        defaultInputModes=["text", "text/plain"],
        defaultOutputModes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        version="1.0.0",                
        url=f"{agent_url}:{agent_port}", # 이 에이전트의 주소
        # service_endpoint="http://localhost:8001", # 이 에이전트의 주소
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
