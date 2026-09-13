from abc import ABC,abstractmethod
from logging import getLogger
from threading import Event
from mavlink.core import MAVLinkTopic
from mavlink.definition import MAVLink

class Node(ABC):
    """各Noneを表すMockクラス。MAVLink_message の送信と受信を行う"""
    def __init__(
        self,
        topic:MAVLinkTopic,
        name: str|None=None,
        sys_id: int=1,
        comp_id: int=1,
    ):
        """_summary_

        Args:
            topic (MAVLinkTopic): 送受信を行う先のTopic
            name (str | None, optional): Nodeの名前
            sys_id (int, optional): NodeのSystem ID
            comp_id (int, optional): NodeのComponent ID
        """
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
        """Arduinoでいうvoid setup()に相当する処理を行う
        """
        ...
    @abstractmethod
    def loop(self):
        """Arduinoでいうvoid loop()に相当する処理を行う
        """
        ...

    def run(self, stop_event:Event):
        """Nodeで行う処理を実行する。stop_eventがsetされると終了する。

        Args:
            stop_event (Event): 実行を終了させるためのEvent
        """
        self.setup()
        while not stop_event.is_set():
            self.loop()