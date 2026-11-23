"""
Browser Connector using CDP & Playwright.
Supports lifecycle management (disconnects during sleep to free memory/CPU).
"""

import socket
import urllib.parse
from typing import Optional, List, Dict, Any
from connectors.base import BaseConnector

def is_cdp_port_open(port: int = 9222, timeout: float = 0.05) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False

class BrowserConnector(BaseConnector):
    def __init__(self, cdp_port: int = 9222):
        super().__init__(name="browser_cdp")
        self.cdp_port = cdp_port
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def connect(self) -> bool:
        if self._connected and self._page and not self._page.is_closed():
            return True

        from playwright.sync_api import sync_playwright

        # 1. Try attaching to existing running browser on port 9222
        if is_cdp_port_open(self.cdp_port):
            try:
                if not self._playwright:
                    self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{self.cdp_port}")
                contexts = self._browser.contexts
                self._context = contexts[0] if contexts else self._browser.new_context()
                pages = self._context.pages
                self._page = pages[0] if pages else self._context.new_page()
                self._page.on("dialog", lambda d: d.accept())
                self._connected = True
                return True
            except Exception as e:
                print(f"[BrowserConnector] CDP connect warning: {e}")

        # 2. Otherwise launch isolated Chromium instance
        try:
            if not self._playwright:
                self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=False)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
            self._page.on("dialog", lambda d: d.accept())
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Called on sleep/standby to completely release browser resources."""
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self._browser = None
            self._context = None
            self._page = None
            self._playwright = None
            self._connected = False
            print("[BrowserConnector] Disconnected & freed memory on sleep.")

    def health_check(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "connected": self._connected,
            "cdp_port_open": is_cdp_port_open(self.cdp_port),
            "page_active": bool(self._page and not self._page.is_closed())
        }

    # --- Browser Actions ---
    def open_url(self, url: str) -> bool:
        if not self.connect():
            return False
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=10000)
            return True
        except Exception as e:
            print(f"[BrowserConnector] Open URL error: {e}")
            return False

    def search_web(self, query: str) -> bool:
        encoded = urllib.parse.quote(query)
        return self.open_url(f"https://www.google.com/search?q={encoded}")

    def toggle_video_playback(self) -> str:
        if not self._page or self._page.is_closed():
            return "Browser not connected"
        js = """
        (() => {
            const videos = Array.from(document.querySelectorAll('video'));
            if (videos.length === 0) return "No video elements found";
            let state = "";
            videos.forEach(v => {
                if (v.paused) { v.play(); state = "Playing"; }
                else { v.pause(); state = "Paused"; }
            });
            return state;
        })()
        """
        try:
            return self._page.evaluate(js)
        except Exception as e:
            return f"Error: {e}"

    def scroll_page(self, direction: str = "down", amount: int = 500) -> bool:
        if not self._page or self._page.is_closed():
            return False
        delta_y = amount if direction == "down" else -amount
        try:
            self._page.evaluate(f"window.scrollBy({{top: {delta_y}, behavior: 'smooth'}})")
            return True
        except Exception:
            return False

    def click_link_or_text(self, text: str) -> bool:
        if not self._page or self._page.is_closed():
            return False
        try:
            elem = self._page.get_by_text(text, exact=False).first
            if elem.is_visible():
                elem.click(timeout=3000)
                return True
        except Exception:
            pass
        try:
            self._page.locator(f"text='{text}'").first.click(timeout=3000)
            return True
        except Exception:
            return False

    def get_visible_links(self, max_links: int = 15) -> List[Dict[str, str]]:
        if not self._page or self._page.is_closed():
            return []
        js = """
        (() => {
            const links = Array.from(document.querySelectorAll('a, button'));
            return links
                .filter(el => el.offsetParent !== null && el.innerText.trim().length > 0)
                .slice(0, 30)
                .map((el, idx) => ({ id: idx + 1, text: el.innerText.trim().replace(/\\n/g, ' ') }));
        })()
        """
        try:
            return self._page.evaluate(js)[:max_links]
        except Exception:
            return []
