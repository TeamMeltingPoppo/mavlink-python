from .generated import mavlink
import struct
from pathlib import Path
from .subscriber import MAVLinkSubscriber
import threading

class MAVLinkRecorder:
    def __init__(self, file:Path,subscriber:MAVLinkSubscriber):
        """Set the file to write MAVLink messages to."""
        self.file = file
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.touch()
        self.subscriber=subscriber
    def __write_to_file(self, timestamp:int, msg:mavlink.MAVLink_message):
        """Write the timestamp and message to the file."""
        bytes_to_write = bytearray(struct.pack('>Q', timestamp)) + msg.get_msgbuf()
        if self.file:
            with open(self.file, 'ab') as f:
                f.write(bytes_to_write)
    def run(self,stop_event:threading.Event):
        while not stop_event.is_set():
            result=self.subscriber.get(0.01)
            if result is not None:
                self.__write_to_file(*result)