"""
Safety Gatekeeper & Sandbox Enforcement.
"""

import os
import re
import subprocess
from enum import Enum
from typing import Tuple, Optional, Callable, Dict, Any
from telemetry.logging_config import get_security_logger

sec_log = get_security_logger()

from safety.policy import (
    HARD_FORBIDDEN_PATTERNS,
    SENSITIVE_CONFIRMATION_PATTERNS,
    ALLOWED_EXTENSIONS,
    FORBIDDEN_EXTENSIONS,
    ALLOWED_ROOTS,
    FORBIDDEN_PATH_SUBSTRINGS
)

class PolicyVerdict(Enum):
    ALLOWED = "allowed"
    CONFIRMATION_REQUIRED = "confirmation_required"
    HARD_BLOCKED = "hard_blocked"

class SafeFileSystem:
    @staticmethod
    def validate_path(path: str, must_exist: bool = False) -> Tuple[bool, str]:
        try:
            expanded = os.path.abspath(os.path.expanduser(path.strip()))
        except Exception as e:
            return False, f"Invalid path syntax: {e}"

        for forbidden in FORBIDDEN_PATH_SUBSTRINGS:
            if forbidden in expanded:
                return False, f"Access denied: Protected system path '{forbidden}'."

        if not any(expanded.startswith(root) for root in ALLOWED_ROOTS):
            return False, f"Access denied: Path '{expanded}' is outside permitted workspaces."

        _, ext = os.path.splitext(expanded)
        ext_lower = ext.lower()
        if ext_lower in FORBIDDEN_EXTENSIONS:
            return False, f"Access denied: Prohibited extension '{ext_lower}'."
        if ext_lower not in ALLOWED_EXTENSIONS:
            return False, f"Access denied: Non-allowlisted extension '{ext_lower}'."

        if must_exist and not os.path.exists(expanded):
            return False, f"Target does not exist: '{expanded}'."

        return True, expanded

    @classmethod
    def safe_write(cls, path: str, content: str) -> Tuple[bool, str]:
        ok, res = cls.validate_path(path, must_exist=False)
        if not ok:
            sec_log.warning(f"WRITE_DENIED: path='{path}' reason='{res}'")
            return False, res
        try:
            os.makedirs(os.path.dirname(res), exist_ok=True)
            with open(res, "w", encoding="utf-8") as f:
                f.write(content)
            sec_log.info(f"FILE_WRITTEN: path='{res}' bytes={len(content)}")
            return True, f"Safely written: {res}"
        except Exception as e:
            sec_log.error(f"WRITE_ERROR: path='{path}' error='{e}'")
            return False, str(e)

    @classmethod
    def safe_read(cls, path: str, max_bytes: int = 100000) -> Tuple[bool, str]:
        ok, res = cls.validate_path(path, must_exist=True)
        if not ok:
            sec_log.warning(f"READ_DENIED: path='{path}' reason='{res}'")
            return False, res
        try:
            with open(res, "r", encoding="utf-8", errors="replace") as f:
                sec_log.info(f"FILE_READ: path='{res}'")
                return True, f.read(max_bytes)
        except Exception as e:
            sec_log.error(f"READ_ERROR: path='{path}' error='{e}'")
            return False, str(e)

    @classmethod
    def safe_move_to_trash(cls, path: str) -> Tuple[bool, str]:
        """Strictly moves file to macOS Trash via Finder. ZERO permanent deletion."""
        ok, res = cls.validate_path(path, must_exist=True)
        if not ok:
            sec_log.warning(f"TRASH_DENIED: path='{path}' reason='{res}'")
            return False, res
        script = f'tell application "Finder" to delete POSIX file "{res}"'
        try:
            subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            sec_log.info(f"FILE_MOVED_TO_TRASH: path='{res}'")
            return True, f"Safely moved to macOS Trash: {os.path.basename(res)}"
        except subprocess.CalledProcessError as e:
            sec_log.error(f"TRASH_ERROR: path='{path}' error='{e.stderr.strip()}'")
            return False, f"Finder error: {e.stderr.strip()}"

class SafetyGatekeeper:
    def __init__(self, tts_connector=None):
        self.tts = tts_connector
        self.awaiting_confirmation: bool = False
        self.pending_action: Optional[Dict[str, Any]] = None

    def evaluate_text(self, text: str) -> Tuple[PolicyVerdict, str]:
        lower = text.lower()
        for pat in HARD_FORBIDDEN_PATTERNS:
            if re.search(pat, lower):
                reason = f"Hard violation: Matches prohibited pattern '{pat}'."
                sec_log.warning(f"BLOCKED_TEXT: input='{text}' pattern='{pat}'")
                return PolicyVerdict.HARD_BLOCKED, reason
        for pat in SENSITIVE_CONFIRMATION_PATTERNS:
            if re.search(pat, lower):
                reason = f"Sensitive action: Requires verbal confirmation ('{pat}')."
                sec_log.info(f"SENSITIVE_TEXT_CONFIRMATION_REQUIRED: input='{text}' pattern='{pat}'")
                return PolicyVerdict.CONFIRMATION_REQUIRED, reason
        return PolicyVerdict.ALLOWED, "Verified safe."

    def evaluate_action_payload(self, payload: Dict[str, Any]) -> Tuple[PolicyVerdict, str]:
        action = payload.get("action")
        if action in ["bash", "shell", "exec"]:
            sec_log.warning(f"BLOCKED_PAYLOAD: Arbitrary shell action='{action}'")
            return PolicyVerdict.HARD_BLOCKED, "Arbitrary shell execution is permanently disabled."

        if action == "safe_write_file":
            ok, msg = SafeFileSystem.validate_path(payload.get("path", ""))
            if not ok:
                sec_log.warning(f"BLOCKED_PAYLOAD_WRITE: path='{payload.get('path')}' reason='{msg}'")
            return (PolicyVerdict.ALLOWED, "Write allowed.") if ok else (PolicyVerdict.HARD_BLOCKED, msg)

        if action == "safe_trash_file":
            ok, msg = SafeFileSystem.validate_path(payload.get("path", ""), must_exist=True)
            if not ok:
                sec_log.warning(f"BLOCKED_PAYLOAD_TRASH: path='{payload.get('path')}' reason='{msg}'")
                return PolicyVerdict.HARD_BLOCKED, msg
            sec_log.info(f"TRASH_CONFIRMATION_REQUIRED: path='{payload.get('path')}'")
            return PolicyVerdict.CONFIRMATION_REQUIRED, f"Move '{payload.get('path')}' to macOS Trash?"

        return PolicyVerdict.ALLOWED, "Payload verified safe."

    def request_confirmation(self, description: str, execute_fn: Callable, *args, **kwargs):
        self.awaiting_confirmation = True
        self.pending_action = {"fn": execute_fn, "args": args, "kwargs": kwargs, "desc": description}
        sec_log.info(f"USER_CONFIRMATION_REQUESTED: desc='{description}'")
        print(f"\n[SAFETY GATEKEEPER] Confirmation required: {description}")
        if self.tts:
            self.tts.speak(f"Confirmation required: {description}. Please say yes or no.")

    def process_confirmation(self, response_text: str) -> Optional[bool]:
        clean = response_text.strip().lower()
        if clean in ["yes", "yeah", "yep", "confirm", "proceed", "do it", "sure", "ok"]:
            action = self.pending_action
            self.awaiting_confirmation = False
            self.pending_action = None
            sec_log.info(f"USER_CONFIRMATION_GRANTED: response='{clean}'")
            if action and action["fn"]:
                action["fn"](*action["args"], **action["kwargs"])
            return True
        elif clean in ["no", "nope", "cancel", "stop", "abort"]:
            self.awaiting_confirmation = False
            self.pending_action = None
            sec_log.info(f"USER_CONFIRMATION_DENIED: response='{clean}'")
            print("[SAFETY GATEKEEPER] Action cancelled by user.")
            return False
        return None
