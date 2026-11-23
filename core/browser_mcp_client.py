"""
Browser Controller using Playwright and CDP.

Features:
1. Connects to existing Chrome/Brave via CDP (port 9222) or launches a headless/headful session.
2. Zero-popup architecture:
   - Listens for all JavaScript dialogs and automatically accepts them: page.on('dialog', lambda d: d.accept())
   - No extension pairing required.
3. Fast Actions:
   - navigate(url) / search(query)
   - click_link(text_or_selector)
   - toggle_video() (Play/Pause all HTML5 videos on page)
   - scroll(direction, amount)
   - get_clickable_elements(): returns indexed list of clickable elements for the LLM to pick from
"""

import time
import socket
from typing import Optional, List, Dict, Any

def is_cdp_port_open(port: int = 9222, timeout: float = 0.05) -> bool:
    """Ultra-fast (1ms) socket check to verify if browser debugging port is listening."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False

class BrowserMCPClient:
    def __init__(self, cdp_port: int = 9222):
        self.cdp_port = cdp_port
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def _ensure_connected(self) -> bool:
        """Connects to running browser via CDP or launches Chromium instance."""
        if self._page and not self._page.is_closed():
            return True

        from playwright.sync_api import sync_playwright

        # Fast 1ms socket check before attempting CDP
        if is_cdp_port_open(self.cdp_port):
            try:
                if not self._playwright:
                    self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{self.cdp_port}")
                contexts = self._browser.contexts
                if contexts:
                    self._context = contexts[0]
                    pages = self._context.pages
                    self._page = pages[0] if pages else self._context.new_page()
                else:
                    self._context = self._browser.new_context()
                    self._page = self._context.new_page()
                self._setup_auto_accept_dialogs()
                return True
            except Exception as e:
                print(f"[Browser MCP] CDP connect error: {e}")

        # If CDP not listening, try launching Chromium instance
        try:
            if not self._playwright:
                self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=False)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
            self._setup_auto_accept_dialogs()
            return True
        except Exception:
            return False

    def _setup_auto_accept_dialogs(self):
        """Automatically accepts alert/confirm/prompt without showing popups."""
        if self._page:
            self._page.on("dialog", lambda dialog: dialog.accept())

    def open_url(self, url: str) -> bool:
        if not self._ensure_connected():
            return False
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=10000)
            return True
        except Exception as e:
            print(f"[Browser MCP] Navigation error: {e}")
            return False

    def search_web(self, query: str) -> bool:
        import urllib.parse
        encoded = urllib.parse.quote(query)
        return self.open_url(f"https://www.google.com/search?q={encoded}")

    def toggle_video_playback(self) -> str:
        """Toggles play/pause on any HTML5 video on the active page."""
        if not self._ensure_connected():
            return "Browser not connected"
        js = """
        (() => {
            const videos = Array.from(document.querySelectorAll('video'));
            if (videos.length === 0) return "No video elements found";
            let state = "";
            videos.forEach(v => {
                if (v.paused) {
                    v.play();
                    state = "Playing";
                } else {
                    v.pause();
                    state = "Paused";
                }
            });
            return state;
        })()
        """
        try:
            return self._page.evaluate(js)
        except Exception as e:
            return f"Error: {e}"

    def scroll_page(self, direction: str = "down", amount: int = 500) -> bool:
        """Scrolls the page smoothly."""
        if not self._ensure_connected():
            return False
        delta_y = amount if direction == "down" else -amount
        try:
            self._page.evaluate(f"window.scrollBy({{top: {delta_y}, behavior: 'smooth'}})")
            return True
        except Exception:
            return False

    def click_link_or_text(self, text: str) -> bool:
        """Clicks an element matching the given text or selector."""
        if not self._ensure_connected():
            return False
        try:
            # 1. Try text selector
            elem = self._page.get_by_text(text, exact=False).first
            if elem.is_visible():
                elem.click(timeout=3000)
                return True
        except Exception:
            pass

        try:
            # 2. Try role link or button
            self._page.locator(f"text='{text}'").first.click(timeout=3000)
            return True
        except Exception as e:
            print(f"[Browser MCP] Click error: {e}")
            return False

    def get_visible_links(self, max_links: int = 15) -> List[Dict[str, str]]:
        """Returns indexed list of visible links on page for voice target selection."""
        if not self._ensure_connected():
            return []
        js = """
        (() => {
            const links = Array.from(document.querySelectorAll('a, button'));
            return links
                .filter(el => el.offsetParent !== null && el.innerText.trim().length > 0)
                .slice(0, 30)
                .map((el, idx) => ({ id: idx + 1, text: el.innerText.trim().replace(/\\n/g, ' '), href: el.href || '' }));
        })()
        """
        try:
            return self._page.evaluate(js)[:max_links]
        except Exception:
            return []

    def close(self):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
