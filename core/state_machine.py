"""
Agent State Machine with Wake-Word Activation and Idle Auto-Sleep.
"""

import time
import re
from enum import Enum
from typing import Optional, Tuple, List
from config.settings import settings

class AgentState(Enum):
    SLEEPING = "sleeping"                        # Standby: Low-overhead, only wakes on wake-word
    AWAKE_ACTIVE = "awake_active"                # Active: Ready for immediate commands
    AWAITING_CONFIRMATION = "awaiting_confirm"  # Paused: Waiting for yes/no safety confirmation

class LifecycleManager:
    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        sleep_words: Optional[List[str]] = None,
        idle_timeout: float = 60.0,
        wake_word_required: Optional[bool] = None
    ):
        self.wake_words = [w.lower() for w in (wake_words or settings.lifecycle.wake_words)]
        self.sleep_words = [s.lower() for s in (sleep_words or settings.lifecycle.sleep_words)]
        self.idle_timeout = idle_timeout
        self.wake_word_required = settings.lifecycle.wake_word_required if wake_word_required is None else wake_word_required

        # In hands-free mode (wake_word_required = False), boots directly into AWAKE_ACTIVE!
        self.current_state: AgentState = AgentState.AWAKE_ACTIVE if not self.wake_word_required else AgentState.SLEEPING
        self.last_active_time: float = time.time()

    def check_idle_timeout(self) -> bool:
        """Checks if idle time exceeded. If wake_word_required is False, stays in hands-free mode."""
        if not self.wake_word_required:
            return False
        if self.current_state == AgentState.AWAKE_ACTIVE:
            if time.time() - self.last_active_time > self.idle_timeout:
                self.transition_to(AgentState.SLEEPING, reason="Idle timeout exceeded")
                return True
        return False

    def touch_activity(self):
        """Refreshes the idle watchdog timer."""
        self.last_active_time = time.time()

    def transition_to(self, new_state: AgentState, reason: str = ""):
        old_state = self.current_state
        self.current_state = new_state
        self.touch_activity()
        print(f"[Lifecycle] State change: {old_state.value.upper()} ➜ {new_state.value.upper()} ({reason})")

    def _normalize(self, text: str) -> str:
        """Removes punctuation and collapses extra whitespace for robust voice matching."""
        no_punct = re.sub(r"[,.!\?;:]+", " ", text.lower())
        return re.sub(r"\s+", " ", no_punct).strip()

    def parse_activation(self, text: str) -> Tuple[bool, str]:
        """
        Parses text for wake words and handles follow-up conversational mode.
        Returns (is_activated, remainder_command).
        """
        raw_clean = text.strip()
        norm = self._normalize(raw_clean)

        # Check explicit sleep commands first
        for sw in self.sleep_words:
            sw_norm = self._normalize(sw)
            if re.search(rf"\b{re.escape(sw_norm)}\b", norm):
                self.transition_to(AgentState.SLEEPING, reason=f"User requested '{sw}'")
                return False, ""

        # Check idle timeout if wake-word is required
        self.check_idle_timeout()

        # In hands-free mode (wake_word_required = False) and awake:
        # Every utterance is processed directly with zero wake-word required!
        if not self.wake_word_required and self.current_state == AgentState.AWAKE_ACTIVE:
            self.touch_activity()
            # If the user happened to prefix with "Hey Mac", strip it cleanly
            for ww in self.wake_words:
                ww_norm = self._normalize(ww)
                pattern = rf"^\s*{re.escape(ww_norm)}(?:\s+(.*)|$)"
                match = re.match(pattern, norm)
                if match:
                    rem = match.group(1) or ""
                    return True, rem.strip()
            return True, raw_clean

        if self.current_state == AgentState.AWAKE_ACTIVE:
            self.touch_activity()
            # If the user happens to repeat the wake word while already awake, strip it
            for ww in self.wake_words:
                ww_norm = self._normalize(ww)
                pattern = rf"^\s*{re.escape(ww_norm)}(?:\s+(.*)|$)"
                match = re.match(pattern, norm)
                if match:
                    rem = match.group(1) or ""
                    return True, rem.strip()
            # Follow-up conversational mode: no wake word needed while awake!
            return True, raw_clean

        # If sleeping, require wake word or activation command ("turn on", "wake up", "hey mac")
        for ww in self.wake_words:
            ww_norm = self._normalize(ww)
            pattern = rf"^\s*{re.escape(ww_norm)}(?:\s+(.*)|$)"
            match = re.match(pattern, norm)
            if match:
                remainder = match.group(1) or ""
                self.transition_to(AgentState.AWAKE_ACTIVE, reason=f"Wake-word '{ww}' matched")
                return True, remainder.strip()

        return False, ""
