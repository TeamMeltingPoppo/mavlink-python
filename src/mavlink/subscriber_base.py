from .generated import mavlink
import abc
from typing import Callable

class MAVLinkSubscriberBase(abc.ABC):
    """A subscriber to MAVLink messages based on msgid, sysid, and compid."""
    def __init__(self, filter:Callable[[int,int,int],bool]):
        self.filter=filter
    def push(self,item:tuple[int, mavlink.MAVLink_message]):
        if self.filter(item[1].get_msgId(),item[1].get_srcSystem(),item[1].get_srcComponent()):
            self.__push__(item)
    @abc.abstractmethod
    def __push__(self,item:tuple[int, mavlink.MAVLink_message]):
        ...
