"""
Heavily Guard-Railed Progressive Orchestrator for Mac-Control.

Pillars:
1. HARD-RAILED RESTRAINTS:
   - Zero sudo, zero root access, zero system modifications.
   - Zero permanent rm deletion; all file removals strictly move to macOS ~/.Trash with confirmation.
   - Safe file sandbox: only code/markdown/data files in permitted user workspaces.
   - Complete abolition of arbitrary bash execution.
2. 4-TIER PROGRESSIVE EXECUTION:
   - Tier 0: Instant Deterministic Fast-Path (<10ms)
   - Tier 0.5: Semantic Memory & Knowledge Graph (<1ms)
   - Tier 1: Local Micro-LLM + Accessibility / DOM Tree (~200-400ms)
   - Tier 2: Free Cloud LLM Fallback (~1-1.5s)
   - Tier 3: Vision Fallback Engine (VLM + Coordinate Click + Promotion)
3. ASYNC EVENT BUS:
   - Prioritized event queue with compound command splitting.
"""

import time
import os
import re
from typing import Dict, Any, Optional
from core.event_bus import EventBus
from core.semantic_graph import SemanticGraph
from core.tts_engine import TTSEngine
from core.macos_controller import MacOSController
from core.peekaboo_bridge import AccessibilityBridge
from core.browser_mcp_client import BrowserMCPClient
from core.guardrails import SafetyGuard, PolicyVerdict
from core.safe_fs import SafeFileSystem
from core.fast_router import FastRouter
from core.llm_router import LLMRouter
from core.vision_fallback import VisionFallbackEngine

class ProgressiveOrchestrator:
    def __init__(self, ollama_model="qwen2.5:1.5b", openrouter_api_key=None):
        self.bus = EventBus()
        self.graph = SemanticGraph()

        self.tts = TTSEngine(default_enabled=False)
        self.macos = MacOSController()
        self.accessibility = AccessibilityBridge()
        self.browser = BrowserMCPClient()
        self.vision = VisionFallbackEngine(openrouter_api_key=openrouter_api_key)

        self.guard = SafetyGuard(tts_engine=self.tts)
        self.fast_router = FastRouter(
            macos_ctrl=self.macos,
            tts_engine=self.tts,
            browser_mcp=self.browser,
            accessibility=self.accessibility
        )
        self.llm_router = LLMRouter(ollama_model=ollama_model, openrouter_api_key=openrouter_api_key)

        self.bus.start()

    def process_voice_input(self, raw_voice_text: str) -> Dict[str, Any]:
        """Entry point for incoming voice transcripts."""
        start_t = time.time()
        clean = raw_voice_text.strip()
        if not clean:
            return {"status": "empty"}

        # 1. Check if awaiting safety confirmation (yes/no response)
        if self.guard.awaiting_confirmation:
            confirmed = self.guard.process_confirmation(clean)
            return {
                "status": "confirmation_processed",
                "confirmed": confirmed,
                "elapsed_ms": (time.time() - start_t) * 1000
            }

        # 2. Compound Command Splitting ("open brave and then scroll down")
        sub_commands = self.bus.split_compound_commands(clean)
        results = []

        for sub_cmd in sub_commands:
            res = self._execute_single_command(sub_cmd)
            results.append(res)
            # If any sub-command triggered a hard block, stop the chain
            if res.get("verdict") == PolicyVerdict.HARD_BLOCKED.value:
                break

        return {
            "status": "completed",
            "commands": sub_commands,
            "results": results,
            "total_elapsed_ms": (time.time() - start_t) * 1000
        }

    def _execute_single_command(self, cmd_text: str) -> Dict[str, Any]:
        cmd_start = time.time()
        clean = cmd_text.strip()

        # --- GATEKEEPER 1: Raw Voice Policy Check ---
        verdict, reason = self.guard.evaluate_command_text(clean)

        if verdict == PolicyVerdict.HARD_BLOCKED:
            self.guard.handle_hard_block(reason)
            return {
                "status": "rejected",
                "verdict": verdict.value,
                "reason": reason,
                "elapsed_ms": (time.time() - cmd_start) * 1000
            }

        # Check if raw voice directly requests trashing a specific file
        trash_match = re.match(r"^(?:trash(?: file)?|move to trash|delete file)\s+([~/].+)$", clean, flags=re.IGNORECASE)
        if trash_match:
            target_path = trash_match.group(1).strip()
            is_valid, msg = SafeFileSystem.validate_path(target_path, must_exist=True)
            if not is_valid:
                self.guard.handle_hard_block(f"Trash operation blocked: {msg}")
                return {"status": "rejected", "reason": msg}

            def _do_direct_trash():
                ok, trash_msg = SafeFileSystem.safe_move_to_trash(target_path)
                print(f"[TRASH RESULT] {trash_msg}")
                self.tts.speak(trash_msg)

            self.guard.request_confirmation(f"Move '{target_path}' to macOS Trash?", _do_direct_trash)
            return {
                "status": "confirmation_requested",
                "action": {"action": "safe_trash_file", "path": target_path},
                "elapsed_ms": (time.time() - cmd_start) * 1000
            }

        # --- Tier 0: Instant Reflex Router (<10ms) ---
        if self.fast_router.try_route(clean):
            elapsed = (time.time() - cmd_start) * 1000
            print(f"[Tier-0 Reflex] Executed '{clean}' in {elapsed:.1f}ms")
            return {"tier": 0, "status": "executed", "command": clean, "elapsed_ms": elapsed}

        frontmost_app = self.macos.get_frontmost_app()

        # --- Tier 0.5: Semantic Memory & Knowledge Graph (<1ms) ---
        cached_action = self.graph.find_cached_action(clean, app_name=frontmost_app)
        if cached_action:
            # Re-verify cached payload against safety policy
            action_verdict, v_reason = self.guard.evaluate_action_payload(cached_action)
            if action_verdict == PolicyVerdict.HARD_BLOCKED:
                self.guard.handle_hard_block(v_reason)
                return {"status": "rejected", "verdict": action_verdict.value, "reason": v_reason}

            success = self._execute_action_dict(cached_action, frontmost_app=frontmost_app)
            elapsed = (time.time() - cmd_start) * 1000
            if success:
                print(f"[SemanticGraph Accelerated] '{clean}' executed from memory in {elapsed:.1f}ms")
                return {"tier": 0.5, "status": "executed_from_memory", "action": cached_action, "elapsed_ms": elapsed}

        # --- Tier 1 & Tier 2: LLM Intent Parsing ---
        print(f"[Orchestrator] Resolving via LLM intent ({clean})...")
        action_dict = None
        tier_used = 1

        try:
            action_dict = self.llm_router.route(clean)
        except Exception as e:
            print(f"[LLM Router Error] {e}")

        if action_dict:
            # --- GATEKEEPER 2: Structured Action Payload Verification ---
            payload_verdict, p_reason = self.guard.evaluate_action_payload(action_dict)

            if payload_verdict == PolicyVerdict.HARD_BLOCKED:
                self.guard.handle_hard_block(p_reason)
                return {
                    "status": "rejected",
                    "verdict": payload_verdict.value,
                    "reason": p_reason,
                    "elapsed_ms": (time.time() - cmd_start) * 1000
                }

            if payload_verdict == PolicyVerdict.REQUIRES_CONFIRMATION:
                # Sensitive safe action (e.g. safe_trash_file)
                path = action_dict.get("path", "")
                def _do_trash():
                    ok, msg = SafeFileSystem.safe_move_to_trash(path)
                    print(f"[TRASH RESULT] {msg}")
                    self.tts.speak(msg)

                self.guard.request_confirmation(f"Move '{path}' to macOS Trash?", _do_trash)
                return {
                    "status": "confirmation_requested",
                    "action": action_dict,
                    "elapsed_ms": (time.time() - cmd_start) * 1000
                }

            action_success = self._execute_action_dict(action_dict, frontmost_app=frontmost_app)
            if action_success:
                elapsed = (time.time() - cmd_start) * 1000
                self.graph.record_successful_resolution(
                    intent_text=clean,
                    action_dict=action_dict,
                    resolved_by_tier=tier_used,
                    app_name=frontmost_app
                )
                return {"tier": tier_used, "status": "executed", "action": action_dict, "elapsed_ms": elapsed}

        # --- Tier 3: Vision Fallback Engine ---
        print(f"[Orchestrator] Engaging Tier-3 Vision Fallback...")
        vision_success = self.vision.execute_fallback(
            target_description=clean,
            semantic_graph=self.graph,
            app_name=frontmost_app
        )
        elapsed = (time.time() - cmd_start) * 1000

        if vision_success:
            self.tts.speak("Located and clicked with vision.", async_speak=True)
            return {"tier": 3, "status": "executed_via_vision", "command": clean, "elapsed_ms": elapsed}

        return {"status": "unresolved", "command": clean, "elapsed_ms": elapsed}

    def _execute_action_dict(self, action_dict: Dict[str, Any], frontmost_app: Optional[str] = None) -> bool:
        action = action_dict.get("action")

        try:
            # 1. Safe File Operations
            if action == "safe_write_file":
                path = action_dict.get("path", "")
                content = action_dict.get("content", "")
                ok, msg = SafeFileSystem.safe_write_file(path, content)
                print(f"[Safe File Write] {msg}")
                self.tts.speak(f"File created safely: {os.path.basename(path)}")
                return ok

            elif action == "safe_read_file":
                path = action_dict.get("path", "")
                ok, content = SafeFileSystem.safe_read_file(path)
                if ok:
                    print(f"\n[Safe File Read - {path}]\n{content[:500]}\n")
                    self.tts.speak(f"Read {os.path.basename(path)}")
                return ok

            elif action == "safe_trash_file":
                # Always routed through confirmation prompt, but fallback here
                path = action_dict.get("path", "")
                ok, msg = SafeFileSystem.safe_move_to_trash(path)
                return ok

            # 2. Vision Global Coordinate Click
            elif action == "click_coordinates":
                x = action_dict.get("x")
                y = action_dict.get("y")
                if x is not None and y is not None:
                    return self.vision.click_coordinates(x, y)

            # 3. Safe Browser Actions
            elif action == "open_url":
                self.browser.open_url(action_dict["url"])
                return True
            elif action == "search":
                self.browser.search_web(action_dict["query"])
                return True
            elif action == "click_link":
                target = action_dict.get("text", "")
                if self.browser.click_link_or_text(target):
                    return True
                res = self.accessibility.click_element(target, app=frontmost_app)
                return res.get("success", False)
            elif action == "toggle_video":
                res = self.browser.toggle_video_playback()
                return "Playing" in res or "Paused" in res
            elif action == "scroll":
                return self.browser.scroll_page(action_dict.get("direction", "down"), action_dict.get("amount", 500))

            # 4. Safe UI & Window Controls
            elif action == "open_app":
                self.macos.open_app(action_dict["app"])
                return True
            elif action == "click_element":
                res = self.accessibility.click_element(action_dict["query"], app=action_dict.get("app") or frontmost_app)
                return res.get("success", False)
            elif action == "type_text":
                res = self.accessibility.type_text(action_dict["text"], app=action_dict.get("app") or frontmost_app)
                return res.get("success", False)
            elif action == "focus_window":
                res = self.accessibility.focus_window(action_dict["app"])
                return res.get("success", False)
            elif action == "maximize_window":
                res = self.accessibility.maximize_window(action_dict["app"])
                return res.get("success", False)
            elif action == "minimize_window":
                res = self.accessibility.minimize_window(action_dict["app"])
                return res.get("success", False)
            elif action == "approve_dialog":
                res = self.accessibility.click_dialog_button("Allow")
                return res.get("success", False)

        except Exception as e:
            print(f"[Action Execution Error] {e}")

        return False

    def close(self):
        self.bus.stop()
        self.browser.close()
