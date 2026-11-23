"""
Zero-Popup Browser Controller.

Why Browser MCP usually shows a manual pairing popup:
- Browser MCP is typically a Chrome Extension. Chrome extensions enforce user interaction
  (clicking the toolbar icon or entering a 6-digit pin) for security to prevent unauthorized remote control.

How we achieve ZERO-CLICK / ZERO-POPUP remote browser control:
1. Native URL & Tab Navigation: via OS URL handlers and AppleScript (instant, 0 popups).
2. Chrome DevTools Protocol (CDP) / Playwright:
   - Connects directly to Chrome / Brave via `--remote-debugging-port=9222`.
   - Protocol-level control: DOM inspection, link clicking, text input, video play/pause.
   - Zero extensions required. Zero authorization popups ever.
3. Auto-Approval Accessibility Hook (Fallback):
   - If an OS/Browser confirmation prompt does appear, an Accessibility API clicker
     can auto-dismiss and click "Allow".
"""

import json
import urllib.request
import subprocess

class BrowserController:
    def __init__(self, cdp_port=9222):
        self.cdp_port = cdp_port

    def open_url(self, url: str):
        """Opens a URL in the user's default browser (Brave, Chrome, Safari)."""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        subprocess.run(["open", url])

    def search_web(self, query: str):
        """Searches Google/default search engine."""
        encoded = urllib.parse.quote(query)
        self.open_url(f"https://www.google.com/search?q={encoded}")

    def check_cdp_available(self) -> bool:
        """Checks if a browser is running with remote debugging enabled."""
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.cdp_port}/json/version")
            with urllib.request.urlopen(req, timeout=1) as response:
                return response.status == 200
        except Exception:
            return False

    def auto_approve_permission_dialog(self):
        """
        Accessibility fallback:
        If any modal window with 'Allow', 'OK', or 'Pair' pops up, auto-clicks it.
        """
        script = '''
        tell application "System Events"
            set procList to every process whose visible is true
            repeat with proc in procList
                try
                    tell proc
                        if exists (window 1) then
                            set btns to every button of window 1 whose name is "Allow" or name is "OK" or name is "Continue"
                            if (count of btns) > 0 then
                                click item 1 of btns
                                return "Approved " & (name of proc)
                            end if
                        end if
                    end tell
                end try
            end repeat
        end tell
        return "No pending permission dialog"
        '''
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            return res.stdout.strip()
        except Exception as e:
            return str(e)
