"""
Base Event Classes and Priority Definitions.
"""

import time
import uuid
from abc import ABC
from enum import IntEnum
from typing import Any, Dict

class EventPriority(IntEnum):
    EMERGENCY = 0       # Immediate stop, kill, or mute actions
    CONFIRMATION = 1    # Yes/No safety responses
    LIFECYCLE = 2       # Wake-word detection, sleep commands, state transitions
    COMMAND = 3         # Normal user voice commands
    BACKGROUND = 4      # Semantic graph learning, cache sync, logging

class BaseEvent(ABC):
    def __init__(self, priority: EventPriority = EventPriority.COMMAND):
        self.event_id: str = str(uuid.uuid4())[:8]
        self.timestamp: float = time.time()
        self.priority: EventPriority = priority

    @property
    def event_type(self) -> str:
        return self.__class__.__name__

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "priority": self.priority.name,
        }

    def __lt__(self, other: "BaseEvent") -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp

    def __repr__(self) -> str:
        return f"<{self.event_type} id={self.event_id} p={self.priority.name}>"
