import os
import time
import uuid
import vertexai
from vertexai.preview import reasoning_engines

# Set environment variables
os.environ["GOOGLE_CLOUD_PROJECT"] = "genaillentsearch"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

vertexai.init(project="genaillentsearch", location="us-central1")

# Use our deployed reasoning engine ID
deployed_id = "7895861829652447232"
engine = reasoning_engines.ReasoningEngine(deployed_id)

user_id = f"test-user-{uuid.uuid4().hex[:8]}"
print(f"Creating remote sessions for user {user_id}...")
session_1 = engine.create_session(user_id=user_id)
session_id_1 = session_1["id"]
session_2 = engine.create_session(user_id=user_id)
session_id_2 = session_2["id"]
print(f"Created sessions: {session_id_1}, {session_id_2}")

print(f"--- Start Deployed Session 1 (User: {user_id}, Session: {session_id_1}) ---")
query_1 = "Hello! My favorite color is magenta and I live in Paris. What is my favorite color?"
print(f"Query 1: {query_1}")

# Call deployed agent via stream_query
response_stream_1 = engine.stream_query(
    message=query_1,
    user_id=user_id,
    session_id=session_id_1
)

for event_dict in response_stream_1:
    if event_dict.get("content"):
        print("Deployed Agent Response 1:", event_dict["content"]["parts"][0]["text"])

print("\n--- Waiting 45 seconds for remote Memory Bank consolidation... ---")
time.sleep(45)

print(f"\n--- Start Deployed Session 2 (User: {user_id}, Session: {session_id_2}) ---")
query_2 = "Hi there! What color do I like and where do I live? Do not search the web."
print(f"Query 2: {query_2}")

response_stream_2 = engine.stream_query(
    message=query_2,
    user_id=user_id,
    session_id=session_id_2
)

for event_dict in response_stream_2:
    if event_dict.get("content"):
        print("Deployed Agent Response 2:", event_dict["content"]["parts"][0]["text"])
