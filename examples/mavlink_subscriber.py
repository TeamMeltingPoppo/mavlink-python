import time
import threading

import serial

import mavlink
from mavlink import MAVLinkData

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


def display_history(
    history: mavlink.MAVLinkHistory,
    status: mavlink.MAVLinkStatus,
    interval: float,
    stop_event: threading.Event,
):
    logger = getLogger("history")
    while not stop_event.wait(interval):
        history.sync(sync_timestamp=time.time())

        messages = history.messages()
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

        logger.info(
            f"Status snapshot: {snapshot}"
        )


if __name__ == "__main__":

    from pathlib import Path
    from datetime import datetime

    basicConfig(level="DEBUG",format="%(asctime)s [%(levelname)s %(name)s] %(message)s")
    logger = getLogger()

    mavlink_data = mavlink.MAVLinkData()

    # Record received MAVLink messages to a telemetry log.
    mavlink_data.set_logfile(Path(f"{datetime.now().strftime('logs/log_%Y%m%d_%H%M%S')}.tlog"))
    # Get the current MAVLink status for monitoring purposes.
    mavlink_status = mavlink_data.get_status()

    subscriber = mavlink_data.subscribe(
        msgid=None,
        compid=0,  # Subscribe to messages from component ID 0
    )

    history = mavlink_data.subscribe_history(
        msgid=None,
        compid=0,  # Subscribe to messages from component ID 0
        duration=10.0,
        maxsize=1000,
    )

    serial_port = serial.Serial(
        port="COM6",
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
            target=display_history,
            args=(history, mavlink_status, 1.0, stop_event),
            name="mavlink-history",
        ),
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
        mavlink_data.unsubscribe(history)

        serial_port.close()