"""
Lifecycle and State Machine Events.
"""

from events.base import BaseEvent, EventPriority

class WakeWordDetectedEvent(BaseEvent):
    def __init__(self, wake_word: str, remainder_command: str = ""):
        super().__init__(priority=EventPriority.LIFECYCLE)
        self.wake_word = wake_word
        self.remainder_command = remainder_command

class SleepRequestedEvent(BaseEvent):
    def __init__(self, trigger: str = "command"):
        super().__init__(priority=EventPriority.LIFECYCLE)
        self.trigger = trigger  # 'command', 'idle_timeout', or 'manual'

class StateTransitionEvent(BaseEvent):
    def __init__(self, from_state: str, to_state: str, reason: str = ""):
        super().__init__(priority=EventPriority.LIFECYCLE)
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
