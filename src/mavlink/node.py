from abc import ABC,abstractmethod
from logging import getLogger
from threading import Event
from mavlink.topic import MAVLinkTopic
from mavlink.generated.mavlink import MAVLink

class Node(ABC):
    """各Noneを表すMockクラス。MAVLink_message の送信と受信を行う"""
    def __init__(
        self,
        topic:MAVLinkTopic,
        name: str|None=None,
        sys_id: int=1,
        comp_id: int=1,
    ):
        self.sys_id = sys_id
        self.comp_id = comp_id
        self.topic = topic
        self.mav=MAVLink(None,srcSystem=sys_id,srcComponent=comp_id)
        if name == None:
            self.name = f"{sys_id=} {comp_id=}"
        else:
            self.name = name
        self.logger = getLogger(f"node({self.name})")
    @abstractmethod
    def setup(self):
        ...
    @abstractmethod
    def loop(self):
        ...

    def run(self, stop_event:Event):
        self.setup()
        while not stop_event.is_set():
            self.loop()