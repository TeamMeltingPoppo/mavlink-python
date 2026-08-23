import queue
from .generated import mavlink as definition

class MAVLinkPublisher:
    def __init__(self,sys_id:int,comp_id:int,writer_buffer:queue.Queue[bytes]):
        self.mav=definition.MAVLink(None,srcSystem=sys_id,srcComponent=comp_id)
        self.__writer_buffer:queue.Queue[bytes]=writer_buffer
    def publish(self,message:definition.MAVLink_message):
        self.__writer_buffer.put(message.pack(self.mav))