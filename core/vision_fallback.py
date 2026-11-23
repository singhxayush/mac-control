"""
Tier-3 Vision Fallback Engine.

Used as a progressive fallback when Tier 0 (reflex), Tier 1 (DOM/AX),
and Semantic Graph memory cannot locate a targeted element.

Workflow:
1. Captures a fast screenshot via macOS `screencapture` or Peekaboo (50ms).
2. Sends the image to a Vision-Language Model (OpenRouter free tier or local Ollama vision).
3. Extracts bounding coordinates (x, y).
4. Executes the click using Peekaboo (`peekaboo click --at x,y --global`).
5. Feeds the coordinates back into the `SemanticGraph` so subsequent requests
   become instantaneous (<10ms) Tier-0/1 actions.
"""

import os
import json
import base64
import urllib.request
import subprocess
from typing import Optional, Dict, Any, Tuple

CAPTURE_PATH = "/tmp/mac_control_vision.png"

VISION_SYSTEM_PROMPT = """You are an expert macOS GUI vision locator.
Analyze the provided screenshot and find the exact element described in the user request.
Return ONLY a JSON object with:
{
  "found": true | false,
  "x": <integer logical x pixel coordinate of the center of the element>,
  "y": <integer logical y pixel coordinate of the center of the element>,
  "label": "<brief element label>",
  "confidence": <float between 0.0 and 1.0>
}
Do NOT include markdown formatting, code fences, or explanations.
"""

class VisionFallbackEngine:
    def __init__(self, openrouter_api_key: Optional[str] = None):
        self.openrouter_api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")

    def capture_screen(self, path: str = CAPTURE_PATH) -> bool:
        """Captures screen in ~50ms using macOS native screencapture."""
        try:
            res = subprocess.run(["screencapture", "-x", "-C", path], capture_output=True, timeout=3)
            return res.returncode == 0 and os.path.exists(path)
        except Exception as e:
            print(f"[VisionFallback] Screencapture error: {e}")
            return False

    def locate_element_with_vision(
        self,
        target_description: str,
        image_path: str = CAPTURE_PATH,
        model: str = "google/gemini-2.0-flash-exp:free"
    ) -> Optional[Dict[str, Any]]:
        """Queries Vision LLM with screenshot base64."""
        if not self.openrouter_api_key:
            print("[VisionFallback] No OPENROUTER_API_KEY configured for Vision Fallback.")
            return None

        try:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{VISION_SYSTEM_PROMPT}\nTarget element: '{target_description}'"},
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
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.openrouter_api_key}"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                content = res["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                if parsed.get("found"):
                    return parsed
        except Exception as e:
            print(f"[VisionFallback] Vision inference error: {e}")

        return None

    def click_coordinates(self, x: int, y: int) -> bool:
        """Clicks global coordinates using Peekaboo."""
        cmd = ["npx", "-y", "@steipete/peekaboo", "click", "--at", f"{x},{y}", "--global"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return res.returncode == 0
        except Exception as e:
            print(f"[VisionFallback] Click execution error: {e}")
            return False

    def execute_fallback(
        self,
        target_description: str,
        semantic_graph=None,
        app_name: Optional[str] = None
    ) -> bool:
        """
        Executes full Tier-3 fallback:
        Capture -> Locate -> Click -> Store in Semantic Graph.
        """
        print(f"[VisionFallback] Triggered for: '{target_description}'...")
        if not self.capture_screen():
            return False

        location = self.locate_element_with_vision(target_description)
        if not location:
            print(f"[VisionFallback] Could not locate element '{target_description}'.")
            return False

        x, y = location["x"], location["y"]
        print(f"[VisionFallback] Found element at ({x}, {y}) (confidence={location.get('confidence')}). Clicking...")
        success = self.click_coordinates(x, y)

        if success and semantic_graph:
            # Promote this to Semantic Graph for subsequent instant Tier 0/1 execution!
            action_payload = {
                "action": "click_coordinates",
                "x": x,
                "y": y,
                "label": location.get("label", target_description)
            }
            semantic_graph.record_successful_resolution(
                intent_text=target_description,
                action_dict=action_payload,
                resolved_by_tier=3,
                app_name=app_name,
                coordinates=(x, y)
            )

        return success
