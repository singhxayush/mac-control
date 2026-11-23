"""
Action Execution & Result Events.
"""

from typing import Dict, Any, Optional
from events.base import BaseEvent, EventPriority

class ActionRequestedEvent(BaseEvent):
    def __init__(self, action_type: str, payload: Dict[str, Any], tier: float = 1.0):
        super().__init__(priority=EventPriority.COMMAND)
        self.action_type = action_type
        self.payload = payload
        self.tier = tier

class ActionExecutedEvent(BaseEvent):
    def __init__(self, action_type: str, success: bool, tier: float, elapsed_ms: float, details: Optional[Dict[str, Any]] = None):
        super().__init__(priority=EventPriority.COMMAND)
        self.action_type = action_type
        self.success = success
        self.tier = tier
        self.elapsed_ms = elapsed_ms
        self.details = details or {}

class ActionFailedEvent(BaseEvent):
    def __init__(self, action_type: str, error: str, tier: float):
        super().__init__(priority=EventPriority.COMMAND)
        self.action_type = action_type
        self.error = error
        self.tier = tier
