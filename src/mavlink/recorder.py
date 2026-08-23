import struct
from pathlib import Path
from .subscriber_base import MAVLinkSubscriberBase
from threading import Lock

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
        timestamp,msg = item
        bytes_to_write = bytearray(struct.pack('>Q', timestamp)) + msg.get_msgbuf()
        with self.lock:
            if self.file:
                with open(self.file, 'ab') as f:
                    f.write(bytes_to_write)