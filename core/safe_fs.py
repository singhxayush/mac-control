"""
Safe File System Handler for Mac-Control Harness.

Guarantees:
1. ZERO PERMANENT DELETION: Deletion strictly moves files to macOS ~/.Trash via Finder.
2. EXTENSION RESTRICTIONS: Only user data/code files (.py, .js, .ts, .json, .md, .txt, etc.).
   Executable scripts (.sh, .bash, .command), system plists, binaries (.dylib, .app, .bin) are strictly blocked.
3. PATH SANDBOXING: Confined to user workspace (~/Build, ~/Documents, ~/Desktop, ~/Downloads, /tmp/mac-control).
   System paths (/System, /Library, /etc, /usr, /bin, /sbin, ~/.ssh, ~/.zshrc) are strictly forbidden.
"""

import os
import subprocess
from typing import Tuple, Optional

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".json", ".md", ".markdown", ".txt", ".csv", ".tsv",
    ".yaml", ".yml", ".xml", ".sql", ".log", ".pdf",
    ".png", ".jpg", ".jpeg", ".svg"
}

FORBIDDEN_EXTENSIONS = {
    ".sh", ".bash", ".zsh", ".command", ".dylib", ".so",
    ".app", ".bin", ".pkg", ".dmg", ".plist", ".mobileconfig",
    ".kext", ".exe", ".env", ".key", ".pem", ".cert"
}

ALLOWED_ROOT_PREFIXES = [
    os.path.expanduser("~/Build"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Downloads"),
    "/tmp/mac-control"
]

FORBIDDEN_PATH_SUBSTRINGS = [
    "/System", "/Library", "/usr", "/bin", "/sbin", "/etc", "/var",
    "/private", "/opt/homebrew", ".ssh", ".gnupg", ".zsh", ".bash",
    ".profile", ".config", ".gemini", ".gitconfig", ".sudoers"
]

class SafeFileSystem:
    @staticmethod
    def validate_path(path: str, must_exist: bool = False) -> Tuple[bool, str]:
        """Validates that a path is safe and within permitted boundaries."""
        try:
            expanded = os.path.abspath(os.path.expanduser(path.strip()))
        except Exception as e:
            return False, f"Invalid path syntax: {e}"

        # 1. Check forbidden system substrings
        for forbidden in FORBIDDEN_PATH_SUBSTRINGS:
            if forbidden in expanded:
                return False, f"Access denied: Path touches protected system directory '{forbidden}'."

        # 2. Check allowed roots
        is_inside_allowed = any(expanded.startswith(root) for root in ALLOWED_ROOT_PREFIXES)
        if not is_inside_allowed:
            allowed_list = ", ".join(ALLOWED_ROOT_PREFIXES)
            return False, f"Access denied: Path '{expanded}' is outside allowed workspaces ({allowed_list})."

        # 3. Check extension
        _, ext = os.path.splitext(expanded)
        ext_lower = ext.lower()

        if ext_lower in FORBIDDEN_EXTENSIONS:
            return False, f"Access denied: File extension '{ext_lower}' is forbidden for system safety."

        if ext_lower not in ALLOWED_EXTENSIONS:
            return False, f"Access denied: File extension '{ext_lower}' is not in the allowed safe extensions list."

        if must_exist and not os.path.exists(expanded):
            return False, f"File does not exist: '{expanded}'"

        return True, expanded

    @classmethod
    def safe_write_file(cls, path: str, content: str) -> Tuple[bool, str]:
        """Safely creates or overwrites an allowed file."""
        is_valid, resolved = cls.validate_path(path, must_exist=False)
        if not is_valid:
            return False, resolved

        try:
            os.makedirs(os.path.dirname(resolved), exist_ok=True)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)
            return True, f"File safely written to '{resolved}'"
        except Exception as e:
            return False, f"Write error: {e}"

    @classmethod
    def safe_read_file(cls, path: str, max_bytes: int = 100000) -> Tuple[bool, str]:
        """Safely reads content from an allowed file."""
        is_valid, resolved = cls.validate_path(path, must_exist=True)
        if not is_valid:
            return False, resolved

        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
            return True, content
        except Exception as e:
            return False, f"Read error: {e}"

    @classmethod
    def safe_move_to_trash(cls, path: str) -> Tuple[bool, str]:
        """
        Moves a file to the native macOS Trash via Finder AppleScript.
        NEVER permanently deletes via rm or unlink!
        """
        is_valid, resolved = cls.validate_path(path, must_exist=True)
        if not is_valid:
            return False, resolved

        script = f'tell application "Finder" to delete POSIX file "{resolved}"'
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            return True, f"File safely moved to macOS Trash: {os.path.basename(resolved)}"
        except subprocess.CalledProcessError as e:
            return False, f"Finder trash error: {e.stderr.strip()}"
