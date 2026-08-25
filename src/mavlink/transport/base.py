from abc import ABC,abstractmethod
from typing import Sequence

class TransportBase(ABC):
    @abstractmethod
    def send(self,data:Sequence[int]):
        ...
    @abstractmethod
    def recv(self,timeout:float)->Sequence[int] | None:
        ...
    @abstractmethod
    def close(self):
        ...