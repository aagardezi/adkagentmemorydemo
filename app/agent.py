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

import os

import google.auth
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools import google_search
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = (
    "us-central1"  # Using us-central1 for Vertex AI / Memory Bank
)
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback triggered after agent run to extract and consolidate memories."""
    # Process and extract memories from the session history
    await callback_context.add_session_to_memory()
    return None


root_agent = Agent(
    name="stateful_search_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a stateful assistant with access to Google Search and long-term memory. "
        "Use Google Search to answer general questions when needed. "
        "You will also receive long-term memories about the user. "
        "Use these memories to personalize your responses and recall past facts about the user. "
        "Keep your answers concise and friendly."
    ),
    tools=[google_search, PreloadMemoryTool()],
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="stateful_search_app",
)
