"""
LLM Connector for Intent Routing (Ollama Local + OpenRouter Cloud Fallback).
"""

import json
import urllib.request
from typing import Dict, Any, Optional
from connectors.base import BaseConnector

TOOL_SYSTEM_PROMPT = """You are an intelligent macOS voice assistant named Mac-Control.
You handle both macOS system actions AND conversational/informational questions.
Output ONLY a JSON object. No markdown fences or explanations.

Critical Rules:
- Output valid JSON only.
- Never use sudo or bash shell commands. Never use permanent rm deletions.

JSON Output Schema:
1. When user requests an OS action or control:
   {"type": "action", "action": "open_app", "app": "Notes"}
   {"type": "action", "action": "focus_window", "app": "Finder"}
   {"type": "action", "action": "search", "query": "python guides"}
   {"type": "action", "action": "scroll", "direction": "down", "amount": 500}
   {"type": "action", "action": "toggle_video"}
   {"type": "action", "action": "safe_write_file", "path": "/tmp/mac-control/test.txt", "content": "hello"}
   {"type": "action", "action": "safe_read_file", "path": "/tmp/mac-control/test.txt"}
   {"type": "action", "action": "safe_trash_file", "path": "/tmp/mac-control/test.txt"}

2. When user asks a question, conversational query, capability question, greeting, or explanation:
   {"type": "chat", "message": "A concise, natural 1-2 sentence spoken answer."}
"""

class LLMConnector(BaseConnector):
    def __init__(
        self,
        ollama_endpoint: str = "http://127.0.0.1:11434",
        ollama_model: str = "qwen2.5:0.5b",
        openrouter_api_key: str = "",
        openrouter_model: str = "nvidia/llama-3.1-nemotron-70b-instruct:free",
        openrouter_free_only: bool = True
    ):
        super().__init__(name="llm_router")
        self.ollama_endpoint = ollama_endpoint
        self.ollama_model = ollama_model
        self.openrouter_api_key = openrouter_api_key
        self.openrouter_model = openrouter_model
        self.openrouter_free_only = openrouter_free_only

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def health_check(self) -> Dict[str, Any]:
        ollama_alive = False
        try:
            req = urllib.request.Request(f"{self.ollama_endpoint}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                ollama_alive = resp.status == 200
        except Exception:
            pass
        return {
            "name": self.name,
            "connected": self._connected,
            "ollama_alive": ollama_alive,
            "has_openrouter_key": bool(self.openrouter_api_key),
            "openrouter_model": self.openrouter_model,
            "free_only_enforced": self.openrouter_free_only
        }

    def route_intent(self, text: str) -> Optional[Dict[str, Any]]:
        # 1. Try local Ollama
        try:
            payload = {
                "model": self.ollama_model,
                "prompt": f"{TOOL_SYSTEM_PROMPT}\nUser command: {text}\nJSON:",
                "stream": False,
                "format": "json"
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(f"{self.ollama_endpoint}/api/generate", data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return json.loads(res.get("response", "{}"))
        except Exception:
            # 2. Fallback to OpenRouter free tier
            if self.openrouter_api_key:
                return self._query_openrouter(text)
        return None

    def _query_openrouter(self, text: str) -> Optional[Dict[str, Any]]:
        # HARD CREDIT PROTECTION CHECK
        if self.openrouter_free_only and not self.openrouter_model.endswith(":free"):
            print(f"[LLMConnector Security] Rejected paid model '{self.openrouter_model}'. Only ':free' models allowed.")
            return None

        payload = {
            "model": self.openrouter_model,
            "messages": [
                {"role": "system", "content": TOOL_SYSTEM_PROMPT},
                {"role": "user", "content": f"User command: {text}\nJSON:"}
            ],
            "response_format": {"type": "json_object"}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openrouter_api_key}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                content = res["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception as e:
            print(f"[LLMConnector] OpenRouter fallback error: {e}")
            return None
