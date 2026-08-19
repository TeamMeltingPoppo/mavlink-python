import queue
from .generated import mavlink
from typing import Optional
from .subscriber_base import MAVLinkSubscriberBase

class MAVLinkSubscriber(MAVLinkSubscriberBase):
    """A subscriber that only keeps the latest message."""
    def __init__(self, msgid:int, sysid:int, compid:int,maxsize:int=100):
        super().__init__(msgid, sysid, compid,maxsize=maxsize)
        self.__latest_msg : Optional[tuple[float, mavlink.MAVLink_message]] = None
    def get(self,timeout:Optional[float]=None) -> Optional[tuple[float, mavlink.MAVLink_message]]:
        """Get the next message from the queue, or None if the queue is empty."""
        try:
            item = self.queue.get(timeout=timeout)
            self.__latest_msg = item
            return item
        except queue.Empty:
            return None
    def latest(self) -> Optional[tuple[float, mavlink.MAVLink_message]]:
        return self.__latest_msg