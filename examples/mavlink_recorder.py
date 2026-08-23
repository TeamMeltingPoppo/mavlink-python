import time
import threading

import serial

import mavlink
from mavlink import MAVLinkData, definition, MAVLinkRecorder

from logging import basicConfig, getLogger

def polling_thread(
    mavlink_data: MAVLinkData,
    serial_port: serial.Serial,
    stop_event: threading.Event,
):
    while not stop_event.is_set():
        if serial_port.in_waiting > 0:
            data = serial_port.read()
            if data:
                mavlink_data.parse_bytes(data, int(time.time_ns() // 1000))

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
        time.sleep(0.0001)  # Sleep briefly to avoid busy waiting

if __name__ == "__main__":

    from pathlib import Path
    from datetime import datetime

    basicConfig(level="DEBUG",format="%(asctime)s [%(levelname)s %(name)s] %(message)s")
    logger = getLogger()

    mavlink_data = mavlink.MAVLinkData()

    # subscribe messages which component_id = 1
    subscriber = mavlink_data.subscribe(lambda msgid,sysid,compid :compid==1)

    # subscribe all message for a recorder
    subscriber_all = mavlink_data.subscribe(lambda msgid,sysid,compid : True)
    filepath=Path(f"{datetime.now().strftime('logs/log_%Y%m%d_%H%M%S')}.tlog")
    # Record received MAVLink messages to a telemetry log.
    recorder=MAVLinkRecorder(filepath,subscriber_all)


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
        ),
        threading.Thread(
            target=recorder.run,
            args=(stop_event,),
            name="recorder"
        )
    ]

    try:
        for thread in threads:
            thread.start()

        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Exiting...")

    finally:
        stop_event.set()

        for thread in threads:
            thread.join()

        mavlink_data.unsubscribe(subscriber)

        serial_port.close()