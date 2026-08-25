import threading

import serial

import mavlink
from mavlink import MAVLinkConnection
from mavlink.transport import TransportSerial

from logging import basicConfig, getLogger

def display_subscriber(
    subscriber: mavlink.MAVLinkSubscriber,
    stop_event: threading.Event,
):
    logger = getLogger("subscriber")
    while not stop_event.is_set():
        result = subscriber.get(timeout=0.01)
        if result:
            logger.info(f"Received message: {result.message}")

if __name__ == "__main__":

    from pathlib import Path
    from datetime import datetime

    basicConfig(level="DEBUG",format="%(asctime)s [%(levelname)s %(name)s] %(message)s")
    logger = getLogger()

    mavlink_topic = mavlink.MAVLinkTopic()

    filepath=Path(f"{datetime.now().strftime('logs/log_%Y%m%d_%H%M%S')}.tlog")
    # Record received MAVLink messages to a telemetry log.
    mavlink_topic.create_record(filepath=filepath)

    subscriber = mavlink_topic.create_subscriber(lambda msgid,sysid,compid :(sysid==1)and(compid==1))
    # subscribe HEARTBEAT messages
    # subscriber = mavlink_topic.create_subscriber(lambda msgid,sysid,compid :msgid==mavlink.definition.MAVLINK_MSG_ID_HEARTBEAT)

    serialport = serial.Serial(
        port="COM5",
        baudrate=115200,
        timeout=0.1,
    )
    
    transport=TransportSerial(serialport=serialport)

    connection=MAVLinkConnection(transport=transport,topic=mavlink_topic)

    stop_event = threading.Event()

    threads = [
        threading.Thread(
            target=connection.run_rx,
            args=(stop_event,),
            name="mavlink-polling",
        ),
        threading.Thread(
            target=connection.run_tx,
            args=(stop_event,),
            name="mavlink-polling",
        ),
        threading.Thread(
            target=display_subscriber,
            args=(subscriber, stop_event),
            name="mavlink-subscriber",
        )
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

        mavlink_topic.unsubscribe(subscriber)
        connection.close()