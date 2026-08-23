from .generated import mavlink
from queue import Queue
from typing import Optional,Callable
from collections import deque
from .subscriber_base import MAVLinkSubscriberBase

class MAVLinkHistory(MAVLinkSubscriberBase):
    """A subscriber that keeps a history of messages."""
    def __init__(self, filter:Callable[[int,int,int],bool],duration:int=1000_000,maxsize:int=10000):
        super().__init__(filter=filter)
        self.__duration = duration
        self.__queue : Queue[tuple[float, mavlink.MAVLink_message]] = Queue(maxsize=maxsize)
        self.history : deque[tuple[float, mavlink.MAVLink_message]] = deque(maxlen=maxsize)
    def sync(self,sync_timestamp:Optional[int]=None):
        """Update the history with the latest message."""
        while not self.__queue.empty():
            timestamp, msg = self.__queue.get()
            self.history.append((timestamp, msg))
        if len(self.history) == 0:
            return
        if sync_timestamp is None:
            sync_timestamp = self.history[-1][0] if self.history else 0.0
        while self.history and (sync_timestamp - self.history[0][0]) > self.__duration:
            self.history.popleft()
    def __push__(self,item:tuple[int, mavlink.MAVLink_message]):
        self.__queue.put(item)
    def messages(self) -> list[tuple[int, mavlink.MAVLink_message]]:
        """Get the history of messages."""
        return self.history
    def clear(self):
        """Clear the history of messages."""
        self.history.clear()
        self.__queue.queue.clear()
    def latest(self) -> Optional[tuple[int, mavlink.MAVLink_message]]:
        """Get the latest message from the history."""
        if self.history:
            return self.history[-1]
        return None