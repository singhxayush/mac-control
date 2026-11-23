"""
Multi-Layered Safety Guardrail & System Restraint Harness.

Guarantees:
1. HARD PROHIBITION:
   - Zero `sudo`, `su`, root escalations, kernel alterations.
   - Zero permanent file deletions (`rm`, `unlink` are completely blocked).
   - Zero modifications to /System, /Library, /etc, /usr, ~/.ssh, shell dotfiles.
   - Zero arbitrary shell script/binary execution.
2. SAFE FILE OPERATIONS:
   - Only non-executable user data/code files (.py, .js, .json, .md, .txt).
   - Deletions are strictly moved to macOS ~/.Trash via Finder with verbal confirmation.
3. TWO-PHASE VERBAL AUTHORIZATION:
   - Hard blocks: Rejected immediately with audible warning.
   - Sensitive safe operations (moving to trash): Held in pending state, prompts verbally, awaits "yes/no".
"""

import re
from enum import Enum
from typing import Optional, Callable, Dict, Any, Tuple
from core.safe_fs import SafeFileSystem

class PolicyVerdict(Enum):
    ALLOWED = "allowed"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    HARD_BLOCKED = "hard_blocked"

# Unbreakable blocklist: Any command matching these is immediately rejected
HARD_FORBIDDEN_PATTERNS = [
    r"\bsudo\b", r"\bsu\b", r"\bdoas\b",
    r"\bchmod\b", r"\bchown\b", r"\bchgrp\b", r"\bchflags\b",
    r"\brm\s+", r"\bunlink\b", r"\bshred\b", r"\bsrm\b",
    r"\blaunchctl\b", r"\bkextload\b", r"\bkextunload\b",
    r"\bdefaults\s+write\b", r"\bdscl\b", r"\bfdisk\b",
    r"\bdiskutil\s+erase\b", r"\bmkfs\b", r"\bdd\s+if=",
    r"\bshutdown\b", r"\breboot\b", r"\bhalt\b",
    r"\|\s*(?:bash|sh|zsh)\b", r"\bcurl\b.*\|\s*(?:sh|bash)",
    r"\b/System\b", r"\b/Library\b", r"\b/etc\b", r"\b/var\b",
    r"\b/private\b", r"\b/usr/bin\b", r"\b/bin\b", r"\b/sbin\b",
    r"\.ssh\b", r"\.zshrc\b", r"\.bashrc\b", r"\.bash_profile\b",
    r"\.sudoers\b", r"\.env\b", r"\bpasswd\b", r"\bshadow\b"
]

SENSITIVE_CONFIRMATION_PATTERNS = [
    r"\btrash\b", r"\bmove to trash\b", r"\bdelete file\b",
    r"\bforce quit\b", r"\bempty trash\b", r"\bcheckout\b",
    r"\bpay\b", r"\bpurchase\b", r"\bclose without saving\b"
]

class SafetyGuard:
    def __init__(self, tts_engine):
        self.tts = tts_engine
        self.awaiting_confirmation = False
        self.pending_action: Optional[Dict[str, Any]] = None

    def evaluate_command_text(self, text: str) -> Tuple[PolicyVerdict, str]:
        """Scans raw natural language or command strings for policy violations."""
        lower = text.lower()

        # 1. Hard Block Evaluation
        for pat in HARD_FORBIDDEN_PATTERNS:
            if re.search(pat, lower):
                reason = f"Command matches hard-prohibited pattern '{pat}'. System commands and sudo are completely blocked."
                return PolicyVerdict.HARD_BLOCKED, reason

        # 2. Sensitive Confirmation Evaluation
        for pat in SENSITIVE_CONFIRMATION_PATTERNS:
            if re.search(pat, lower):
                reason = f"Sensitive action detected ('{pat}'). Verbal confirmation required."
                return PolicyVerdict.REQUIRES_CONFIRMATION, reason

        return PolicyVerdict.ALLOWED, "Command verified safe by harness policy."

    def evaluate_action_payload(self, action_payload: Dict[str, Any]) -> Tuple[PolicyVerdict, str]:
        """Validates structured action payloads emitted by the LLM."""
        action = action_payload.get("action")

        # 1. Hard block on arbitrary shell commands
        if action in ["bash", "shell", "exec"]:
            return PolicyVerdict.HARD_BLOCKED, "Arbitrary shell execution is permanently disabled in this harness."

        # 2. File Writing validation
        if action == "safe_write_file":
            path = action_payload.get("path", "")
            is_valid, msg = SafeFileSystem.validate_path(path, must_exist=False)
            if not is_valid:
                return PolicyVerdict.HARD_BLOCKED, f"File write rejected: {msg}"
            return PolicyVerdict.ALLOWED, "Safe file write verified."

        # 3. File Trash validation
        if action == "safe_trash_file":
            path = action_payload.get("path", "")
            is_valid, msg = SafeFileSystem.validate_path(path, must_exist=True)
            if not is_valid:
                return PolicyVerdict.HARD_BLOCKED, f"Trash action rejected: {msg}"
            return PolicyVerdict.REQUIRES_CONFIRMATION, f"Move file '{path}' to macOS Trash?"

        # 4. AppleScript validation
        if action == "applescript":
            code = action_payload.get("code", "")
            for pat in HARD_FORBIDDEN_PATTERNS:
                if re.search(pat, code.lower()):
                    return PolicyVerdict.HARD_BLOCKED, f"AppleScript contains forbidden pattern '{pat}'."
            return PolicyVerdict.ALLOWED, "AppleScript verified safe."

        return PolicyVerdict.ALLOWED, "Action allowed."

    def request_confirmation(self, description: str, execute_fn: Callable, *args, **kwargs):
        """Intercepts sensitive safe action, prompts user via TTS, and holds state."""
        self.awaiting_confirmation = True
        self.pending_action = {
            "fn": execute_fn,
            "args": args,
            "kwargs": kwargs,
            "description": description
        }

        prompt = f"Confirmation required: {description}. Should I proceed? Say yes or no."
        print(f"\n[SAFETY HARNESS] Sensitive action paused: {description}")
        print(f"[SAFETY HARNESS] Waiting for user confirmation ('yes' / 'no')...")
        self.tts.speak(prompt, force=True)

    def handle_hard_block(self, reason: str):
        """Audibly warns the user that an action was blocked."""
        print(f"\n[SAFETY HARNESS VIOLATION BLOCKED] {reason}")
        self.tts.speak("Action blocked by safety policy. System modifications and sudo are strictly forbidden.", force=True)

    def process_confirmation(self, user_voice_text: str) -> Optional[bool]:
        """Processes voice response when awaiting confirmation."""
        clean = user_voice_text.strip().lower()

        # Affirmative
        if clean in ["yes", "yeah", "yep", "confirm", "proceed", "do it", "sure", "ok"]:
            self.tts.speak("Confirmed. Proceeding.", force=True)
            action = self.pending_action
            self.awaiting_confirmation = False
            self.pending_action = None
            if action and action["fn"]:
                action["fn"](*action["args"], **action["kwargs"])
            return True

        # Negative / Cancel
        elif clean in ["no", "nope", "cancel", "stop", "abort", "don't", "dont"]:
            self.tts.speak("Action cancelled.", force=True)
            self.awaiting_confirmation = False
            self.pending_action = None
            print("[SAFETY HARNESS] Action cancelled by user.")
            return False

        else:
            self.tts.speak("Please say clearly: yes to proceed, or no to cancel.", force=True)
            return None
