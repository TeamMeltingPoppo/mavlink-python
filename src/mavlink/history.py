from .generated import mavlink
from typing import Optional
from collections import deque
from .subscriber_base import MAVLinkSubscriberBase

class MAVLinkHistory(MAVLinkSubscriberBase):
    """A subscriber that keeps a history of messages."""
    def __init__(self, msgid:int, sysid:int, compid:int,duration:float=10.0,maxsize:int=10000):
        super().__init__(msgid, sysid, compid,maxsize=maxsize)
        self.__duration = duration
        self.history : deque[tuple[float, mavlink.MAVLink_message]] = deque(maxlen=maxsize)
    def sync(self,sync_timestamp:Optional[float]=None):
        """Update the history with the latest message."""
        while not self.queue.empty():
            timestamp, msg = self.queue.get()
            self.history.append((timestamp, msg))
        if sync_timestamp is None:
            sync_timestamp = self.history[-1][0] if self.history else 0.0
        while self.history and (sync_timestamp - self.history[0][0]) > self.__duration:
            self.history.popleft()
    def messages(self) -> list[tuple[float, mavlink.MAVLink_message]]:
        """Get the history of messages."""
        return self.history
    def clear(self):
        """Clear the history of messages."""
        self.history.clear()
        self.queue.queue.clear()
    def latest(self) -> Optional[tuple[float, mavlink.MAVLink_message]]:
        """Get the latest message from the history."""
        if self.history:
            return self.history[-1]
        return None