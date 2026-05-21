import sys
import asyncio
from pathlib import Path

# Add backend to path
sys.path.append("c:/Users/Wissen/Hiring_Platform/backend")

from app.core.config import settings
from app.llm.factory import get_llm_provider

async def test_llm():
    print("LLM Provider configured in settings:", settings.LLM_PROVIDER)
    print("LLM Model configured in settings:", settings.LLM_MODEL)
    print("GROQ API Key configured:", bool(settings.GROQ_API_KEY))
    print("GROK API Key configured:", bool(settings.GROK_API_KEY))
    print("ANTHROPIC API Key configured:", bool(settings.ANTHROPIC_API_KEY))
    
    try:
        provider = get_llm_provider()
        print("Got provider object:", type(provider))
        
        print("Calling complete_json...")
        result = await provider.complete_json(
            system="You are a helpful assistant. Return a JSON object with key 'message'.",
            user="Say hello in JSON",
            max_tokens=100
        )
        print("Result:", result)
    except Exception as e:
        print("Error during LLM completion:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm())
