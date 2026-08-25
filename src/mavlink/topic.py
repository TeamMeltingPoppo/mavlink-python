import struct
from pathlib import Path
from typing import Callable,Optional
from pathlib import Path
from logging import getLogger
from dataclasses import dataclass
from queue import Queue,Empty
from collections import deque
import time

from threading import Lock,Event
import abc

from .generated import mavlink

from .transport.base import TransportBase

@dataclass
class TopicItem:
    timestamp: int
    message: mavlink.MAVLink_message
    source: object

class MAVLinkPublisher:
    def __init__(self,topic:"MAVLinkTopic"):
        self.topic=topic
    def publish(self,timestamp: int,message: mavlink.MAVLink_message) -> None:
        self.topic.publish(timestamp, message)

class MAVLinkSubscriberBase(abc.ABC):
    """A subscriber to MAVLink messages based on msgid, sysid, and compid."""
    def __init__(self, filter:Callable[[int,int,int],bool]):
        self.filter=filter
    def push(self,item:TopicItem):
        if self.filter(item.message.get_msgId(),item.message.get_srcSystem(),item.message.get_srcComponent()):
            self.__push__(item)
    @abc.abstractmethod
    def __push__(self,item:TopicItem):
        ...

class MAVLinkSubscriber(MAVLinkSubscriberBase):
    """A subscriber that only keeps the latest message."""
    def __init__(self, filter:Callable[[int,int,int],bool],maxsize:int=10000):
        super().__init__(filter=filter)
        self.__latest_msg : Optional[TopicItem] = None
        self.__queue : Queue[TopicItem] = Queue(maxsize=maxsize)
    def __push__(self,item:TopicItem):
        self.__queue.put(item)
    def get(self,timeout:Optional[float]=None) -> Optional[TopicItem]:
        """Get the next message from the queue, or None if the queue is empty."""
        try:
            item = self.__queue.get(timeout=timeout)
            self.__latest_msg = item
            return item
        except Empty:
            return None
    def latest(self) -> Optional[TopicItem]:
        return self.__latest_msg

class MAVLinkHistory(MAVLinkSubscriberBase):
    """A subscriber that keeps a history of messages."""
    def __init__(self, filter:Callable[[int,int,int],bool],duration:int=1000_000,maxsize:int=10000):
        super().__init__(filter=filter)
        self.__duration = duration
        self.__queue : Queue[TopicItem] = Queue(maxsize=maxsize)
        self.history : deque[TopicItem] = deque(maxlen=maxsize)
    def sync(self,sync_timestamp:Optional[int]=None):
        """Update the history with the latest message."""
        while not self.__queue.empty():
            item = self.__queue.get()
            self.history.append(item)
        if len(self.history) == 0:
            return
        if sync_timestamp is None:
            sync_timestamp = self.history[-1].timestamp if self.history else 0.0
        while self.history and (sync_timestamp - self.history[0].timestamp) > self.__duration:
            self.history.popleft()
    def __push__(self,item:tuple[int, mavlink.MAVLink_message]):
        self.__queue.put(item)
    def items(self) -> list[TopicItem]:
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

class MAVLinkRecorder(MAVLinkSubscriberBase):
    def __init__(self, filepath:Path):
        """Set the file to write MAVLink messages to."""
        super().__init__(lambda _msg,_sys,_comp:True)
        self.file = filepath
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.touch()
        self.lock=Lock()
    def __push__(self, item):
        """Write the timestamp and message to the file."""
        bytes_to_write = bytearray(struct.pack('>Q', item.timestamp)) + item.message.get_msgbuf()
        with self.lock:
            if self.file:
                with open(self.file, 'ab') as f:
                    f.write(bytes_to_write)

@dataclass(frozen=True)
class MAVLinkStatusSnapshot:
    observed_messages: frozenset[tuple[int, int, int]]
    last_received: dict[tuple[int, int, int], int]

class MAVLinkStatus:
    """A subscriber to MAVLink messages based on msgid, sysid, and compid."""
    def __init__(self):
        self.observed_messages: set[tuple[int, int, int]] = set()
        self.last_received: dict[tuple[int, int, int], int] = {}
        self._lock = Lock()  # Lock for thread-safe operations
    def update(self, msgid: int, sysid: int, compid: int, timestamp: int):
        """Update the status with a new message."""
        with self._lock:
            self.observed_messages.add((msgid, sysid, compid))
            self.last_received[(msgid, sysid, compid)] = timestamp
    def snapshot(self) -> MAVLinkStatusSnapshot:
        """Get a snapshot of the current status."""
        with self._lock:
            return MAVLinkStatusSnapshot(
                observed_messages=frozenset(self.observed_messages),
                last_received=self.last_received.copy()
            )

class MAVLinkConnection:
    def __init__(self,transport:TransportBase,topic:MAVLinkTopic,filter: Callable[[int, int, int], bool]|None=None):
        self.transport=transport
        self.topic=topic
        self.mav=mavlink.MAVLink(None)
        self.mav.robust_parsing=True
        self.subscriber=self.topic.create_subscriber(filter=filter or (lambda msgid, sysid, compid: True))

    def run_rx(self,stop_event:Event):
        while not stop_event.is_set():
            buffer=self.transport.recv(timeout=0.1)
            if buffer is None:
                continue
            timestamp=time.time_ns() // 1000
            messages=self.mav.parse_buffer(buffer)
            if messages is None:
                continue
            for message in messages:
                self.topic.publish(timestamp=timestamp,message=message,source=self)

    def run_tx(self, stop_event):
        while not stop_event.is_set():
            item = self.subscriber.get(timeout=0.1)
            if item is None:
                continue
            if item.source==self:
                continue
            self.transport.send(item.message.get_msgbuf())

    def close(self):
        self.topic.unsubscribe(self.subscriber)
        self.transport.close()

class MAVLinkTopic:
    """A wrapper around the MAVLink class to handle subscriptions and message parsing."""
    def __init__(self):
        self.subscribers : set[MAVLinkSubscriberBase] = set()
        self.logger = getLogger(__name__)
        self.status = MAVLinkStatus()  # Initialize a single MAVLinkStatus instance for tracking message status
    def create_subscriber(self, filter:Callable[[int,int,int],bool],maxsize:int=100) -> MAVLinkSubscriber:
        subscriber = MAVLinkSubscriber(filter,maxsize=maxsize)
        self.subscribers.add(subscriber)
        return subscriber
    def create_history_subscriber(self,filter:Callable[[int,int,int],bool],duration:int=1000_000,maxsize:int=1000) -> MAVLinkHistory:
        history_subscriber = MAVLinkHistory(filter,duration=duration,maxsize=maxsize)
        self.subscribers.add(history_subscriber)
        return history_subscriber
    def create_record(self,filepath:Path)->MAVLinkRecorder:
        recorder = MAVLinkRecorder(filepath=filepath)
        self.subscribers.add(recorder)
        return recorder
    def unsubscribe(self, subscriber:MAVLinkSubscriberBase):
        self.subscribers.discard(subscriber)
    def publish(self,timestamp:int,message:mavlink.MAVLink_message,source:object=None):
        self.status.update(message.get_msgId(), message.get_srcSystem(), message.get_srcComponent(), timestamp)
        for subscriber in self.subscribers:
            subscriber.push(TopicItem(timestamp=timestamp,message=message,source=source))
    def create_publisher(self):
        return MAVLinkPublisher(self)
    def get_status(self) -> MAVLinkStatus:
        """Create and return a new MAVLinkStatus instance."""
        return self.status