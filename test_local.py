import os
import time
import uuid

from google.adk.memory import VertexAiMemoryBankService
from google.adk.runners import Runner
from google.adk.sessions import VertexAiSessionService
from google.genai import types
import datetime
import google.adk.memory.vertex_ai_memory_bank_service as vms

async def patched_ingest(self, *, app_name, user_id, events_to_process, custom_metadata=None):
    import vertexai
    direct_events = []
    for event in events_to_process:
      if vms._should_filter_out_event(event.content):
        continue
      if event.content:
        event_time = None
        if event.timestamp is not None:
          event_time = datetime.datetime.fromtimestamp(
              event.timestamp, tz=datetime.timezone.utc
          )
        direct_events.append(
            vertexai.types.IngestionDirectContentsSourceEvent(
                content=event.content,
                event_id=event.id,
                event_time=event_time,
            )
        )

    api_client = self._get_api_client()

    stream_id = custom_metadata.get('stream_id') if custom_metadata else None
    force_flush = (
        custom_metadata.get('force_flush') if custom_metadata else None
    )
    generation_trigger_config = (
        custom_metadata.get('generation_trigger_config')
        if custom_metadata
        else None
    )

    request_kwargs = {
        'name': 'reasoningEngines/' + self._agent_engine_id,
        'scope': {
            'app_name': app_name,
            'user_id': user_id,
        },
    }
    if direct_events:
      request_kwargs['direct_contents_source'] = (
          vertexai.types.IngestionDirectContentsSource(events=direct_events)
      )
    if stream_id:
      request_kwargs['stream_id'] = stream_id
    config = {}
    if force_flush is not None:
      config['force_flush'] = force_flush
    if config:
      request_kwargs['config'] = config
    if generation_trigger_config:
      request_kwargs['generation_trigger_config'] = generation_trigger_config

    print("\n--- [PATCH] Awaiting IngestEvents synchronously... ---")
    await api_client.agent_engines.memories.ingest_events(**request_kwargs)
    print("--- [PATCH] IngestEvents completed! ---")

vms.VertexAiMemoryBankService._add_events_to_memory_via_ingest = patched_ingest


from app.agent import root_agent

# Set environment variables
os.environ["GOOGLE_CLOUD_PROJECT"] = "genaillentsearch"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# Use our deployed reasoning engine ID
deployed_id = "7895861829652447232"

memory_service = VertexAiMemoryBankService(
    project="genaillentsearch", location="us-central1", agent_engine_id=deployed_id
)

session_service = VertexAiSessionService(
    project="genaillentsearch", location="us-central1", agent_engine_id=deployed_id
)

runner = Runner(
    agent=root_agent,
    app_name="stateful_search_app",
    session_service=session_service,
    memory_service=memory_service,
    auto_create_session=True,
)

user_id = f"test-user-{uuid.uuid4().hex[:8]}"
session_id_1 = f"session-1-{uuid.uuid4().hex[:8]}"
session_id_2 = f"session-2-{uuid.uuid4().hex[:8]}"


print(f"--- Start Session 1 (User: {user_id}, Session: {session_id_1}) ---")
query_1 = "Hello! My name is sgardezi. My favorite color is cyan and I live in Boston. What is my favorite color?"
print(f"Query 1: {query_1}")

content_1 = types.Content(role="user", parts=[types.Part.from_text(text=query_1)])
for event in runner.run(
    user_id=user_id, session_id=session_id_1, new_message=content_1
):
    if event.is_final_response():
        print("Agent Response 1:", event.content.parts[0].text)

# Clear cached api_clients on the model to avoid closed event loop error in subsequent thread runs
for cache_key in ["api_client", "_live_api_client", "_api_backend"]:
    if cache_key in root_agent.model.__dict__:
        del root_agent.model.__dict__[cache_key]

print("\n--- Waiting 45 seconds for Memory Bank consolidation LRO... ---")
time.sleep(45)

print(f"\n--- Start Session 2 (User: {user_id}, Session: {session_id_2}) ---")
query_2 = "Hi there! What is my name, where do I live, and what color do I like? Do not search the web."
print(f"Query 2: {query_2}")

content_2 = types.Content(role="user", parts=[types.Part.from_text(text=query_2)])
for event in runner.run(
    user_id=user_id, session_id=session_id_2, new_message=content_2
):
    if event.is_final_response():
        print("Agent Response 2:", event.content.parts[0].text)
