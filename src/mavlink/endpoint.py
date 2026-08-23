import logging
from typing import Sequence,Optional,List
from .generated import mavlink as definition
from mavlink import MAVLinkStream

class MAVLinkEndpoint:
    def __init__(self,sys_id:int,comp_id:int):
        self.mav=definition.MAVLink(None,srcSystem=sys_id,srcComponent=comp_id)
        self.mav.robust_parsing=True
        self.logger=logging.getLogger(f"endpoint({sys_id=},{comp_id=})")
    def parse(self,buffer:Sequence[int])->Optional[List[definition.MAVLink_message]]:
        try:
            result = self.mav.parse_buffer(buffer)
        except definition.MAVError as e:
            self.logger.error(f"Error parsing MAVLink message: {e}")
            result = None
        return result
    def pack(self,message:definition.MAVLink_message)->bytes:
        return message.pack(self.mav)