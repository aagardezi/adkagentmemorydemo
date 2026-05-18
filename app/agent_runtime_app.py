# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import os
from typing import Any

import vertexai
from dotenv import load_dotenv
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from google.cloud import logging as google_cloud_logging
from vertexai.agent_engines.templates.adk import AdkApp

from app.agent import app as adk_app
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback
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

    await api_client.agent_engines.memories.ingest_events(**request_kwargs)

vms.VertexAiMemoryBankService._add_events_to_memory_via_ingest = patched_ingest


# Load environment variables from .env file at runtime
load_dotenv()


class AgentEngineApp(AdkApp):
    def set_up(self) -> None:
        """Initialize the agent engine app with logging and telemetry."""
        vertexai.init()
        setup_telemetry()

        from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService
        from google.adk.memory.vertex_ai_memory_bank_service import VertexAiMemoryBankService

        project = os.environ.get("GOOGLE_CLOUD_PROJECT") or "genaillentsearch"
        location = os.environ.get("GOOGLE_CLOUD_LOCATION") or "us-central1"
        agent_engine_id = os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID") or "7895861829652447232"

        self._tmpl_attrs["session_service_builder"] = lambda: VertexAiSessionService(
            project=project,
            location=location,
            agent_engine_id=agent_engine_id,
        )
        self._tmpl_attrs["memory_service_builder"] = lambda: VertexAiMemoryBankService(
            project=project,
            location=location,
            agent_engine_id=agent_engine_id,
        )

        super().set_up()
        logging.basicConfig(level=logging.INFO)
        logging_client = google_cloud_logging.Client()
        self.logger = logging_client.logger(__name__)
        if gemini_location:
            os.environ["GOOGLE_CLOUD_LOCATION"] = gemini_location

    def register_feedback(self, feedback: dict[str, Any]) -> None:
        """Collect and log feedback."""
        feedback_obj = Feedback.model_validate(feedback)
        self.logger.log_struct(feedback_obj.model_dump(), severity="INFO")

    def register_operations(self) -> dict[str, list[str]]:
        """Registers the operations of the Agent."""
        operations = super().register_operations()
        # Strip unsupported api modes to avoid server-side registration failure
        operations.pop("async", None)
        operations.pop("async_stream", None)
        operations[""] = [*operations.get("", []), "register_feedback"]
        return operations


gemini_location = os.environ.get("GOOGLE_CLOUD_LOCATION")
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")


agent_runtime = AgentEngineApp(
    app=adk_app,
    artifact_service_builder=lambda: (
        GcsArtifactService(bucket_name=logs_bucket_name)
        if logs_bucket_name
        else InMemoryArtifactService()
    ),
)
