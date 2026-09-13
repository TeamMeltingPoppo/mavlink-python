import struct
from pathlib import Path
from typing import Callable,Optional,Sequence
from pathlib import Path
from logging import getLogger
from dataclasses import dataclass
from queue import Queue,Empty
from collections import deque
import time

from threading import Lock,Event,Thread
import abc

import mavlink.definition as mavlink
@dataclass(frozen=True)
class TopicItem:
    """Topic内でやり取りされるデータ"""
    timestamp: int
    message: mavlink.MAVLink_message
    source_id: str

class MAVLinkPublisher:
    """TopicへMAVLink Messageを送信するPublisher"""
    def __init__(self,topic:"MAVLinkTopic",source_id:str):
        self.topic=topic
        self.source_id=source_id
    def publish(self,timestamp: int,message: mavlink.MAVLink_message) -> None:
        """Topicへメッセージをpublishする

        Args:
            timestamp (int): メッセージのtimestamp
            message (mavlink.MAVLink_message): 送信するメッセージ
        """
        self.topic._publish(timestamp, message,self.source_id)

class MAVLinkSubscriberBase(abc.ABC):
    # TopicからFilteringしてMAVLink Messageを受信するSubscriber基底class
    def __init__(self, filter:Callable[[TopicItem],bool]):
        self.filter=filter
    def push(self,item:TopicItem):
        if self.filter(item):
            self.__push__(item)
    @abc.abstractmethod
    def __push__(self,item:TopicItem):
        ...

class MAVLinkSubscriber(MAVLinkSubscriberBase):
    """TopicからMAVLink Messageを受信するSubscriber"""
    def __init__(self, filter:Callable[[TopicItem],bool],maxsize:int=10000):
        super().__init__(filter=filter)
        self.__queue : Queue[TopicItem] = Queue(maxsize=maxsize)
    def __push__(self,item:TopicItem):
        self.__queue.put(item)
    def get(self,timeout:Optional[float]=None) -> Optional[TopicItem]:
        """timeoutで指定した時間内でTopicからメッセージを受け取る

        Args:
            timeout (Optional[float], optional): Timeoutするまでの時間。 Defaults to None.

        Returns:
            Optional[TopicItem]: 受信したメッセージ。指定された時間内に受信できなければNoneが返される。
        """
        try:
            item = self.__queue.get(timeout=timeout)
            return item
        except Empty:
            return None

class MAVLinkHistory(MAVLinkSubscriberBase):
    """Topicから受信したMAVLink Messageの履歴を保持するSubscriber"""
    def __init__(self, filter:Callable[[TopicItem],bool],duration:int=1000_000,maxsize:int=None):
        super().__init__(filter=filter)
        self.__duration = duration
        self.__queue : Queue[TopicItem] = Queue(maxsize=maxsize)
        self.history : deque[TopicItem] = deque(maxlen=maxsize)
    def sync(self,sync_timestamp:Optional[int]=None):
        """MAVLink MessageのHistoryと最新のメッセージを更新する

        Args:
            sync_timestamp (Optional[int], optional): Historyが保持するメッセージの時刻の基準値。Noneを指定すると最新のメッセージのtimestampを基準とする。 Defaults to None.
        """
        while not self.__queue.empty():
            item = self.__queue.get()
            self.history.append(item)
        if len(self.history) == 0:
            return
        if sync_timestamp is None:
            sync_timestamp = self.history[-1].timestamp if self.history else 0.0
        while self.history and (sync_timestamp - self.history[0].timestamp) > self.__duration:
            self.history.popleft()
    def __push__(self,item:TopicItem):
        self.__queue.put(item)
    def items(self) -> list[TopicItem]:
        """保持しているHistoryを取得する

        Returns:
            list[TopicItem]: 保持しているHistory
        """
        return self.history
    def clear(self):
        """Historyをclearする"""
        self.history.clear()
        self.__queue.queue.clear()
    def latest(self) -> Optional[TopicItem]:
        """保持している最新のメッセージを取得する

        Returns:
            Optional[TopicItem]: 保持している最新のメッセージ。何もメッセージを受け取っていなければNoneを返す。
        """
        if self.history:
            return self.history[-1]
        return None

class MAVLinkRecorder(MAVLinkSubscriberBase):
    """受信したMAVLinkMessageをTlog形式でfileに保存するSubscriber"""
    def __init__(self, filepath:Path):
        super().__init__(lambda _item:True)
        self.file = filepath
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.touch()
        self.lock=Lock()
        self.parser=struct.Struct(">Q")
    def __push__(self, item):
        # Write the timestamp and message to the file.
        bytes_to_write = bytearray(self.parser.pack(item.timestamp)) + item.message.get_msgbuf()
        with self.lock:
            if self.file:
                with open(self.file, 'ab') as f:
                    f.write(bytes_to_write)


class TLogReader():
    """TLog形式で保存されたfileを読み込むReader

    Example:
        ```python
        reader=TLogReader(Path("sample.tlog")) # sample.tlogを読み込む
        for (timestamp,message) in reader:
            print(f"{timestamp=},{message=}") # Iteratorでtimestampとmessageを取り出す
        ```
    """
    def __init__(self,filepath:Path):
        """TLog形式で保存されたfileを読み込むReader

        Args:
            filepath (Path): 読み込むfileへのpath
        """
        with filepath.open("rb") as f:
            self.buffer=f.read()
        self.idx=0
        self.mav=mavlink.MAVLink(None)
        self.parser=struct.Struct(">Q")
    def __iter__(self):
        return self
    def __next__(self):
        while (self.idx+20) < len(self.buffer):
            # MAVLinkのwire format : https://mavlink.io/en/guide/serialization.html
            idx_msg=self.idx+8
            if self.buffer[idx_msg]==0xFD: # STX
                payload_length=self.buffer[idx_msg+1]
                if len(self.buffer) < (idx_msg+payload_length+12):
                    break
                try:
                    msg=self.mav.parse_char(self.buffer[idx_msg:idx_msg+payload_length+12])
                except mavlink.MAVError:
                    self.idx+=1
                    continue
                if msg:
                    timestamp:int=self.parser.unpack(self.buffer[self.idx:self.idx+8])[0]
                    self.idx=idx_msg+12+payload_length
                    return timestamp,msg
            self.idx+=1
        raise StopIteration

@dataclass(frozen=True)
class MAVLinkStatusSnapshot:
    """A snapshot of the current status of observed MAVLink messages."""
    observed_messages: frozenset[tuple[int, int, int]]
    last_received: dict[tuple[int, int, int], int]

class MAVLinkStatus:
    """MAVLinkTopicの受信状況を取得するためのclass"""
    def __init__(self):
        self.observed_messages: set[tuple[int, int, int]] = set()
        self.last_received: dict[tuple[int, int, int], int] = {}
        self._lock = Lock()  # Lock for thread-safe operations
    def update(self, msgid: int, sysid: int, compid: int, timestamp: int):
        with self._lock:
            self.observed_messages.add((msgid, sysid, compid))
            self.last_received[(msgid, sysid, compid)] = timestamp
    def snapshot(self) -> MAVLinkStatusSnapshot:
        """現在の受信状況を取得する

        Returns:
            MAVLinkStatusSnapshot: 現在の受信状況のsnapshot
        """
        with self._lock:
            return MAVLinkStatusSnapshot(
                observed_messages=frozenset(self.observed_messages),
                last_received=self.last_received.copy()
            )

class Sender(abc.ABC):
    """Transportで送信を行う基底class"""
    @abc.abstractmethod
    def send(self,data:Sequence[int]):
        """バイト列の送信を行う

        Args:
            data (Sequence[int]): 送信するバイト列
        """
        ...

class Receiver(abc.ABC):
    """Transportで受信を行う基底class"""
    @abc.abstractmethod
    def recv(self,timeout:float)->Sequence[int] | None:
        """バイト列を受信する

        Args:
            timeout (float): 受信でtimeoutするまでの時間。単位はs

        Returns:
            Sequence[int] | None: 受信したバイト列。何も受信しなかった場合はNoneを返す
        """
        ...
class TransportBase(abc.ABC):
    """Transport実装の基底class"""
    @abc.abstractmethod
    def get_source_id(self)->str:
        """Publisherの送信元を判別するためのIDを返す

        Returns:
            str: 送信元を判別するためのID
        """
        ...
    @abc.abstractmethod
    def get_sender(self)->Sender | None:
        """Senderを返す

        Returns:
            Sender | None: Senderが存在しなければNoneを返す
        """
        ...
    @abc.abstractmethod
    def get_receiver(self)->Receiver | None:
        """Receiverを返す

        Returns:
            Receiver | None: Receiverが存在しなければNoneを返す
        """
        ...
    @abc.abstractmethod
    def close(self):
        """通信の終了処理を行う
        """
        ...
class MAVLinkBridge:
    """TransportをTopicへ結びつけるためのBridge"""
    def __init__(self,transport:TransportBase,topic:MAVLinkTopic,filter: Callable[[TopicItem], bool]|None=None):
        """TransportをTopicへ結びつけるためのBridge

        Args:
            transport (TransportBase): BindするTransport
            topic (MAVLinkTopic): BindされるTopic
            filter (Callable[[TopicItem], bool] | None, optional): メッセージを受け取るかを判別する関数。Trueを返すと受け取る
        """
        self.transport=transport
        self.reciever=transport.get_receiver()
        self.sender=transport.get_sender()
        self.filter=filter
        self.topic=topic
        self.mav=mavlink.MAVLink(None)
        self.mav.robust_parsing=True

    def _run_rx(self,stop_event:Event):
        if not self.reciever:
            return
        publisher=self.topic.create_publisher(self.transport.get_source_id())
        while not stop_event.is_set():
            buffer=self.reciever.recv(timeout=0.1)
            if buffer is None:
                continue
            timestamp=time.time_ns() // 1000
            messages=self.mav.parse_buffer(buffer)
            if messages is None:
                continue
            for message in messages:
                publisher.publish(timestamp=timestamp,message=message)

    def _run_tx(self, stop_event:Event):
        if not self.sender:
            return
        subscriber=self.topic.create_subscriber(filter=self.filter or (lambda item: True))
        while not stop_event.is_set():
            item = subscriber.get(timeout=0.1)
            if item is None:
                continue
            if item.source_id==self.transport.get_source_id():
                continue
            self.sender.send(item.message.get_msgbuf())
        self.topic.unsubscribe(subscriber)

    def run(self,stop_event:Event):
        """Bridgeを実行する。stop_eventがsetされると終了する。

        Args:
            stop_event (Event): 実行を終了させるためのEvent
        """
        thread_rx=Thread(target=self._run_rx,args=(stop_event,),name="thread_rx")
        thread_tx=Thread(target=self._run_tx,args=(stop_event,),name="thread_tx")
        thread_rx.start()
        thread_tx.start()
        thread_rx.join()
        thread_tx.join()
        self.transport.close()

class MAVLinkTopic:
    """MAVLink Messageの送受信を媒介するTopic"""
    def __init__(self):
        """MAVLink Messageの送受信を媒介するTopic
        """
        self.subscribers : set[MAVLinkSubscriberBase] = set()
        self.lock : Lock = Lock()
        self.logger = getLogger(__name__)
        self.status = MAVLinkStatus()  # Initialize a single MAVLinkStatus instance for tracking message status
    def create_subscriber(self, filter:Callable[[TopicItem],bool],maxsize:int=100) -> MAVLinkSubscriber:
        """Subscriberのインスタンスを作成する

        Args:
            filter (Callable[[TopicItem],bool]): メッセージを受け取るかを判別する関数。Trueを返すと受け取る
            maxsize (int, optional): 内部的に用いるqueueのサイズ

        Returns:
            MAVLinkSubscriber
        """
        subscriber = MAVLinkSubscriber(filter,maxsize=maxsize)
        with self.lock:
            self.subscribers.add(subscriber)
        return subscriber
    def create_history_subscriber(self,filter:Callable[[TopicItem],bool],duration:int=1000_000,maxsize:int=1000) -> MAVLinkHistory:
        """MAVLinkHistorySubscriberのインスタンスを作成する

        Args:
            filter (Callable[[TopicItem],bool]): メッセージを受け取るかを判別する関数。Trueを返すと受け取る
            duration (int, optional): Historyで保持するMessageの時間幅。単位はus
            maxsize (int, optional): Historyの内部的に用いるdequeの長さ

        Returns:
            MAVLinkHistory
        """
        history_subscriber = MAVLinkHistory(filter,duration=duration,maxsize=maxsize)
        with self.lock:
            self.subscribers.add(history_subscriber)
        return history_subscriber
    def create_record(self,filepath:Path)->MAVLinkRecorder:
        """MAVLinkRecorderのインスタンスを作成する

        Args:
            filepath (Path): 保存先のfileへのpath

        Returns:
            MAVLinkRecorder
        """
        recorder = MAVLinkRecorder(filepath=filepath)
        with self.lock:
            self.subscribers.add(recorder)
        return recorder
    def unsubscribe(self, subscriber:MAVLinkSubscriberBase):
        """Subscriberの登録を解除する

        Args:
            subscriber (MAVLinkSubscriberBase): 登録を解除するSubscriber
        """
        with self.lock:
            self.subscribers.discard(subscriber)
    def _publish(self,timestamp:int,message:mavlink.MAVLink_message,source_id:str):
        self.status.update(message.get_msgId(), message.get_srcSystem(), message.get_srcComponent(), timestamp)
        with self.lock:
            for subscriber in self.subscribers:
                subscriber.push(TopicItem(timestamp=timestamp,message=message,source_id=source_id))
    def create_publisher(self, source_id:str) -> MAVLinkPublisher:
        """MAVLinkPublisherのインスタンスを作成する

        Args:
            source_id (str): 送信元を判別するためのID

        Returns:
            MAVLinkPublisher
        """
        return MAVLinkPublisher(self, source_id=source_id)
    def get_status(self) -> MAVLinkStatus:
        """MAVLinkStatusのインスタンスを作成する

        Returns:
            MAVLinkStatus
        """
        return self.status