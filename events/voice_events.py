"""
Voice Input and Chaining Events.
"""

from typing import List
from events.base import BaseEvent, EventPriority

class RawVoiceInputEvent(BaseEvent):
    def __init__(self, raw_text: str, source: str = "stt"):
        super().__init__(priority=EventPriority.COMMAND)
        self.raw_text = raw_text
        self.source = source

class CompoundCommandEvent(BaseEvent):
    def __init__(self, original_text: str, sub_commands: List[str]):
        super().__init__(priority=EventPriority.COMMAND)
        self.original_text = original_text
        self.sub_commands = sub_commands
