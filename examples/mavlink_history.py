import time
import threading

import serial

import mavlink
from mavlink import MAVLinkData, definition

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

    mavlink_data = mavlink.MAVLinkData()

    # Record received MAVLink messages to a telemetry log.
    mavlink_data.set_logfile(Path(f"{datetime.now().strftime('logs/log_%Y%m%d_%H%M%S')}.tlog"))

    status = mavlink_data.get_status()
    subscriber = mavlink_data.subscribe_history(compid=1,duration=3000_000)

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