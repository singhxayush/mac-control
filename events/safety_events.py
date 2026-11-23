"""
Safety, Restraint & Authorization Events.
"""

from typing import Dict, Any, Callable
from events.base import BaseEvent, EventPriority

class SafetyViolationEvent(BaseEvent):
    def __init__(self, blocked_command: str, reason: str, rule: str):
        super().__init__(priority=EventPriority.EMERGENCY)
        self.blocked_command = blocked_command
        self.reason = reason
        self.rule = rule

class SafetyConfirmationRequiredEvent(BaseEvent):
    def __init__(self, description: str, pending_action: Dict[str, Any]):
        super().__init__(priority=EventPriority.CONFIRMATION)
        self.description = description
        self.pending_action = pending_action
