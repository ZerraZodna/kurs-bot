"""Local LLM model that directly connects to the local LLM API."""

import json
import logging
import os
from typing import Any

logger = logging.getLogger("local_model")


class LocalModel:
    """Local LLM model that connects directly to the local LLM API."""
    
    def __init__(self, *, model_name: str = "Qwen3.5-9B-UD-Q4_K_XL", base_url: str = "http://192.168.64.1:8080/v1"):
        self.model_name = model_name
        self.base_url = base_url
        self.cost = 0.0
        self.n_calls = 0
        self._client = None
    
    def _get_client(self):
        """Get or create the HTTP client."""
        if self._client is None:
            import httpx
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=60.0,
            )
        return self._client
    
    def query(self, messages: list[dict[str, str]]) -> dict:
        """Query the local LLM and return the response."""
        try:
            import httpx
            client = self._get_client()
            
            # Format messages for the local API
            formatted_messages = [
                {"role": msg["role"], "content": msg["content"]} for msg in messages
            ]
            
            # Call the local LLM API
            response = client.post(
                "/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": formatted_messages,
                    "stream": False,
                },
            )
            response.raise_for_status()
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            self.n_calls += 1
            # Local models are free
            self.cost += 0.0
            
            return {
                "content": content or "",
                "extra": {"response": result},
            }
        except Exception as e:
            logger.error(f"Failed to query local LLM: {e}")
            raise RuntimeError(f"Local LLM query failed: {e}")
    
    def get_template_vars(self) -> dict[str, Any]:
        """Return template variables."""
        return {
            "n_model_calls": self.n_calls,
            "model_cost": self.cost,
        }
