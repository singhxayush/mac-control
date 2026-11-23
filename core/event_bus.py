"""
Prioritized Event Bus & Event Buffer for Mac-Control.

Features:
1. Thread-safe priority queue buffer for asynchronous action dispatching.
2. Compound voice command splitting ("open brave and then scroll down").
3. Publish-Subscribe (Pub/Sub) pattern for decoupling Voice Input,
   Fast Router, Safety Interceptor, Execution Engines, Vision Fallback, and Memory Graph.
4. Batch dispatch support: triggers multiple actions in sequence without dropping events.
"""

import time
import uuid
import re
import queue
import threading
from enum import IntEnum
from typing import Callable, Dict, List, Any, Optional

class EventPriority(IntEnum):
    EMERGENCY = 0       # Emergency stop, kill commands
    CONFIRMATION = 1    # Yes/No safety responses
    COMMAND = 2         # Standard user voice commands
    FALLBACK = 3        # Vision / tiered fallbacks
    BACKGROUND = 4      # Memory graph writes, cache indexing

class Event:
    def __init__(self, topic: str, payload: Any, priority: EventPriority = EventPriority.COMMAND):
        self.event_id = str(uuid.uuid4())[:8]
        self.topic = topic
        self.payload = payload
        self.priority = priority
        self.timestamp = time.time()

    def __lt__(self, other):
        # PriorityQueue orders by lowest value first
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp

    def __repr__(self):
        return f"<Event {self.event_id} [{self.topic}] p={self.priority.name}>"

class EventBus:
    def __init__(self):
        self._queue = queue.PriorityQueue()
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

    def subscribe(self, topic: str, handler: Callable[[Event], None]):
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(handler)

    def publish(self, topic: str, payload: Any, priority: EventPriority = EventPriority.COMMAND):
        event = Event(topic=topic, payload=payload, priority=priority)
        self._queue.put(event)
        return event

    def publish_batch(self, events: List[Event]):
        for ev in events:
            self._queue.put(ev)

    def split_compound_commands(self, voice_text: str) -> List[str]:
        """
        Splits chained voice requests into discrete sub-commands.
        Examples:
          'open brave and then scroll down' -> ['open brave', 'scroll down']
          'play video and mute' -> ['play video', 'mute']
        """
        # Split on common speech conjunctions: 'and then', 'then', 'after that', 'and also'
        pattern = r"\s+(?:and then|after that|then|and also|\band\b)\s+"
        sub_cmds = [c.strip() for c in re.split(pattern, voice_text, flags=re.IGNORECASE) if c.strip()]
        return sub_cmds if len(sub_cmds) > 1 else [voice_text.strip()]

    def start(self):
        """Starts the event loop worker thread."""
        self._running = True
        self._worker_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._worker_thread.start()

    def stop(self):
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)

    def _dispatch_loop(self):
        while self._running:
            try:
                event = self._queue.get(timeout=0.2)
                handlers = []
                with self._lock:
                    handlers = list(self._subscribers.get(event.topic, []))
                    # Also trigger wildcard listeners
                    handlers.extend(self._subscribers.get("*", []))

                for handler in handlers:
                    try:
                        handler(event)
                    except Exception as e:
                        print(f"[EventBus Error] Handler for '{event.topic}' failed: {e}")
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[EventBus Worker Error] {e}")
