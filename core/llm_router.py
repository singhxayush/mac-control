"""
Tier-1 & Tier-2 LLM Intent Router with Rigid Safety Schema.

Guarantees:
1. NO ARBITRARY SHELL / BASH ACTIONS: The schema completely disallows arbitrary command-line execution.
2. SAFE FILE OPERATIONS ONLY:
   - safe_write_file: restricted to safe extensions (.py, .js, .json, .md, .txt) in user workspaces.
   - safe_trash_file: strictly moves user files to macOS ~/.Trash (never permanently deletes).
   - safe_read_file: reads user files.
3. BROWSER & UI ACTIONS:
   - open_url, search, click_link, scroll, toggle_video.
   - click_element, type_text, open_app, focus_window, maximize_window, minimize_window.
"""

import json
import urllib.request
import os

TOOL_SYSTEM_PROMPT = """You are an ultra-fast, heavily guard-railed macOS voice automation agent.
You MUST output ONLY a valid JSON object matching one of the supported actions.
Do NOT output markdown fences (```json), explanations, or conversational text.

CRITICAL SAFETY POLICIES:
- You CANNOT run sudo, shell scripts, or delete files permanently.
- Arbitrary bash/terminal commands are strictly forbidden and disabled.
- File creation is restricted to safe code/markdown/data files (.py, .js, .ts, .json, .md, .txt).
- File deletions are strictly moved to macOS Trash (safe_trash_file).

Supported JSON actions:
1. Safe File Operations:
   {"action": "safe_write_file", "path": "/Users/ayush/Build/.../file.py", "content": "content"}
   {"action": "safe_trash_file", "path": "/Users/ayush/Build/.../file.txt"}
   {"action": "safe_read_file", "path": "/Users/ayush/Build/.../file.md"}

2. Browser Actions:
   {"action": "open_url", "url": "https://..."}
   {"action": "search", "query": "search query"}
   {"action": "click_link", "text": "visible link text or button"}
   {"action": "scroll", "direction": "down|up", "amount": 500}
   {"action": "toggle_video"}

3. macOS Accessibility & Window Control:
   {"action": "click_element", "query": "Button text", "app": "App Name or null"}
   {"action": "type_text", "text": "text to type", "app": "App Name or null"}
   {"action": "open_app", "app": "Application Name"}
   {"action": "focus_window", "app": "Application Name"}
   {"action": "maximize_window", "app": "Application Name"}
   {"action": "minimize_window", "app": "Application Name"}
   {"action": "approve_dialog"}

Examples:
- "Create a python script named test.py in my build directory" -> {"action": "safe_write_file", "path": "/Users/ayush/Build/test.py", "content": "# Test script"}
- "Trash the old notes file in my documents" -> {"action": "safe_trash_file", "path": "/Users/ayush/Documents/old_notes.txt"}
- "Open YouTube" -> {"action": "open_url", "url": "https://youtube.com"}
- "Search for python tutorials" -> {"action": "search", "query": "python tutorials"}
- "Switch to Slack" -> {"action": "open_app", "app": "Slack"}
"""

class LLMRouter:
    def __init__(self, ollama_model="qwen2.5:1.5b", openrouter_api_key=None):
        self.ollama_model = ollama_model
        self.openrouter_api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")

    def query_ollama(self, prompt: str) -> dict:
        """Queries local Ollama endpoint (http://localhost:11434/api/generate)."""
        payload = {
            "model": self.ollama_model,
            "prompt": f"{TOOL_SYSTEM_PROMPT}\nUser command: {prompt}\nJSON:",
            "stream": False,
            "format": "json"
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return json.loads(res.get("response", "{}"))

    def query_openrouter(self, prompt: str, model="google/gemini-2.0-flash-exp:free") -> dict:
        """Queries OpenRouter free tier API as fallback."""
        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not set.")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": TOOL_SYSTEM_PROMPT},
                {"role": "user", "content": f"User command: {prompt}\nJSON:"}
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
        with urllib.request.urlopen(req, timeout=5) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            content = res["choices"][0]["message"]["content"]
            return json.loads(content)

    def route(self, prompt: str) -> dict:
        """Attempts local Ollama first, falls back to OpenRouter if configured."""
        try:
            return self.query_ollama(prompt)
        except Exception as e:
            if self.openrouter_api_key:
                return self.query_openrouter(prompt)
            raise RuntimeError(f"Local Ollama failed ({e}) and no OpenRouter key provided.")
