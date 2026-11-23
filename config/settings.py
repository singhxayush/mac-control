"""
Global Configuration & Settings for Mac-Control.
"""

import os
from dataclasses import dataclass, field
from typing import List, Set

@dataclass
class SafetySettings:
    allowed_roots: List[str] = field(default_factory=lambda: [
        os.path.expanduser("~/Build"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Downloads"),
        "/tmp/mac-control"
    ])
    allowed_extensions: Set[str] = field(default_factory=lambda: {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
        ".json", ".md", ".markdown", ".txt", ".csv", ".tsv",
        ".yaml", ".yml", ".xml", ".sql", ".log", ".pdf",
        ".png", ".jpg", ".jpeg", ".svg"
    })
    forbidden_extensions: Set[str] = field(default_factory=lambda: {
        ".sh", ".bash", ".zsh", ".command", ".dylib", ".so",
        ".app", ".bin", ".pkg", ".dmg", ".plist", ".mobileconfig",
        ".kext", ".exe", ".env", ".key", ".pem", ".cert"
    })
    forbidden_path_substrings: List[str] = field(default_factory=lambda: [
        "/System", "/Library", "/usr", "/bin", "/sbin", "/etc", "/var",
        "/private", "/opt/homebrew", ".ssh", ".gnupg", ".zsh", ".bash",
        ".profile", ".config", ".gemini", ".gitconfig", ".sudoers"
    ])

@dataclass
class LifecycleSettings:
    wake_words: List[str] = field(default_factory=lambda: [
        "hey mac", "mac", "hey mack", "hey matt", "computer", "hey computer", "turn on", "wake up"
    ])
    sleep_words: List[str] = field(default_factory=lambda: [
        "go to sleep", "turn off", "sleep", "standby", "stop listening", "bye mac"
    ])
    idle_timeout_seconds: float = 60.0      # Idle watchdog timer
    hands_free_mode: bool = True            # Hands-free always listening: no wake word required!
    wake_word_required: bool = False        # False = zero "Hey Mac" requirement, just talk naturally

@dataclass
class AudioSettings:
    voice_feedback_enabled: bool = False   # DISABLED / SILENT BY DEFAULT
    kokoro_voice: str = "af_heart"         # Kokoro-82M sweetest warm human voice
    speed: float = 1.0
    volume_step: int = 8

@dataclass
class STTSettings:
    engine: str = "faster_whisper"       # "faster_whisper" (local offline) or "google"
    whisper_model: str = "tiny.en"       # ultra-fast local whisper
    device: str = "auto"                # "auto", "cpu", or "mps"
    energy_threshold: int = 300          # microphone sensitivity threshold
    pause_threshold: float = 0.8         # seconds of silence marking end of phrase
    phrase_time_limit: float = 7.0       # max phrase recording length in seconds

@dataclass
class ConnectorSettings:
    cdp_port: int = 9222
    ollama_model: str = "qwen2.5:0.5b"
    ollama_endpoint: str = "http://127.0.0.1:11434"
    openrouter_model: str = "nvidia/llama-3.1-nemotron-70b-instruct:free"  # NVIDIA Nemotron Free
    openrouter_free_only: bool = True                                      # STRICT ENFORCEMENT: Never charge credits
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    graph_storage_path: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "semantic_graph.json")

@dataclass
class AppSettings:
    safety: SafetySettings = field(default_factory=SafetySettings)
    lifecycle: LifecycleSettings = field(default_factory=LifecycleSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    stt: STTSettings = field(default_factory=STTSettings)
    connectors: ConnectorSettings = field(default_factory=ConnectorSettings)

# Global singleton settings
settings = AppSettings()
