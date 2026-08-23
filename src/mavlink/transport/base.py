from abc import ABC,abstractmethod
from typing import Callable
from mavlink import MAVLinkPublisher,MAVLinkSubscriber

class Sender(ABC):
    @abstractmethod
    def get_publisher(self,sys_id:int,comp_id:int)->MAVLinkPublisher:
        ...

class Reciever(ABC):
    @abstractmethod
    def get_subscriber(self,filter:Callable[[int,int,int],bool],maxsize=1000)->MAVLinkSubscriber:
        ...