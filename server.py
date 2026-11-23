#!/usr/bin/env python3
"""
Mac-Control HTTP Daemon with Wake-Word & Lifecycle Support.

Usage:
  .venv/bin/python3 server.py
  curl -X POST http://127.0.0.1:8080/command -H "Content-Type: application/json" -d '{"text": "Hey Mac, scroll down"}'
"""

import sys
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from core.orchestrator import VoiceOSOrchestrator

orchestrator = VoiceOSOrchestrator()

class CommandHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ["/health", "/status"]:
            health = {
                "status": "online",
                "state": orchestrator.lifecycle.current_state.value,
                "voice_feedback_enabled": orchestrator.tts.voice_feedback_enabled,
                "connectors": {
                    "macos": orchestrator.macos.health_check(),
                    "llm": orchestrator.llm.health_check(),
                    "tts": orchestrator.tts.health_check(),
                    "browser": orchestrator.browser.health_check()
                }
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health, indent=2).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/command":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                text = data.get("text", "")
                result = orchestrator.process_voice_input(text)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"[HTTP Daemon] {self.address_string()} - {format % args}")

if __name__ == "__main__":
    server_address = ("127.0.0.1", 8080)
    httpd = HTTPServer(server_address, CommandHandler)
    print("=" * 70)
    print(" Mac-Control HTTP Daemon running on http://127.0.0.1:8080/command")
    print("=" * 70)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        orchestrator.shutdown()
