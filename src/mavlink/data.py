from typing import Sequence,Optional
import struct
from pathlib import Path
from logging import getLogger
import time
import threading

from .generated import mavlink
from mavlink.subscriber_base import MAVLinkSubscriberBase
from .subscriber import MAVLinkSubscriber
from .history import MAVLinkHistory
from .status import MAVLinkStatus

class MAVLinkData:
    """A wrapper around the MAVLink class to handle subscriptions and message parsing."""
    def __init__(self):
        self.queues_msg_sys_comp : dict[tuple[int,int|None,int], set[MAVLinkSubscriberBase]] = {}
        self.queues_msg : dict[int, set[MAVLinkSubscriberBase]] = {}
        self.queues_comp : dict[int, set[MAVLinkSubscriberBase]] = {}
        self.mavlink_instance = mavlink.MAVLink(None)  # Initialize MAVLink instance without a file
        self.mavlink_instance.srcSystem = 1  # Set default system ID
        self.mavlink_instance.robust_parsing = True  # Enable robust parsing to handle malformed messages
        self.file : Optional[Path] = None  # Optional file for logging messages
        self.logger = getLogger(__name__)
        self._lock = threading.Lock()  # Lock for thread-safe operations
        self.status = MAVLinkStatus()  # Initialize a single MAVLinkStatus instance for tracking message status
    def __subscribe(self, subscriber:MAVLinkSubscriberBase):
        msgid = subscriber.msgid
        sysid = subscriber.sysid
        compid = subscriber.compid
        if (msgid is not None) and (compid is not None):
            if (msgid, sysid, compid) not in self.queues_msg_sys_comp:
                self.queues_msg_sys_comp[(msgid, sysid, compid)] = set()
            self.queues_msg_sys_comp[(msgid, sysid, compid)].add(subscriber)
        elif (msgid is not None):
            if msgid not in self.queues_msg:
                self.queues_msg[msgid] = set()
            self.queues_msg[msgid].add(subscriber)
        elif (compid is not None):
            if compid not in self.queues_comp:
                self.queues_comp[compid] = set()
            self.queues_comp[compid].add(subscriber)
        else:
            raise ValueError("At least one of msgid, sysid, or compid must be specified for subscription.")
    def subscribe(self, msgid:int, sysid:int=1, compid:int=None,maxsize:int=100) -> MAVLinkSubscriber:
        subscriber = MAVLinkSubscriber(msgid, sysid, compid,maxsize=maxsize)
        self.__subscribe(subscriber)
        return subscriber
    def subscribe_history(self, msgid:int, sysid:int=1, compid:int=None,duration:float=10.0,maxsize:int=1000) -> MAVLinkHistory:
        history_subscriber = MAVLinkHistory(msgid, sysid, compid,duration=duration,maxsize=maxsize)
        self.__subscribe(history_subscriber)
        return history_subscriber
    def unsubscribe(self, subscriber:MAVLinkSubscriberBase):
        key = (subscriber.msgid, subscriber.sysid, subscriber.compid)
        if key in self.queues_msg_sys_comp:
            self.queues_msg_sys_comp[key].discard(subscriber)
            if not self.queues_msg_sys_comp[key]:
                del self.queues_msg_sys_comp[key]
        if subscriber.msgid in self.queues_msg:
            self.queues_msg[subscriber.msgid].discard(subscriber)
            if not self.queues_msg[subscriber.msgid]:
                del self.queues_msg[subscriber.msgid]
        if subscriber.compid in self.queues_comp:
            self.queues_comp[subscriber.compid].discard(subscriber)
            if not self.queues_comp[subscriber.compid]:
                del self.queues_comp[subscriber.compid]
    def parse_bytes(self, data:Sequence[int],timestamp:int):
        try:
            msg_list = self.mavlink_instance.parse_buffer(data)
        except mavlink.MAVError as e:
            self.logger.error(f"Error parsing MAVLink message: {e}")
            msg_list = None
        if msg_list is None:
            msg_list = []
        for msg in msg_list:
            key = (msg.get_msgId(), msg.get_srcSystem(), msg.get_srcComponent())
            for subscriber in self.queues_msg_sys_comp.get(key, []):
                subscriber.queue.put((timestamp, msg))
            for subscriber in self.queues_msg.get(msg.get_msgId(), set()):
                subscriber.queue.put((timestamp, msg))
            for subscriber in self.queues_comp.get(msg.get_srcComponent(), set()):
                subscriber.queue.put((timestamp, msg))
            # Update the status for each observed message
            self.status.update(msg.get_msgId(), msg.get_srcSystem(), msg.get_srcComponent(), timestamp)
            self.__write_to_file(timestamp, msg)
    def __write_to_file(self, timestamp:int, msg:mavlink.MAVLink_message):
        """Write the timestamp and message to the file."""
        bytes_to_write = bytearray(struct.pack('>Q', timestamp)) + msg.get_msgbuf()
        if self.file:
            with open(self.file, 'ab') as f:
                f.write(bytes_to_write)
    def set_logfile(self, file:Path):
        """Set the file to write MAVLink messages to."""
        self.file = file
        self.logger.info(f"Set MAVLink log file to: {self.file}")
        # Ensure the directory exists
        self.file.parent.mkdir(parents=True, exist_ok=True)
        # Open the file in binary write mode
        self.logger.info(f"Creating/clearing the file: {self.file}")
        with open(self.file, 'wb') as f:
            pass  # Just to create/clear the file
    def get_status(self) -> MAVLinkStatus:
        """Create and return a new MAVLinkStatus instance."""
        return self.status