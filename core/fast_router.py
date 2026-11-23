"""
Tier-0 Deterministic Fast Router.
Executes instantaneous reflex commands (<10ms latency) without calling an LLM.
"""

import re
from typing import Optional, Callable

class FastRouter:
    def __init__(self, macos_ctrl, tts_engine, browser_mcp, accessibility):
        self.macos = macos_ctrl
        self.tts = tts_engine
        self.browser = browser_mcp
        self.accessibility = accessibility
        self.cached_links = []

        # Mapping of regex patterns to execution functions
        self.routes = [
            # TTS feedback toggle
            (r"^(voice on|enable voice|turn on voice)$", lambda: self.tts.set_enabled(True)),
            (r"^(voice off|mute voice|disable voice|quiet mode)$", lambda: self.tts.set_enabled(False)),

            # Media playback (Spacebar or HTML5 video toggle)
            (r"^(play|pause|resume|toggle video|play pause)$", self._handle_play_pause),

            # Volume
            (r"^(volume up|turn it up|louder)$", lambda: self.macos.volume_up(8)),
            (r"^(volume down|turn it down|quieter)$", lambda: self.macos.volume_down(8)),
            (r"^(mute|unmute)$", self.macos.mute),

            # Scrolling
            (r"^(scroll down|page down|go down)$", lambda: self._handle_scroll("down")),
            (r"^(scroll up|page up|go up)$", lambda: self._handle_scroll("up")),

            # Tabs & Browser navigation
            (r"^(new tab|open new tab)$", self.macos.new_tab),
            (r"^(close tab|close this tab)$", self.macos.close_tab),
            (r"^(next tab|switch tab)$", self.macos.next_tab),
            (r"^(previous tab|prev tab|back tab)$", self.macos.previous_tab),
            (r"^(reload|refresh|refresh page)$", self.macos.reload_page),

            # Auto-approval of modals / dialogs
            (r"^(allow|approve|click allow|accept)$", lambda: self.accessibility.click_dialog_button("Allow")),
            (r"^(dismiss|cancel dialog)$", lambda: self.accessibility.dismiss_dialog()),

            # Link discovery & indexed clicking
            (r"^(list links|show links|read links)$", self._handle_list_links),

            # System
            (r"^(lock screen|lock mac)$", self.macos.lock_screen),
        ]

    def _handle_play_pause(self):
        # If browser already connected via CDP, try HTML5 video toggle
        if self.browser._page and not self.browser._page.is_closed():
            res = self.browser.toggle_video_playback()
            if "Playing" in res or "Paused" in res:
                return
        # Instant macOS Spacebar / Media toggle (<10ms)
        self.macos.toggle_play_pause()

    def _handle_scroll(self, direction):
        # If browser already connected via CDP, use smooth DOM scroll
        if self.browser._page and not self.browser._page.is_closed():
            self.browser.scroll_page(direction, amount=500)
        else:
            # Instant native macOS Page Down / Up keycode (<10ms)
            if direction == "down":
                self.macos.scroll_down(pages=1)
            else:
                self.macos.scroll_up(pages=1)

    def _handle_list_links(self):
        links = self.browser.get_visible_links(max_links=8)
        self.cached_links = links
        if not links:
            self.tts.speak("No visible links detected on the page.")
            return
        print("\n--- Visible Links ---")
        for item in links:
            print(f"[{item['id']}] {item['text']}")
        self.tts.speak(f"Found {len(links)} links. Say 'click link 1' or the name.")

    def try_route(self, text: str) -> bool:
        """
        Attempts to execute the command via Tier-0 fast-path.
        Returns True if handled, False if it needs LLM parsing.
        """
        cleaned = text.strip().lower().rstrip(".?!")

        # Check for indexed link clicking: "click link 2" or "link 2"
        link_match = re.match(r"^(?:click )?link (\d+)$", cleaned)
        if link_match and self.cached_links:
            idx = int(link_match.group(1))
            target = next((l for l in self.cached_links if l["id"] == idx), None)
            if target:
                self.tts.speak(f"Clicking {target['text']}")
                self.browser.click_link_or_text(target["text"])
                return True

        for pattern, action in self.routes:
            if re.match(pattern, cleaned):
                action()
                return True
        return False
