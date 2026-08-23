from typing import Sequence,Optional,Callable
import struct
from pathlib import Path
from logging import getLogger

from .generated import mavlink
from mavlink.subscriber_base import MAVLinkSubscriberBase
from .subscriber import MAVLinkSubscriber
from .history import MAVLinkHistory
from .status import MAVLinkStatus

class MAVLinkData:
    """A wrapper around the MAVLink class to handle subscriptions and message parsing."""
    def __init__(self):
        self.subscribers : set[MAVLinkSubscriberBase] = set()
        self.mavlink_instance = mavlink.MAVLink(None)  # Initialize MAVLink instance without a file
        self.mavlink_instance.srcSystem = 1  # Set default system ID
        self.mavlink_instance.robust_parsing = True  # Enable robust parsing to handle malformed messages
        self.file : Optional[Path] = None  # Optional file for logging messages
        self.logger = getLogger(__name__)
        self.status = MAVLinkStatus()  # Initialize a single MAVLinkStatus instance for tracking message status
    def subscribe(self, filter:Callable[[int,int,int],bool],maxsize:int=100) -> MAVLinkSubscriber:
        subscriber = MAVLinkSubscriber(filter,maxsize=maxsize)
        self.subscribers.add(subscriber)
        return subscriber
    def subscribe_history(self,filter:Callable[[int,int,int],bool],duration:int=1000_000,maxsize:int=1000) -> MAVLinkHistory:
        history_subscriber = MAVLinkHistory(filter,duration=duration,maxsize=maxsize)
        self.subscribers.add(history_subscriber)
        return history_subscriber
    def unsubscribe(self, subscriber:MAVLinkSubscriberBase):
        self.subscribers.discard(subscriber)
    def parse_bytes(self, data:Sequence[int],timestamp:int):
        try:
            msg_list = self.mavlink_instance.parse_buffer(data)
        except mavlink.MAVError as e:
            self.logger.error(f"Error parsing MAVLink message: {e}")
            msg_list = None
        if msg_list is None:
            msg_list = []
        for msg in msg_list:
            for subscriber in self.subscribers:
                subscriber.push((timestamp, msg))
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
        self.logger.debug(f"Set MAVLink log file to: {self.file}")
        # Ensure the directory exists
        self.file.parent.mkdir(parents=True, exist_ok=True)
        # Open the file in binary write mode
        self.logger.debug(f"Creating/clearing the file: {self.file}")
        with open(self.file, 'wb') as f:
            pass  # Just to create/clear the file
    def get_status(self) -> MAVLinkStatus:
        """Create and return a new MAVLinkStatus instance."""
        return self.status