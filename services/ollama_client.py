import json
import logging
from typing import Generator, List, Dict, Any, Optional
import requests
from config import config

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for interacting with Ollama Cloud / Remote API."""

    def __init__(
        self,
        host: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.host = (host or config.OLLAMA_HOST).rstrip("/")
        self.api_key = api_key or config.OLLAMA_API_KEY
        self.model = model or config.OLLAMA_MODEL

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def stream_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> Generator[str, None, None]:
        """Stream chat completions chunk by chunk from Ollama API."""
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
            "options": {
                "temperature": temperature,
            },
        }

        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                stream=True,
                timeout=60,
            )
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    message = chunk.get("message", {})
                    content = message.get("content", "")
                    if content:
                        yield content
                    if chunk.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama request error: {e}")
            yield f"\n\n*[Error generating response from Ollama: {str(e)}]*"

    def complete_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        """Non-streaming chat completion from Ollama API."""
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        response = requests.post(
            url,
            headers=self._get_headers(),
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")

    def check_health(self) -> Dict[str, Any]:
        """Check connection to Ollama host."""
        try:
            url = f"{self.host}/api/tags"
            resp = requests.get(url, headers=self._get_headers(), timeout=5)
            if resp.ok:
                models = [m.get("name") for m in resp.json().get("models", [])]
                return {
                    "status": "connected",
                    "host": self.host,
                    "target_model": self.model,
                    "available_models": models,
                }
            return {
                "status": "unhealthy",
                "host": self.host,
                "status_code": resp.status_code,
                "error": resp.text,
            }
        except Exception as e:
            return {
                "status": "unreachable",
                "host": self.host,
                "error": str(e),
            }
