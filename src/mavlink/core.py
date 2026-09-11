import struct
from pathlib import Path
from typing import Callable,Optional
from pathlib import Path
from logging import getLogger
from dataclasses import dataclass
from queue import Queue,Empty
from collections import deque
import time

from threading import Lock,Event,Thread
import abc

import mavlink.definition as mavlink

from .transport.base import TransportBase

@dataclass(frozen=True)
class TopicItem:
    """A data class representing a MAVLink message with its timestamp and source ID."""
    timestamp: int
    message: mavlink.MAVLink_message
    source_id: str

class MAVLinkPublisher:
    """A publisher that sends MAVLink messages to a topic."""
    def __init__(self,topic:"MAVLinkTopic",source_id:str):
        self.topic=topic
        self.source_id=source_id
    def publish(self,timestamp: int,message: mavlink.MAVLink_message) -> None:
        """Publish a MAVLink message to the topic."""
        self.topic._publish(timestamp, message,self.source_id)

class MAVLinkSubscriberBase(abc.ABC):
    """A subscriber to MAVLink messages based on msgid, sysid, and compid."""
    def __init__(self, filter:Callable[[TopicItem],bool]):
        self.filter=filter
    def push(self,item:TopicItem):
        if self.filter(item):
            self.__push__(item)
    @abc.abstractmethod
    def __push__(self,item:TopicItem):
        ...

class MAVLinkSubscriber(MAVLinkSubscriberBase):
    """A subscriber that only keeps the latest message."""
    def __init__(self, filter:Callable[[TopicItem],bool],maxsize:int=10000):
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
    def __init__(self, filter:Callable[[TopicItem],bool],duration:int=1000_000,maxsize:int=10000):
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
    def __push__(self,item:TopicItem):
        self.__queue.put(item)
    def items(self) -> list[TopicItem]:
        """Get the history of messages."""
        return self.history
    def clear(self):
        """Clear the history of messages."""
        self.history.clear()
        self.__queue.queue.clear()
    def latest(self) -> Optional[TopicItem]:
        """Get the latest message from the history."""
        if self.history:
            return self.history[-1]
        return None

class MAVLinkRecorder(MAVLinkSubscriberBase):
    """A subscriber that records MAVLink messages to a file."""
    def __init__(self, filepath:Path):
        """Set the file to write MAVLink messages to."""
        super().__init__(lambda _item:True)
        self.file = filepath
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.touch()
        self.lock=Lock()
        self.parser=struct.Struct(">Q")
    def __push__(self, item):
        """Write the timestamp and message to the file."""
        bytes_to_write = bytearray(self.parser.pack(item.timestamp)) + item.message.get_msgbuf()
        with self.lock:
            if self.file:
                with open(self.file, 'ab') as f:
                    f.write(bytes_to_write)


class TLogReader():
    """A reader for TLog files that yields MAVLink messages with their timestamps."""
    def __init__(self,filepath:Path):
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

class MAVLinkBridge:
    """A bridge that connects a transport to a MAVLink topic."""
    def __init__(self,transport:TransportBase,topic:MAVLinkTopic,filter: Callable[[TopicItem], bool]|None=None):
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
        """Run the bridge, starting both the receive and transmit threads."""
        thread_rx=Thread(target=self._run_rx,args=(stop_event,),name="thread_rx")
        thread_tx=Thread(target=self._run_tx,args=(stop_event,),name="thread_tx")
        thread_rx.start()
        thread_tx.start()
        thread_rx.join()
        thread_tx.join()
        self.transport.close()

class MAVLinkTopic:
    """A wrapper around the MAVLink class to handle subscriptions and message parsing."""
    def __init__(self):
        self.subscribers : set[MAVLinkSubscriberBase] = set()
        self.lock : Lock = Lock()
        self.logger = getLogger(__name__)
        self.status = MAVLinkStatus()  # Initialize a single MAVLinkStatus instance for tracking message status
    def create_subscriber(self, filter:Callable[[TopicItem],bool],maxsize:int=100) -> MAVLinkSubscriber:
        """Create and return a new MAVLinkSubscriber instance."""
        subscriber = MAVLinkSubscriber(filter,maxsize=maxsize)
        with self.lock:
            self.subscribers.add(subscriber)
        return subscriber
    def create_history_subscriber(self,filter:Callable[[TopicItem],bool],duration:int=1000_000,maxsize:int=1000) -> MAVLinkHistory:
        """Create and return a new MAVLinkHistory instance."""
        history_subscriber = MAVLinkHistory(filter,duration=duration,maxsize=maxsize)
        with self.lock:
            self.subscribers.add(history_subscriber)
        return history_subscriber
    def create_record(self,filepath:Path)->MAVLinkRecorder:
        """Create and return a new MAVLinkRecorder instance."""
        recorder = MAVLinkRecorder(filepath=filepath)
        with self.lock:
            self.subscribers.add(recorder)
        return recorder
    def unsubscribe(self, subscriber:MAVLinkSubscriberBase):
        """Unsubscribe a subscriber from the topic."""
        with self.lock:
            self.subscribers.discard(subscriber)
    def _publish(self,timestamp:int,message:mavlink.MAVLink_message,source_id:str):
        self.status.update(message.get_msgId(), message.get_srcSystem(), message.get_srcComponent(), timestamp)
        with self.lock:
            for subscriber in self.subscribers:
                subscriber.push(TopicItem(timestamp=timestamp,message=message,source_id=source_id))
    def create_publisher(self, source_id:str) -> MAVLinkPublisher:
        """Create and return a new MAVLinkPublisher instance."""
        return MAVLinkPublisher(self, source_id=source_id)
    def get_status(self) -> MAVLinkStatus:
        """Create and return a new MAVLinkStatus instance."""
        return self.status