from abc import ABC,abstractmethod
from typing import Sequence

class Sender(ABC):
    @abstractmethod
    def send(self,data:Sequence[int]):
        ...

class Receiver(ABC):
    @abstractmethod
    def recv(self,timeout:float)->Sequence[int] | None:
        ...

class TransportBase(ABC):
    @abstractmethod
    def get_sender(self)->Sender | None:
        ...
    @abstractmethod
    def get_receiver(self)->Receiver | None:
        ...
    @abstractmethod
    def close(self):
        ...