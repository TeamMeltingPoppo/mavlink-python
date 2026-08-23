from queue import Queue,Empty
from .generated import mavlink
from typing import Optional
from typing import Callable
from .subscriber_base import MAVLinkSubscriberBase

class MAVLinkSubscriber(MAVLinkSubscriberBase):
    """A subscriber that only keeps the latest message."""
    def __init__(self, filter:Callable[[int,int,int],bool],maxsize:int=10000):
        super().__init__(filter=filter)
        self.__latest_msg : Optional[tuple[float, mavlink.MAVLink_message]] = None
        self.__queue : Queue[tuple[float, mavlink.MAVLink_message]] = Queue(maxsize=maxsize)
    def __push__(self,item:tuple[int, mavlink.MAVLink_message]):
        self.__queue.put(item)
    def get(self,timeout:Optional[float]=None) -> Optional[tuple[float, mavlink.MAVLink_message]]:
        """Get the next message from the queue, or None if the queue is empty."""
        try:
            item = self.__queue.get(timeout=timeout)
            self.__latest_msg = item
            return item
        except Empty:
            return None
    def latest(self) -> Optional[tuple[float, mavlink.MAVLink_message]]:
        return self.__latest_msg