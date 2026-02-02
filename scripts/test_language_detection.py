"""
Language Detection and Prompt Adaptation

Tests whether LLMs respond in the user's language automatically,
and implements a language-aware prompt builder if needed.
"""

import asyncio
import httpx
from typing import Optional


async def test_language_response(prompt: str, user_message: str, language: str) -> str:
    """Test if Ollama responds in the correct language without explicit instruction."""
    payload = {
        "model": "llama3.1:8b",
        "prompt": f"{prompt}\n\nUser: {user_message}\n\nAssistant:",
        "stream": False
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("http://localhost:11434/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
    except Exception as e:
        return f"Error: {e}"


async def run_language_tests():
    """Test different language scenarios."""
    
    system_prompt = "You are a spiritual coach specializing in A Course in Miracles. Respond with wisdom, compassion, and practical spiritual guidance."
    
    print("=" * 80)
    print("LANGUAGE RESPONSE TESTING")
    print("=" * 80)
    
    # Test 1: Norwegian input, English system prompt
    print("\n[Test 1] Norwegian input with English system prompt")
    print("-" * 80)
    norwegian_msg = "Hei, jeg heter Johannes. Kan du hjelpe meg med å lære mer om spiritualitet?"
    response = await test_language_response(system_prompt, norwegian_msg, "Norwegian")
    print(f"User (Norwegian): {norwegian_msg}")
    print(f"Assistant response: {response[:200]}...")
    
    # Test 2: English input
    print("\n[Test 2] English input with English system prompt")
    print("-" * 80)
    english_msg = "Hi, my name is John. Can you help me learn about spirituality?"
    response = await test_language_response(system_prompt, english_msg, "English")
    print(f"User (English): {english_msg}")
    print(f"Assistant response: {response[:200]}...")
    
    # Test 3: Norwegian with language hint in system prompt
    print("\n[Test 3] Norwegian input with language-aware system prompt")
    print("-" * 80)
    enhanced_prompt = system_prompt + "\n\nIMPORTANT: Always respond in the same language as the user."
    response = await test_language_response(enhanced_prompt, norwegian_msg, "Norwegian")
    print(f"User (Norwegian): {norwegian_msg}")
    print(f"Assistant response: {response[:200]}...")
    
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print("Check if the Norwegian responses are in Norwegian or English.")
    print("If already in Norwegian in Test 1, no modification needed.")
    print("If Test 3 is better, we should add the language instruction.")


if __name__ == "__main__":
    print("\nTesting language response behavior...")
    print("Make sure Ollama is running with llama3.1:8b loaded.\n")
    asyncio.run(run_language_tests())
