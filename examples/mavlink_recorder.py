import time
import threading

import serial

import mavlink
from mavlink import MAVLinkStream, definition, MAVLinkRecorder, MAVLinkEndpoint

from logging import basicConfig, getLogger

def polling_thread(
    mavlink_stream: MAVLinkStream,
    serial_port: serial.Serial,
    stop_event: threading.Event,
):
    endpoint=MAVLinkEndpoint(1,1)
    while not stop_event.is_set():
        if serial_port.in_waiting > 0:
            data = serial_port.read()
            if data:
                msg_list=endpoint.parse(data)
                if msg_list is not None:
                    for msg in msg_list:
                        mavlink_stream.publish(time.time_ns()//1000,msg)

def display_subscriber(
    subscriber: mavlink.MAVLinkSubscriber,
    stop_event: threading.Event,
):
    logger = getLogger("subscriber")
    while not stop_event.is_set():
        result = subscriber.get(timeout=0.0)

        if result:
            timestamp, message = result
            logger.info(f"Received message: {message}")
        time.sleep(0.001)  # Sleep briefly to avoid busy waiting

if __name__ == "__main__":

    from pathlib import Path
    from datetime import datetime

    basicConfig(level="DEBUG",format="%(asctime)s [%(levelname)s %(name)s] %(message)s")
    logger = getLogger()

    mavlink_data = mavlink.MAVLinkStream()

    # subscribe messages which component_id = 1
    subscriber = mavlink_data.subscribe(lambda msgid,sysid,compid :compid==1)

    filepath=Path(f"{datetime.now().strftime('logs/log_%Y%m%d_%H%M%S')}.tlog")
    # Record received MAVLink messages to a telemetry log.
    mavlink_data.record(filepath=filepath)


    serial_port = serial.Serial(
        port="COM5",
        baudrate=115200,
        timeout=0.1,
    )

    stop_event = threading.Event()

    threads = [
        threading.Thread(
            target=polling_thread,
            args=(mavlink_data, serial_port, stop_event),
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

        mavlink_data.unsubscribe(subscriber)

        serial_port.close()