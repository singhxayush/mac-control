"""
macOS System & Accessibility Controller.
Executes OS-level actions in 10-50ms via native AppleScript and System Events.
"""

import subprocess

class MacOSController:
    @staticmethod
    def run_applescript(script: str) -> str:
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            return res.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error: {e.stderr.strip()}"

    # --- Media & Playback Controls ---
    def toggle_play_pause(self):
        """Simulates Spacebar (key code 49) or media toggle in frontmost app."""
        return self.run_applescript('tell application "System Events" to key code 49')

    def volume_up(self, step=6):
        return self.run_applescript(f'set volume output volume ((output volume of (get volume settings)) + {step})')

    def volume_down(self, step=6):
        return self.run_applescript(f'set volume output volume ((output volume of (get volume settings)) - {step})')

    def mute(self):
        return self.run_applescript('set volume output muted (not (output muted of (get volume settings)))')

    # --- Scrolling & Navigation ---
    def scroll_down(self, pages=1):
        """Key code 121 is Page Down, 125 is Down Arrow."""
        code = 121 if pages > 0 else 125
        return self.run_applescript(f'tell application "System Events" to key code {code}')

    def scroll_up(self, pages=1):
        """Key code 116 is Page Up, 126 is Up Arrow."""
        code = 116 if pages > 0 else 126
        return self.run_applescript(f'tell application "System Events" to key code {code}')

    # --- Tab & Window Management ---
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

    # --- App Switching & System ---
    def open_app(self, app_name: str):
        return subprocess.run(["open", "-a", app_name], capture_output=True, text=True)

    def get_frontmost_app(self) -> str:
        return self.run_applescript('tell application "System Events" to get name of first application process whose frontmost is true')

    def lock_screen(self):
        return self.run_applescript('tell application "System Events" to keystroke "q" using {control down, command down}')
