"""
Safety Policy Rules and Constants.
"""

from typing import List, Set
from config.settings import settings

HARD_FORBIDDEN_PATTERNS: List[str] = [
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

SENSITIVE_CONFIRMATION_PATTERNS: List[str] = [
    r"\btrash\b", r"\bmove to trash\b", r"\bdelete file\b",
    r"\bforce quit\b", r"\bempty trash\b", r"\bcheckout\b",
    r"\bpay\b", r"\bpurchase\b"
]

ALLOWED_EXTENSIONS: Set[str] = settings.safety.allowed_extensions
FORBIDDEN_EXTENSIONS: Set[str] = settings.safety.forbidden_extensions
ALLOWED_ROOTS: List[str] = settings.safety.allowed_roots
FORBIDDEN_PATH_SUBSTRINGS: List[str] = settings.safety.forbidden_path_substrings
