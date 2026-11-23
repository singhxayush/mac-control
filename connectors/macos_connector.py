"""
macOS System & Accessibility Connector.
Manages AppleScript, System Events, and Peekaboo bridge interactions.
"""

import subprocess
import json
from typing import Optional, Dict, Any, List
from connectors.base import BaseConnector

class MacOSConnector(BaseConnector):
    def __init__(self):
        super().__init__(name="macos_accessibility")

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def health_check(self) -> Dict[str, Any]:
        can_run = False
        try:
            res = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=2
            )
            can_run = res.returncode == 0
        except Exception:
            pass
        return {"name": self.name, "connected": self._connected, "accessibility_active": can_run}

    def run_applescript(self, script: str) -> str:
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            return res.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error: {e.stderr.strip()}"

    # --- Fast Reflex Controls (<10ms) ---
    def toggle_play_pause(self):
        return self.run_applescript('tell application "System Events" to key code 49')

    def volume_up(self, step: int = 8):
        return self.run_applescript(f'set volume output volume ((output volume of (get volume settings)) + {step})')

    def volume_down(self, step: int = 8):
        return self.run_applescript(f'set volume output volume ((output volume of (get volume settings)) - {step})')

    def mute(self):
        return self.run_applescript('set volume output muted (not (output muted of (get volume settings)))')

    def scroll_down(self, pages: int = 1):
        code = 121 if pages > 0 else 125
        return self.run_applescript(f'tell application "System Events" to key code {code}')

    def scroll_up(self, pages: int = 1):
        code = 116 if pages > 0 else 126
        return self.run_applescript(f'tell application "System Events" to key code {code}')

    def new_tab(self):
        return self.run_applescript('tell application "System Events" to keystroke "t" using command down')

    def close_tab(self):
        return self.run_applescript('tell application "System Events" to keystroke "w" using command down')

    def next_tab(self):
        return self.run_applescript('tell application "System Events" to keystroke "]" using {command down, shift down}')

    def previous_tab(self):
        return self.run_applescript('tell application "System Events" to keystroke "[" using {command down, shift down}')

    def reload_page(self):
        return self.run_applescript('tell application "System Events" to keystroke "r" using command down')

    def open_app(self, app_name: str):
        return subprocess.run(["open", "-a", app_name], capture_output=True, text=True)

    def get_frontmost_app(self) -> str:
        return self.run_applescript('tell application "System Events" to get name of first application process whose frontmost is true')

    def lock_screen(self):
        return self.run_applescript('tell application "System Events" to keystroke "q" using {control down, command down}')

    # --- Peekaboo UI Bridge ---
    def click_element(self, query: str, app: Optional[str] = None) -> Dict[str, Any]:
        args = ["click", query]
        if app:
            args.extend(["--app", app])
        args.append("--json")
        return self._run_peekaboo(args)

    def type_text(self, text: str, app: Optional[str] = None) -> Dict[str, Any]:
        args = ["type", text]
        if app:
            args.extend(["--app", app])
        args.append("--json")
        return self._run_peekaboo(args)

    def click_dialog_button(self, button_name: str = "Allow", app: Optional[str] = None) -> Dict[str, Any]:
        args = ["dialog", "click", "--button", button_name]
        if app:
            args.extend(["--app", app])
        args.append("--json")
        return self._run_peekaboo(args)

    def dismiss_dialog(self, app: Optional[str] = None) -> Dict[str, Any]:
        args = ["dialog", "dismiss"]
        if app:
            args.extend(["--app", app])
        return self._run_peekaboo(args)

    def focus_window(self, app: str) -> Dict[str, Any]:
        return self._run_peekaboo(["window", "focus", "--app", app])

    def maximize_window(self, app: str) -> Dict[str, Any]:
        return self._run_peekaboo(["window", "maximize", "--app", app])

    def minimize_window(self, app: str) -> Dict[str, Any]:
        return self._run_peekaboo(["window", "minimize", "--app", app])

    def _run_peekaboo(self, args: List[str]) -> Dict[str, Any]:
        cmd = ["npx", "-y", "@steipete/peekaboo"] + args
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if "--json" in args or "-j" in args:
                try:
                    return json.loads(res.stdout)
                except Exception:
                    pass
            return {"success": res.returncode == 0, "stdout": res.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}
