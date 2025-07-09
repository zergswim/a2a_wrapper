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