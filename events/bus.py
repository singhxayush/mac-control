"""
Strongly-Typed Prioritized Event Bus.
"""

import queue
import re
import threading
from typing import Callable, Dict, List, Type, Any, Optional
from events.base import BaseEvent

class EventBus:
    def __init__(self):
        self._queue: queue.PriorityQueue[BaseEvent] = queue.PriorityQueue()
        self._subscribers: Dict[str, List[Callable[[BaseEvent], None]]] = {}
        self._type_subscribers: Dict[Type[BaseEvent], List[Callable[[Any], None]]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

    def subscribe_type(self, event_cls: Type[BaseEvent], handler: Callable[[Any], None]):
        """Subscribes a handler to a specific Event class type."""
        with self._lock:
            if event_cls not in self._type_subscribers:
                self._type_subscribers[event_cls] = []
            self._type_subscribers[event_cls].append(handler)

    def subscribe(self, event_name: str, handler: Callable[[BaseEvent], None]):
        """Subscribes by event string name or '*' for all."""
        with self._lock:
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []
            self._subscribers[event_name].append(handler)

    def publish(self, event: BaseEvent):
        """Pushes an event into the prioritized buffer."""
        self._queue.put(event)

    def publish_batch(self, events: List[BaseEvent]):
        for ev in events:
            self._queue.put(ev)

    def split_compound_commands(self, text: str) -> List[str]:
        """Splits speech conjunctions ('and then', 'then', 'and also', 'after that')."""
        pattern = r"\s+(?:and then|after that|then|and also|\band\b)\s+"
        parts = [p.strip() for p in re.split(pattern, text, flags=re.IGNORECASE) if p.strip()]
        return parts if len(parts) > 1 else [text.strip()]

    def start(self):
        self._running = True
        self._worker_thread = threading.Thread(target=self._dispatch_loop, daemon=True, name="EventBusWorker")
        self._worker_thread.start()

    def stop(self):
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)

    def _dispatch_loop(self):
        while self._running:
            try:
                event = self._queue.get(timeout=0.2)
                with self._lock:
                    # 1. Type-based subscribers
                    handlers_type = list(self._type_subscribers.get(type(event), []))
                    # 2. Name-based subscribers
                    handlers_name = list(self._subscribers.get(event.event_type, []))
                    # 3. Wildcard subscribers
                    handlers_wildcard = list(self._subscribers.get("*", []))

                all_handlers = handlers_type + handlers_name + handlers_wildcard
                for h in all_handlers:
                    try:
                        h(event)
                    except Exception as e:
                        print(f"[EventBus Handler Error] {event.event_type} failed: {e}")

                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[EventBus Loop Error] {e}")
