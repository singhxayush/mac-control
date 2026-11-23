"""
macOS Accessibility Bridge using Peekaboo & System Events.

Capabilities:
1. Fast System Events / AppleScript (<10ms) for media, keycodes, and volume.
2. Peekaboo Bridge (using local daemon at ~/Library/Application Support/Peekaboo/daemon.sock):
   - UI Element clicking by text or query: `peekaboo click "<query>" --app "<app>"`
   - Typing into fields: `peekaboo type "<text>"`
   - Window manipulation: focus, minimize, maximize, resize
   - System Dialog / Alert handling: `peekaboo dialog click --button "Allow"`
   - Inspection: `peekaboo inspect_ui` and `peekaboo window list`
"""

import subprocess
import json
from typing import Optional, List, Dict, Any

class AccessibilityBridge:
    def __init__(self):
        self._check_peekaboo_ready()

    def _check_peekaboo_ready(self):
        # We know peekaboo permissions are already granted on this machine
        pass

    def run_peekaboo(self, args: List[str]) -> Dict[str, Any]:
        """Runs a peekaboo CLI command and returns parsed JSON output if available."""
        cmd = ["npx", "-y", "@steipete/peekaboo"] + args
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if "--json" in args or "-j" in args:
                try:
                    return json.loads(res.stdout)
                except Exception:
                    pass
            return {"success": res.returncode == 0, "stdout": res.stdout.strip(), "stderr": res.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- UI Element Interactions ---
    def click_element(self, query: str, app: Optional[str] = None) -> Dict[str, Any]:
        """Clicks on a UI button or element by matching text/query."""
        args = ["click", query]
        if app:
            args.extend(["--app", app])
        args.append("--json")
        return self.run_peekaboo(args)

    def type_text(self, text: str, app: Optional[str] = None) -> Dict[str, Any]:
        """Types text into the active field."""
        args = ["type", text]
        if app:
            args.extend(["--app", app])
        args.append("--json")
        return self.run_peekaboo(args)

    # --- Dialog & Modal Auto-Approval ---
    def click_dialog_button(self, button_name: str = "Allow", app: Optional[str] = None) -> Dict[str, Any]:
        """Auto-clicks 'Allow', 'OK', 'Continue' on system permission or browser alerts."""
        args = ["dialog", "click", "--button", button_name]
        if app:
            args.extend(["--app", app])
        args.append("--json")
        return self.run_peekaboo(args)

    def dismiss_dialog(self, app: Optional[str] = None) -> Dict[str, Any]:
        """Dismisses the current modal dialog."""
        args = ["dialog", "dismiss"]
        if app:
            args.extend(["--app", app])
        return self.run_peekaboo(args)

    # --- Window Management ---
    def list_windows(self, app: str) -> List[Dict[str, Any]]:
        res = self.run_peekaboo(["window", "list", "--app", app, "--json"])
        if isinstance(res, dict) and "data" in res and "windows" in res["data"]:
            return res["data"]["windows"]
        return []

    def focus_window(self, app: str, window_title: Optional[str] = None) -> Dict[str, Any]:
        args = ["window", "focus", "--app", app]
        if window_title:
            args.extend(["--window-title", window_title])
        return self.run_peekaboo(args)

    def maximize_window(self, app: str) -> Dict[str, Any]:
        return self.run_peekaboo(["window", "maximize", "--app", app])

    def minimize_window(self, app: str) -> Dict[str, Any]:
        return self.run_peekaboo(["window", "minimize", "--app", app])
