"""
Base Connector Interface for Resource Lifecycle Management.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseConnector(ABC):
    def __init__(self, name: str):
        self.name = name
        self._connected: bool = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    def connect(self) -> bool:
        """Initializes or attaches to the underlying resource/service."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Releases handles, closes sockets, and frees memory during sleep/standby."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Returns health/readiness status."""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} connected={self._connected}>"
