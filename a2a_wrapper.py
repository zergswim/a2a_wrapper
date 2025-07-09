from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    Part,
    TaskState,
    TextPart,
    MessageSendParams,    
    SendMessageRequest,
    Message
)
from a2a.utils import new_agent_text_message, new_task
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from typing import Any
import requests
import httpx
import uuid
from a2a.client import A2AClient
from google.adk.agents import Agent

# Generic A2A Executor for any ADK agent
import json
from dotenv import load_dotenv

load_dotenv()

async def run_requester_agent(agent_url, query):
    timeout_config = httpx.Timeout(None, connect=10.0)
    # Timeout(
    #     # timeout=120,
    #     timeout=240,
    #     connect=20.0,
    #     read=240,
    #     write=20.0,
    #     pool=10.0
    # )    

    async with httpx.AsyncClient(timeout=timeout_config) as http_client:
        try:
            a2a_client = await A2AClient.get_client_from_agent_card_url(
                httpx_client=http_client, 
                base_url=agent_url,
            )

        except Exception as e:
            print(f"Error creating A2A client or fetching agent card: {e}")
            return

        # 2. 요약 요청 메시지 생성
        request_message = Message(
            messageId=uuid.uuid4().hex,
            role="user", # 또는 다른 클라이언트 에이전트 역할
            parts=[TextPart(type="text", text=query)],
        )

        send_params = MessageSendParams(message=request_message)
        a2a_request = SendMessageRequest(id=str(uuid.uuid4()), params=send_params)
        
        try:
            # 3. send_message 호출 (A2A SDK는 내부적으로 JSON-RPC 요청을 보냄)
            return await a2a_client.send_message(request=a2a_request)
        except httpx.RequestError as e:
            print(f"HTTP request error while communicating with SummarizerAgent: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

class ADKAgentExecutor(AgentExecutor):
    def __init__(self, agent, status_message="Processing request...", artifact_name="response"):
        """Initialize a generic ADK agent executor.

        Args:
            agent: The ADK agent instance
            status_message: Message to display while processing
            artifact_name: Name for the response artifact
        """
        self.agent = agent
        self.status_message = status_message
        self.artifact_name = artifact_name
        self.runner = Runner(
            app_name=agent.name,
            agent=agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    async def cancel(self, task_id: str) -> None:
        """Cancel the execution of a specific task."""
        # Implementation for cancelling tasks

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        task = context.current_task or new_task(context.message)
        await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.contextId)

        try:
            # Update status with custom message
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(self.status_message, task.contextId, task.id)
            )

            # Process with ADK agent
            session = await self.runner.session_service.create_session(
            # 'await'를 제거하고 동기적으로 호출합니다.
            # session = self.runner.session_service.create_session(                
                app_name=self.agent.name,
                user_id="a2a_user",
                state={},
                session_id=task.contextId,
            )

            content = types.Content(
                role='user',
                parts=[types.Part.from_text(text=query)]
            )

            print(f"[AGENT NAME]: {self.agent.name}")

            response_text = ""
            async for event in self.runner.run_async(
                user_id="a2a_user",
                session_id=session.id,
                new_message=content
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text + '\n'
                            print(f"[RESPONSE PART]: {part.text}")
                        elif hasattr(part, 'function_call'):
                            print(f"[FUNCTION CALL detected]: {part.function_call}")
                            # Log or handle function calls if needed
                            pass  # Function calls are handled internally by ADK
                        else:
                            print(f"[UNKNOWN PART]: {part}")

            # Add response as artifact with custom name
            await updater.add_artifact(
                [Part(root=TextPart(text=response_text))],
                name=self.artifact_name
            )

            await updater.complete()

        except Exception as e:
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(f"Error: {e!s}", task.contextId, task.id),
                final=True
            )

# Generic function to create an A2A server for any ADK agent

class A2AToolClient:
    """A2A client."""

    def __init__(self, default_timeout: float = 120.0):
        # Cache for agent metadata - also serves as the list of registered agents
        # None value indicates agent is registered but metadata not yet fetched
        self._agent_info_cache: dict[str, dict[str, Any] | None] = {}
        # Default timeout for requests (in seconds)
        self.default_timeout = default_timeout

    def add_remote_agent(self, agent_url: str):
        """Add agent to the list of available remote agents."""
        normalized_url = agent_url.rstrip('/')
        if normalized_url not in self._agent_info_cache:
            # Initialize with None to indicate metadata not yet fetched
            self._agent_info_cache[normalized_url] = None

    def list_remote_agents(self) -> list[dict[str, Any]]:
        """List available remote agents with caching."""
        if not self._agent_info_cache:
            return []

        remote_agents_info = []
        for remote_connection in self._agent_info_cache:
            # Use cached data if available
            if self._agent_info_cache[remote_connection] is not None:
                remote_agents_info.append(self._agent_info_cache[remote_connection])
            else:
                try:
                    # Fetch and cache agent info
                    agent_info = requests.get(f"{remote_connection}/.well-known/agent.json")
                    agent_data = agent_info.json()
                    self._agent_info_cache[remote_connection] = agent_data
                    remote_agents_info.append(agent_data)
                except Exception as e:
                    print(f"Failed to fetch agent info from {remote_connection}: {e}")

        return self._agent_info_cache

    async def create_task(self, agent_url: str, message: str) -> str:
        """Send a message following the official A2A SDK pattern."""
        # Configure httpx client with timeout
        timeout_config = httpx.Timeout(
            timeout=self.default_timeout,
            connect=10.0,
            read=self.default_timeout,
            write=10.0,
            pool=5.0
        )

        async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
            # Check if we have cached agent card data
            if agent_url in self._agent_info_cache and self._agent_info_cache[agent_url] is not None:
                agent_card_data = self._agent_info_cache[agent_url]
            else:
                # Fetch the agent card
                # agent_card_response = await httpx_client.get(f"{agent_url}/.well-known/agent.json")
                agent_card_response = await httpx_client.get(f"{agent_url}.well-known/agent.json")
                agent_card_data = agent_card_response.json()

            # Create AgentCard from data
            agent_card = AgentCard(**agent_card_data)

            # Create A2A client with the agent card
            client = A2AClient(
                httpx_client=httpx_client,
                agent_card=agent_card
            )

            # Build the message parameters following official structure
            send_message_payload = {
                'message': {
                    'role': 'user',
                    'parts': [
                        {'kind': 'text', 'text': message}
                    ],
                    'messageId': uuid.uuid4().hex,
                }
            }

            # Create the request
            request = SendMessageRequest(
                id=str(uuid.uuid4()),
                params=MessageSendParams(**send_message_payload)
            )

            # Extract text from response
            try:
                # Send the message with timeout configuration
                response = await client.send_message(request)
                print(f"[HOST Response]: {response}")

                response_dict = response.model_dump(mode='json', exclude_none=True)
                if 'result' in response_dict and 'artifacts' in response_dict['result']:
                    artifacts = response_dict['result']['artifacts']
                    for artifact in artifacts:
                        if 'parts' in artifact:
                                for part in artifact['parts']:
                                    if 'text' in part:
                                        return part['text']

                # If we couldn't extract text, return the full response as formatted JSON
                return json.dumps(response_dict, indent=2)

            except Exception as e:
                # Log the error and return string representation
                print(f"Error parsing response: {e}")
                return str(response)

    def remove_remote_agent(self, agent_url: str):
        """Remove an agent from the list of available remote agents."""
        normalized_url = agent_url.rstrip('/')
        if normalized_url in self._agent_info_cache:
            del self._agent_info_cache[normalized_url]

async def create_agent_a2a_server2(agent_name, agent_model, agent_instruction, agent_list, agent_card, my_functions):
    a2a_client = A2AToolClient(default_timeout=160.0)

    #agent_list 등록
    for agent_url in agent_list:
        a2a_client.add_remote_agent(agent_url)

    tools = [a2a_client.list_remote_agents, a2a_client.create_task]

    for function in my_functions:
        tools.append(function)

    my_executor = ADKAgentExecutor(
        Agent(
                model=agent_model,
                name=agent_name,
                instruction=agent_instruction,
                tools=tools,
            )
    )    

    request_handler = DefaultRequestHandler(
        agent_executor=my_executor,
        task_store=InMemoryTaskStore(),
    )

    return A2AStarletteApplication(agent_card=agent_card, http_handler=request_handler)


# async def create_agent_a2a_server(
#     agent,
#     name,
#     description,
#     skills,
#     host="localhost",
#     port=10020,
#     status_message="Processing request...",
#     artifact_name="response"
# ):
#     """Create an A2A server for any ADK agent.

#     Args:
#         agent: The ADK agent instance
#         name: Display name for the agent
#         description: Agent description
#         skills: List of AgentSkill objects
#         host: Server host
#         port: Server port
#         status_message: Message shown while processing
#         artifact_name: Name for response artifacts

#     Returns:
#         A2AStarletteApplication instance
#     """

#     # Agent card (metadata)
#     agent_card = AgentCard(
#         name=name,
#         description=description,
#         url=f"http://{host}:{port}/",
#         version="1.0.0",
#         defaultInputModes=["text", "text/plain"],
#         defaultOutputModes=["text", "text/plain"],
#         capabilities=AgentCapabilities(streaming=True),
#         skills=skills,
#     )

#     # Create executor with custom parameters
#     executor = ADKAgentExecutor(
#         agent=agent,
#         status_message=status_message,
#         artifact_name=artifact_name
#     )

#     request_handler = DefaultRequestHandler(
#         agent_executor=executor,
#         task_store=InMemoryTaskStore(),
#     )

#     # Create A2A application
#     return A2AStarletteApplication(
#         agent_card=agent_card,
#         http_handler=request_handler
#     )