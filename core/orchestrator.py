"""
Unified Voice OS Orchestrator.
Coordinates State Machine, Event Bus, Safety Gatekeeper, Connectors, and Memory Graph.
"""

import os
import time
import re
from typing import Dict, Any, Optional, List

from config.settings import settings
from events.bus import EventBus
from events.voice_events import RawVoiceInputEvent, CompoundCommandEvent
from events.lifecycle_events import WakeWordDetectedEvent, SleepRequestedEvent
from events.action_events import ActionRequestedEvent, ActionExecutedEvent
from events.safety_events import SafetyViolationEvent

from core.state_machine import LifecycleManager, AgentState
from safety.guardrail import SafetyGatekeeper, PolicyVerdict, SafeFileSystem
from memory.semantic_graph import SemanticGraph
from telemetry.logger import TelemetryLogger
from telemetry.models import TelemetryTrace, CostMetrics, TraceSpan
from telemetry.logging_config import get_logger, get_security_logger, current_trace_id

log = get_logger("orchestrator")
sec_log = get_security_logger()

from connectors.macos_connector import MacOSConnector
from connectors.browser_connector import BrowserConnector
from connectors.llm_connector import LLMConnector
from connectors.vision_connector import VisionConnector
from connectors.tts_connector import TTSConnector

class VoiceOSOrchestrator:
    def __init__(self):
        # 1. Event Bus
        self.bus = EventBus()

        # 2. Lifecycle & State Machine
        self.lifecycle = LifecycleManager(idle_timeout=settings.lifecycle.idle_timeout_seconds)

        # 3. Connectors
        self.macos = MacOSConnector()
        self.browser = BrowserConnector(cdp_port=settings.connectors.cdp_port)
        self.llm = LLMConnector(
            ollama_endpoint=settings.connectors.ollama_endpoint,
            ollama_model=settings.connectors.ollama_model,
            openrouter_api_key=settings.connectors.openrouter_api_key,
            openrouter_model=settings.connectors.openrouter_model
        )
        self.vision = VisionConnector(openrouter_api_key=settings.connectors.openrouter_api_key)
        self.tts = TTSConnector(
            voice=settings.audio.kokoro_voice,
            initial_enabled=settings.audio.voice_feedback_enabled,
            speed=settings.audio.speed
        )

        # 4. Safety, Memory & Telemetry
        self.guard = SafetyGatekeeper(tts_connector=self.tts)
        self.graph = SemanticGraph(storage_path=settings.connectors.graph_storage_path)
        self.telemetry = TelemetryLogger.get_instance()

        # Canonical application aliases
        self.app_aliases = {
            "note": "Notes",
            "notes": "Notes",
            "chrome": "Google Chrome",
            "google chrome": "Google Chrome",
            "safari": "Safari",
            "terminal": "Terminal",
            "code": "Visual Studio Code",
            "vscode": "Visual Studio Code",
            "finder": "Finder",
            "music": "Music",
            "spotify": "Spotify",
            "slack": "Slack",
            "calculator": "Calculator",
            "settings": "System Settings",
            "preferences": "System Settings",
            "calendar": "Calendar",
            "mail": "Mail",
            "messages": "Messages"
        }

        # 5. Connect core connectors
        self.macos.connect()
        self.llm.connect()
        self.bus.start()

    def process_voice_input(self, raw_text: str) -> Dict[str, Any]:
        """Main processing pipeline for voice transcripts with telemetry logging."""
        t0 = time.time()
        clean = raw_text.strip()
        if not clean:
            return {"status": "empty"}

        state_before = self.lifecycle.current_state.value
        self.bus.publish(RawVoiceInputEvent(raw_text=clean))

        # --- PHASE 1: Safety Confirmation State Check ---
        if self.guard.awaiting_confirmation:
            confirmed = self.guard.process_confirmation(clean)
            elapsed = (time.time() - t0) * 1000
            res = {
                "status": "confirmation_processed",
                "confirmed": confirmed,
                "elapsed_ms": elapsed
            }
            self.telemetry.log_trace(TelemetryTrace(
                raw_input=clean,
                normalized_input=clean,
                agent_state_before=state_before,
                agent_state_after=self.lifecycle.current_state.value,
                tier_name="ConfirmationGate",
                status="confirmation_processed",
                spoken_feedback="Confirmed." if confirmed else "Cancelled.",
                latency_ms={"total": elapsed}
            ))
            return res

        # --- PHASE 2: State Machine & Wake-Word Activation ---
        is_awake, remainder = self.lifecycle.parse_activation(clean)

        if not is_awake:
            # System is sleeping and no wake word detected. Disconnect heavy connectors if needed.
            if self.browser.is_connected:
                self.browser.disconnect()
            elapsed = (time.time() - t0) * 1000
            self.telemetry.log_trace(TelemetryTrace(
                raw_input=clean,
                normalized_input=clean,
                agent_state_before=state_before,
                agent_state_after="sleeping",
                tier_name="Standby",
                status="sleeping",
                latency_ms={"total": elapsed}
            ))
            return {
                "status": "sleeping",
                "state": self.lifecycle.current_state.value,
                "message": "Standby mode. Say 'Hey Mac' or 'Wake up' to activate."
            }

        # If woke up with no additional command (e.g., just "Hey Mac", "Turn on", "Wake up")
        if not remainder or remainder.lower() in [w.lower() for w in self.lifecycle.wake_words]:
            spoken = None
            if self.tts.voice_feedback_enabled:
                spoken = "Yes? I am listening."
                self.tts.speak(spoken)
            elapsed = (time.time() - t0) * 1000
            self.telemetry.log_trace(TelemetryTrace(
                raw_input=clean,
                normalized_input=remainder,
                agent_state_before=state_before,
                agent_state_after="awake_active",
                wake_word_detected=True,
                tier_name="WakeWordActivation",
                status="awake_ready",
                spoken_feedback=spoken,
                latency_ms={"total": elapsed}
            ))
            return {
                "status": "awake_ready",
                "state": self.lifecycle.current_state.value,
                "message": "Awake and listening for commands."
            }

        # --- PHASE 3: Compound Command Chaining ---
        sub_commands = self.bus.split_compound_commands(remainder)
        self.bus.publish(CompoundCommandEvent(original_text=remainder, sub_commands=sub_commands))
        results = []

        is_conversational = (state_before == "awake_active")

        for sub_cmd in sub_commands:
            trace = TelemetryTrace(
                raw_input=clean,
                normalized_input=sub_cmd,
                agent_state_before=state_before,
                agent_state_after=self.lifecycle.current_state.value,
                wake_word_detected=(not is_conversational),
                conversational_followup=is_conversational
            )
            current_trace_id.set(trace.trace_id)

            res = self._execute_command(sub_cmd, trace=trace)
            results.append(res)

            trace.agent_state_after = self.lifecycle.current_state.value
            trace.intent_tier = res.get("tier")
            trace.tier_name = res.get("tier_name", "unknown")
            trace.action_name = res.get("action_name")
            trace.action_payload = res.get("action")
            trace.safety_verdict = res.get("verdict", "allowed")
            trace.status = res.get("status", "unknown")
            trace.spoken_feedback = res.get("spoken")
            trace.latency_ms = {"total": res.get("elapsed_ms", 0.0)}
            trace.error = res.get("error")

            # Finalize and record trace
            self.telemetry.log_trace(trace)

            # If a sub-command hit a hard security block, abort the remainder of the chain
            if res.get("verdict") == PolicyVerdict.HARD_BLOCKED.value:
                break

        return {
            "status": "completed",
            "state": self.lifecycle.current_state.value,
            "commands": sub_commands,
            "results": results,
            "total_elapsed_ms": (time.time() - t0) * 1000
        }

    def _speak_action_confirmation(self, action_dict: Dict[str, Any]) -> Optional[str]:
        if not self.tts.voice_feedback_enabled:
            return None
        act = action_dict.get("action", "")
        msg = None
        if act == "open_app":
            msg = f"Opening {action_dict.get('app', '')}."
        elif act == "focus_window":
            msg = f"Switched to {action_dict.get('app', '')}."
        elif act == "search":
            msg = f"Searching for {action_dict.get('query', '')}."
        elif act == "safe_write_file":
            msg = "File saved."
        elif act == "safe_read_file":
            msg = "Read file."

        if msg:
            self.tts.speak(msg)
        return msg

    def _execute_command(self, cmd_text: str, trace: Optional[TelemetryTrace] = None) -> Dict[str, Any]:
        t_start = time.time()
        clean = cmd_text.strip()

        # 1. Gatekeeper: Raw Text Policy Check
        span_sec = trace.start_span("safety_gatekeeper_text") if trace else None
        verdict, reason = self.guard.evaluate_text(clean)
        if span_sec and trace:
            trace.record_span(span_sec.finish(status=verdict.value, extra_metadata={"verdict": verdict.value, "reason": reason}))

        if verdict == PolicyVerdict.HARD_BLOCKED:
            self.bus.publish(SafetyViolationEvent(blocked_command=clean, reason=reason, rule="HARD_BLOCK"))
            print(f"[SAFETY VIOLATION BLOCKED] {reason}")
            if self.tts.voice_feedback_enabled:
                self.tts.speak("Action blocked by safety policy.")
            return {
                "tier": -1,
                "tier_name": "HardSecurityBlock",
                "status": "rejected",
                "verdict": verdict.value,
                "reason": reason,
                "elapsed_ms": (time.time() - t_start) * 1000
            }

        # Check for direct file trash command: "trash file <path>"
        trash_match = re.match(r"^(?:trash(?: file)?|move to trash|delete file)\s+([~/].+)$", clean, flags=re.IGNORECASE)
        if trash_match:
            target_path = trash_match.group(1).strip()
            ok, msg = SafeFileSystem.validate_path(target_path, must_exist=True)
            if not ok:
                return {
                    "tier": -1,
                    "tier_name": "SafetyValidationFailed",
                    "status": "rejected",
                    "reason": msg,
                    "elapsed_ms": (time.time() - t_start) * 1000
                }

            def _do_trash():
                success, t_msg = SafeFileSystem.safe_move_to_trash(target_path)
                print(f"[TRASH COMPLETED] {t_msg}")

            self.guard.request_confirmation(f"Move '{target_path}' to macOS Trash?", _do_trash)
            return {
                "tier": 0,
                "tier_name": "TrashConfirmation",
                "status": "confirmation_requested",
                "target": target_path,
                "elapsed_ms": (time.time() - t_start) * 1000
            }

        # 2. Tier 0: Instant Deterministic Reflex (<10ms)
        span_reflex = trace.start_span("tier0_reflex") if trace else None
        reflex_spoken = self._try_tier0_reflex(clean)
        if reflex_spoken:
            if span_reflex and trace:
                trace.record_span(span_reflex.finish(status="hit", extra_metadata={"command": clean}))
            elapsed = (time.time() - t_start) * 1000
            print(f"[Tier-0 Reflex] '{clean}' executed in {elapsed:.1f}ms")
            return {
                "tier": 0,
                "tier_name": "ReflexTier0",
                "status": "executed",
                "command": clean,
                "spoken": reflex_spoken if isinstance(reflex_spoken, str) else None,
                "elapsed_ms": elapsed
            }
        elif span_reflex and trace:
            trace.record_span(span_reflex.finish(status="miss"))

        frontmost_app = self.macos.get_frontmost_app()

        # 3. Tier 0.5: Semantic Memory Graph Cache (<1ms)
        span_graph = trace.start_span("semantic_graph_cache") if trace else None
        cached_action = self.graph.find_cached_action(clean, app_name=frontmost_app)
        if cached_action:
            if span_graph and trace:
                trace.record_span(span_graph.finish(status="hit", extra_metadata={"action": cached_action}))
            v_verdict, v_reason = self.guard.evaluate_action_payload(cached_action)
            if v_verdict == PolicyVerdict.HARD_BLOCKED:
                return {
                    "tier": 0.5,
                    "tier_name": "SemanticGraphBlocked",
                    "status": "rejected",
                    "verdict": v_verdict.value,
                    "reason": v_reason,
                    "elapsed_ms": (time.time() - t_start) * 1000
                }

            if self._execute_action_payload(cached_action, frontmost_app=frontmost_app):
                elapsed = (time.time() - t_start) * 1000
                print(f"[SemanticGraph] '{clean}' executed from memory in {elapsed:.1f}ms")
                spoken = self._speak_action_confirmation(cached_action)
                return {
                    "tier": 0.5,
                    "tier_name": "SemanticGraph",
                    "status": "executed_from_memory",
                    "action": cached_action,
                    "spoken": spoken,
                    "elapsed_ms": elapsed
                }
        elif span_graph and trace:
            trace.record_span(span_graph.finish(status="miss"))

        # 4. Tier 1 / Tier 2: LLM Intent Parsing
        span_llm = trace.start_span("ollama_llm_routing") if trace else None
        print(f"[Orchestrator] Resolving intent via LLM: '{clean}'...")
        action_dict = self.llm.route_intent(clean)
        if span_llm and trace:
            trace.record_span(span_llm.finish(status="hit" if action_dict else "miss"))

        # Attach Cost Metrics
        if trace:
            cost = CostMetrics()
            cost.calculate_cost(prompt_tokens=max(5, len(clean)//4), completion_tokens=15, model=settings.connectors.ollama_model, provider="local")
            trace.cost = cost.to_dict()

        if action_dict:
            # Check for conversational / chat response
            if action_dict.get("type") == "chat" or ("message" in action_dict and "action" not in action_dict):
                msg = action_dict.get("message", "")
                elapsed = (time.time() - t_start) * 1000
                print(f"[Conversational Response] '{msg}'")
                if self.tts.voice_feedback_enabled:
                    self.tts.speak(msg)
                return {
                    "tier": 1.0,
                    "tier_name": "ConversationalChat",
                    "status": "chat_answered",
                    "message": msg,
                    "spoken": msg if self.tts.voice_feedback_enabled else None,
                    "elapsed_ms": elapsed
                }

            span_p_sec = trace.start_span("safety_gatekeeper_payload") if trace else None
            p_verdict, p_reason = self.guard.evaluate_action_payload(action_dict)
            if span_p_sec and trace:
                trace.record_span(span_p_sec.finish(status=p_verdict.value))

            if p_verdict == PolicyVerdict.HARD_BLOCKED:
                return {
                    "tier": 1.0,
                    "tier_name": "LLMHardBlocked",
                    "status": "rejected",
                    "verdict": p_verdict.value,
                    "reason": p_reason,
                    "elapsed_ms": (time.time() - t_start) * 1000
                }

            if p_verdict == PolicyVerdict.CONFIRMATION_REQUIRED:
                path = action_dict.get("path", "")
                self.guard.request_confirmation(
                    f"Move '{path}' to macOS Trash?",
                    lambda: SafeFileSystem.safe_move_to_trash(path)
                )
                return {
                    "tier": 1.0,
                    "tier_name": "LLMConfirmationRequired",
                    "status": "confirmation_requested",
                    "action": action_dict,
                    "elapsed_ms": (time.time() - t_start) * 1000
                }

            span_exec = trace.start_span("action_execution", metadata={"action": action_dict.get("action")}) if trace else None
            if self._execute_action_payload(action_dict, frontmost_app=frontmost_app):
                if span_exec and trace:
                    trace.record_span(span_exec.finish(status="success"))
                elapsed = (time.time() - t_start) * 1000
                self.graph.record_resolution(clean, action_dict, tier=1.0, app_name=frontmost_app)
                spoken = self._speak_action_confirmation(action_dict)
                return {
                    "tier": 1.0,
                    "tier_name": "OllamaQwenLocal",
                    "status": "executed",
                    "action": action_dict,
                    "spoken": spoken,
                    "elapsed_ms": elapsed
                }
            elif span_exec and trace:
                trace.record_span(span_exec.finish(status="failed"))

        # 5. Tier 3: Vision Fallback Engine
        print(f"[Orchestrator] Engaging Tier-3 Vision Fallback...")
        coords = self.vision.locate_and_click(clean)
        elapsed = (time.time() - t_start) * 1000

        if coords:
            action_payload = {"action": "click_coordinates", "x": coords[0], "y": coords[1]}
            self.graph.record_resolution(clean, action_payload, tier=3.0, app_name=frontmost_app)
            return {
                "tier": 3.0,
                "tier_name": "VisionFallback",
                "status": "executed_via_vision",
                "coords": coords,
                "elapsed_ms": elapsed
            }

        if self.tts.voice_feedback_enabled:
            self.tts.speak("Command not recognized.")

        return {
            "tier": -1,
            "tier_name": "Unresolved",
            "status": "unresolved",
            "command": clean,
            "spoken": "Command not recognized." if self.tts.voice_feedback_enabled else None,
            "elapsed_ms": elapsed
        }

    def _try_tier0_reflex(self, text: str) -> bool:
        clean = text.lower().rstrip(".?!")

        # Voice Feedback Toggles (Kokoro-82M)
        if clean in [
            "voice feedback", "turn on voice feedback", "voice feedback on",
            "voice on", "enable voice", "start speaking", "turn on voice",
            "sound on", "enable audio", "speech on", "voice feedback please",
            "turn voice on"
        ]:
            self.tts.set_voice_feedback(True)
            return True
        if clean in [
            "turn off voice feedback", "voice feedback off", "voice off",
            "mute voice", "silent mode", "stop speaking", "turn off voice",
            "sound off", "mute audio", "disable audio", "turn voice off", "mute"
        ]:
            self.tts.set_voice_feedback(False)
            return True

        # General Capabilities / What Can You Do Query (<1ms Reflex)
        if clean in [
            "what can you do", "what all can you do", "what can you do for me",
            "what are your capabilities", "what can i do", "what can i say",
            "what are the commands", "help", "who are you", "what is this",
            "tell me what you can do"
        ]:
            msg = "I can control your Mac and answer questions. You can tell me to open any app, search the web, scroll pages, play or pause media, adjust volume, or manage files. You can also chat or ask me general questions anytime."
            if self.tts.voice_feedback_enabled:
                self.tts.speak(msg)
            return msg

        # Hands-free mode voice toggles
        if clean in ["hands free mode", "hands free on", "enable hands free", "always listen", "disable wake word", "no wake word"]:
            self.lifecycle.wake_word_required = False
            msg = "Hands-free mode enabled. You can talk naturally without saying Hey Mac."
            if self.tts.voice_feedback_enabled:
                self.tts.speak(msg)
            return msg
        if clean in ["require wake word", "wake word on", "enable wake word", "hands free off"]:
            self.lifecycle.wake_word_required = True
            msg = "Wake word required. Say Hey Mac to activate."
            if self.tts.voice_feedback_enabled:
                self.tts.speak(msg)
            return msg

        # Media
        if clean in ["play", "pause", "resume", "play pause"]:
            if self.browser.is_connected:
                res = self.browser.toggle_video_playback()
                if "Playing" in res or "Paused" in res:
                    return True
            self.macos.toggle_play_pause()
            return True

        # Volume
        if clean in ["volume up", "louder"]:
            self.macos.volume_up()
            return True
        if clean in ["volume down", "quieter"]:
            self.macos.volume_down()
            return True
        if clean in ["mute", "unmute"]:
            self.macos.mute()
            return True

        # Scrolling
        if clean in ["scroll down", "page down", "go down"]:
            if self.browser.is_connected:
                self.browser.scroll_page("down", 500)
            else:
                self.macos.scroll_down(pages=1)
            return True
        if clean in ["scroll up", "page up", "go up"]:
            if self.browser.is_connected:
                self.browser.scroll_page("up", 500)
            else:
                self.macos.scroll_up(pages=1)
            return True

        # Tabs
        if clean in ["new tab", "open new tab"]:
            self.macos.new_tab()
            return True
        if clean in ["close tab", "close this tab"]:
            self.macos.close_tab()
            return True
        if clean in ["next tab", "switch tab"]:
            self.macos.next_tab()
            return True
        if clean in ["previous tab", "prev tab"]:
            self.macos.previous_tab()
            return True
        if clean in ["reload", "refresh"]:
            self.macos.reload_page()
            return True

        # Approvals
        if clean in ["allow", "approve", "accept", "click allow"]:
            self.macos.click_dialog_button("Allow")
            return True
        if clean in ["dismiss", "cancel dialog"]:
            self.macos.dismiss_dialog()
            return True

        # Lock
        if clean in ["lock screen", "lock mac"]:
            self.macos.lock_screen()
            return True

        # Fast App Launch / Switch Regex (<2ms)
        m_open = re.match(r"^(?:can you\s+|could you\s+|please\s+|i want to\s+|let's\s+|you might\s+)?(?:open|launch|start)\s+(.+)$", clean)
        if m_open:
            raw_target = m_open.group(1).strip()
            target_app = self._clean_app_name(raw_target)
            # If target looks like a URL or search, defer to browser
            if not target_app.startswith("http") and not "." in target_app:
                self.macos.open_app(target_app)
                spoken = f"Opening {target_app}."
                if self.tts.voice_feedback_enabled:
                    self.tts.speak(spoken)
                return spoken

        m_focus = re.match(r"^(?:can you\s+|could you\s+|please\s+)?(?:switch to|focus|focus window|go to)\s+(.+)$", clean)
        if m_focus:
            raw_target = m_focus.group(1).strip()
            target_app = self._clean_app_name(raw_target)
            res = self.macos.focus_window(target_app)
            if not res.get("success"):
                self.macos.open_app(target_app)
            spoken = f"Switched to {target_app}."
            if self.tts.voice_feedback_enabled:
                self.tts.speak(spoken)
            return spoken

        # Fast Search
        m_search = re.match(r"^(?:can you\s+|could you\s+|please\s+)?(?:search for|google|search)\s+(.+)$", clean)
        if m_search:
            query = m_search.group(1).strip()
            self.browser.search_web(query)
            spoken = f"Searching for {query}."
            if self.tts.voice_feedback_enabled:
                self.tts.speak(spoken)
            return spoken

        # Fast Direct File Write: "write <content> to <path>"
        m_write = re.match(r"^(?:write|save)\s+(.+?)\s+to\s+([~/].+)$", clean, flags=re.IGNORECASE)
        if m_write:
            content_val = m_write.group(1).strip()
            target_path = m_write.group(2).strip()
            ok, msg = SafeFileSystem.safe_write(target_path, content_val)
            spoken = "File saved." if ok else "Access denied."
            if self.tts.voice_feedback_enabled:
                self.tts.speak(spoken)
            return spoken

        # Fast Direct File Read: "read file <path>"
        m_read = re.match(r"^(?:read file|read)\s+([~/].+)$", clean, flags=re.IGNORECASE)
        if m_read:
            target_path = m_read.group(1).strip()
            ok, content_val = SafeFileSystem.safe_read(target_path)
            spoken = "File read." if ok else "Could not read file."
            if self.tts.voice_feedback_enabled:
                self.tts.speak(spoken)
            return spoken

        return False

    def _clean_app_name(self, raw_app: str) -> str:
        if not raw_app:
            return ""
        clean = os.path.basename(raw_app).replace(".app", "").strip()
        clean = clean.strip(" /\\\"'")
        return self.app_aliases.get(clean.lower(), clean)

    def _execute_action_payload(self, action_dict: Dict[str, Any], frontmost_app: Optional[str] = None) -> bool:
        action = str(action_dict.get("action", "")).lower().strip()
        try:
            if action in ["safe_write_file", "write_file", "save_file"]:
                ok, msg = SafeFileSystem.safe_write(action_dict.get("path", ""), action_dict.get("content", ""))
                print(f"[Safe File] {msg}")
                return ok
            elif action in ["safe_read_file", "read_file"]:
                ok, content = SafeFileSystem.safe_read(action_dict.get("path", ""))
                if ok:
                    print(f"[Safe Read Content]: {content[:200]}...")
                return ok
            elif action == "click_coordinates":
                return self.vision.click_coordinates(action_dict["x"], action_dict["y"])
            elif action == "open_url":
                return self.browser.open_url(action_dict["url"])
            elif action == "search":
                return self.browser.search_web(action_dict.get("query", ""))
            elif action == "click_link":
                target = action_dict.get("text", "")
                if self.browser.click_link_or_text(target):
                    return True
                res = self.macos.click_element(target, app=frontmost_app)
                return res.get("success", False)
            elif action in ["toggle_video", "play_pause_video", "play_video", "pause_video"]:
                return "Playing" in self.browser.toggle_video_playback() or "Paused" in self.browser.toggle_video_playback()
            elif action in ["scroll", "scroll_page", "scroll_down", "scroll_up"]:
                dir_val = action_dict.get("direction", "down")
                if "up" in action:
                    dir_val = "up"
                elif "down" in action:
                    dir_val = "down"
                return self.browser.scroll_page(dir_val, action_dict.get("amount", 500))
            elif action in ["open_app", "launch_app", "open", "launch"]:
                app_name = self._clean_app_name(action_dict.get("app") or action_dict.get("query", ""))
                self.macos.open_app(app_name)
                return True
            elif action in ["focus_window", "switch_window", "switch_to", "focus", "click_window", "activate_app"]:
                app_name = self._clean_app_name(action_dict.get("app") or action_dict.get("query", ""))
                res = self.macos.focus_window(app_name)
                if not res.get("success"):
                    self.macos.open_app(app_name)
                return True
            elif action in ["click_element", "click", "tap"]:
                target_query = action_dict.get("query") or action_dict.get("text") or action_dict.get("name", "")
                res = self.macos.click_element(target_query, app=self._clean_app_name(action_dict.get("app") or "") or frontmost_app)
                return res.get("success", False)
            elif action in ["type_text", "type", "write"]:
                res = self.macos.type_text(action_dict.get("text", ""), app=self._clean_app_name(action_dict.get("app") or "") or frontmost_app)
                return res.get("success", False)
            elif action == "maximize_window":
                app_name = self._clean_app_name(action_dict.get("app", ""))
                res = self.macos.maximize_window(app_name)
                return res.get("success", False)
            elif action == "minimize_window":
                app_name = self._clean_app_name(action_dict.get("app", ""))
                res = self.macos.minimize_window(app_name)
                return res.get("success", False)
            elif action == "approve_dialog":
                res = self.macos.click_dialog_button("Allow")
                return res.get("success", False)
        except Exception as e:
            print(f"[Action Error] {e}")
        return False

    def shutdown(self):
        self.bus.stop()
        self.browser.disconnect()
        self.macos.disconnect()
        self.llm.disconnect()
        self.vision.disconnect()
        self.tts.disconnect()
        print("[Orchestrator] All connectors cleanly shut down.")
