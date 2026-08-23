from typing import Callable
from pathlib import Path
from logging import getLogger

from .generated import mavlink
from .subscriber_base import MAVLinkSubscriberBase
from .subscriber import MAVLinkSubscriber
from .history import MAVLinkHistory
from .recorder import MAVLinkRecorder
from .status import MAVLinkStatus

class MAVLinkStream:
    """A wrapper around the MAVLink class to handle subscriptions and message parsing."""
    def __init__(self):
        self.subscribers : set[MAVLinkSubscriberBase] = set()
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
    def record(self,filepath:Path)->MAVLinkRecorder:
        recorder = MAVLinkRecorder(filepath=filepath)
        self.subscribers.add(recorder)
        return recorder
    def unsubscribe(self, subscriber:MAVLinkSubscriberBase):
        self.subscribers.discard(subscriber)
    def publish(self,timestamp:int,msg:mavlink.MAVLink_message):
        self.status.update(msg.get_msgId(), msg.get_srcSystem(), msg.get_srcComponent(), timestamp)
        for subscriber in self.subscribers:
            subscriber.push((timestamp, msg))
    def get_status(self) -> MAVLinkStatus:
        """Create and return a new MAVLinkStatus instance."""
        return self.status