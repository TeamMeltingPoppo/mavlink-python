import time
import threading
import logging
import serial

import mavlink
from mavlink import MAVLinkTopic,Node
from mavlink.transport.udp import TransportUDPMulticast,UDPSender
from mavlink.transport.serialport import TransportSerial

class MockNode(Node):
    def __init__(self,topic:MAVLinkTopic):
        super().__init__(topic=topic,name="Node1",sys_id=255,comp_id=3)
    def setup(self):
        self.subscriber=self.topic.create_subscriber(lambda msgid,sysid,compid:True)
        self.publisher=self.topic.create_publisher()
        self.last_send_heartbeat=time.time()
        self.logger.info("This is Monitor")
    def loop(self):
        for _ in range(1000):
            result = self.subscriber.get(0.01)
            if result:
                if result.source!=self:
                    msg=result.message
                    self.logger.info(f"(sysid:{msg.get_srcSystem()},compid:{msg.get_srcComponent()}) --(msgId:{msg.get_msgId():3d})-> (sysid:{self.sys_id},compid:{self.comp_id})")
            else:
                break
        if (time.time() - self.last_send_heartbeat) >= 1.0:
            heartbeat=mavlink.definition.MAVLink_heartbeat_message(
                type=mavlink.definition.MAV_TYPE_GENERIC,
                autopilot=mavlink.definition.MAV_AUTOPILOT_GENERIC,
                base_mode=mavlink.definition.MAV_MODE_PREFLIGHT,
                custom_mode=0,
                system_status=mavlink.definition.MAV_STATE_ACTIVE,
                mavlink_version=3
            )
            heartbeat.pack(self.mav)
            self.topic.publish(timestamp=time.time_ns()//1000,message=heartbeat,source=self)
            self.last_send_heartbeat=time.time()


if __name__=="__main__":    
    logging.basicConfig(level="DEBUG",format="%(asctime)s [%(levelname)s %(name)s] %(message)s")
    logger = logging.getLogger()

    mavlink_topic = MAVLinkTopic()

    transport_udp   =TransportUDPMulticast(sender=UDPSender('239.255.0.1',14550),receiver=None)
    transport_serial=TransportSerial(serialport=serial.Serial(port="COM5",baudrate=115200,timeout=0.1))
    connection_udp   =mavlink.MAVLinkConnection(transport=transport_udp   ,topic=mavlink_topic)
    connection_serial=mavlink.MAVLinkConnection(transport=transport_serial,topic=mavlink_topic)

    stop_event = threading.Event()

    node=MockNode(topic=mavlink_topic)

    threads = [
        threading.Thread(target=connection_udp.run,args=(stop_event,),name="connection-udp"),
        threading.Thread(target=connection_serial.run,args=(stop_event,),name="connection-serialport"),
        threading.Thread(target=node.run,args=(stop_event,),name=f"node({node.name})")
    ]
    
    try:
        for thread in threads:
            thread.start()

        input()

    finally:
        logger.info("Exiting...")

        stop_event.set()

        for thread in threads:
            thread.join()