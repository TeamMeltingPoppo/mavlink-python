from .generated import mavlink
from queue import Queue
from dataclasses import dataclass
import threading

@dataclass(frozen=True)
class MAVLinkStatusSnapshot:
    observed_messages: frozenset[tuple[int, int, int]]
    last_received: dict[tuple[int, int, int], int]

class MAVLinkStatus:
    """A subscriber to MAVLink messages based on msgid, sysid, and compid."""
    def __init__(self):
        self.observed_messages: set[tuple[int, int, int]] = set()
        self.last_received: dict[tuple[int, int, int], int] = {}
        self._lock = threading.Lock()  # Lock for thread-safe operations
    def update(self, msgid: int, sysid: int, compid: int, timestamp: int):
        """Update the status with a new message."""
        with self._lock:
            self.observed_messages.add((msgid, sysid, compid))
            self.last_received[(msgid, sysid, compid)] = timestamp
    def snapshot(self) -> MAVLinkStatusSnapshot:
        """Get a snapshot of the current status."""
        with self._lock:
            return MAVLinkStatusSnapshot(
                observed_messages=frozenset(self.observed_messages),
                last_received=self.last_received.copy()
            )