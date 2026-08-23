import time
import threading

import serial

import mavlink
from mavlink import MAVLinkStream, MAVLinkEndpoint

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

def display_history(
    subscriber: mavlink.MAVLinkHistory,
    status: mavlink.MAVLinkStatus,
    interval: float,
    stop_event: threading.Event,
):
    logger = getLogger("history")
    while not stop_event.wait(interval):
        subscriber.sync(sync_timestamp=time.time_ns() // 1000)

        messages = subscriber.messages()
        snapshot = status.snapshot()

        if messages:
            timestamps = [timestamp for timestamp, _ in messages]
            logger.info(
                f"History messages "
                f"[{timestamps[0]} -> {timestamps[-1]}] "
                f"count: {len(messages)}"
            )
        else:
            logger.info("No messages in history")
        logger.info("Status:")
        for (msgid,sysid,compid) in snapshot.observed_messages:
            if msgid not in mavlink.mavlink_map.keys():
                continue
            logger.info(f"\t{msgid=:4d}, {sysid=:2d}, {compid=:3d} : latest_timestamp={snapshot.last_received[(msgid,sysid,compid)]:17d} ({mavlink.mavlink_map[msgid].msgname})")

if __name__ == "__main__":

    from pathlib import Path
    from datetime import datetime

    basicConfig(level="DEBUG",format="%(asctime)s [%(levelname)s %(name)s] %(message)s")
    logger = getLogger()

    mavlink_data = mavlink.MAVLinkStream()

    status = mavlink_data.get_status()
    subscriber = mavlink_data.subscribe_history(lambda msgid,sysid,compid :compid==2,duration=3000_000)

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
            target=display_history,
            args=(subscriber,status,1.0,stop_event),
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