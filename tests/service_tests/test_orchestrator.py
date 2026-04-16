import os
from utils import setup_path
setup_path("orchestrator")

from agent.llm_client import get_llm_client, GeminiClient

def test_orchestrator_llm_client():
    print("Testing Orchestrator LLM Client Factory...")
    os.environ["GEMINI_API_KEY"] = "test-key"
    client = get_llm_client()
    print(f"- Client Type: {type(client).__name__}")
    assert isinstance(client, GeminiClient)

if __name__ == "__main__":
    test_orchestrator_llm_client()
