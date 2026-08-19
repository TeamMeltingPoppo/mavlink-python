from .generated import mavlink
from queue import Queue

class MAVLinkSubscriberBase:
    """A subscriber to MAVLink messages based on msgid, sysid, and compid."""
    def __init__(self, msgid:int, sysid:int, compid:int,maxsize:int=100):
        self.msgid = msgid
        self.sysid = sysid
        self.compid = compid
        self.queue : Queue[tuple[float, mavlink.MAVLink_message]] = Queue(maxsize=maxsize)
