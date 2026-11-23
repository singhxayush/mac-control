"""
Vision Fallback Connector (Lazy Snapshot & VLM Coordinate Resolver).
"""

import os
import json
import base64
import urllib.request
import subprocess
from typing import Optional, Dict, Any
from connectors.base import BaseConnector

CAPTURE_PATH = "/tmp/mac_control_vision.png"

VISION_PROMPT = """Analyze the macOS screenshot and locate the exact center pixel coordinates of the requested target element.
Return ONLY a JSON object: {"found": true|false, "x": <int>, "y": <int>, "label": "<str>", "confidence": <float>}."""

class VisionConnector(BaseConnector):
    def __init__(self, openrouter_api_key: str = ""):
        super().__init__(name="vision_fallback")
        self.openrouter_api_key = openrouter_api_key

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def health_check(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "connected": self._connected,
            "screencapture_available": os.path.exists("/usr/sbin/screencapture"),
            "has_openrouter_key": bool(self.openrouter_api_key)
        }

    def capture_screen(self, path: str = CAPTURE_PATH) -> bool:
        try:
            res = subprocess.run(["screencapture", "-x", "-C", path], capture_output=True, timeout=3)
            return res.returncode == 0 and os.path.exists(path)
        except Exception:
            return False

    def locate_and_click(self, target_description: str, model: str = "google/gemini-2.0-flash-exp:free") -> Optional[tuple]:
        if not self.openrouter_api_key or not self.capture_screen():
            return None

        try:
            with open(CAPTURE_PATH, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{VISION_PROMPT}\nTarget: '{target_description}'"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                        ]
                    }
                ],
                "response_format": {"type": "json_object"}
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=data,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.openrouter_api_key}"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                content = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                if parsed.get("found"):
                    x, y = parsed["x"], parsed["y"]
                    self.click_coordinates(x, y)
                    return (x, y)
        except Exception as e:
            print(f"[VisionConnector] Fallback error: {e}")

        return None

    def click_coordinates(self, x: int, y: int) -> bool:
        cmd = ["npx", "-y", "@steipete/peekaboo", "click", "--at", f"{x},{y}", "--global"]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False
