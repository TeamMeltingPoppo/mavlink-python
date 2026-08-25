import time
import threading

import serial

from mavlink import MAVLinkTopic,MAVLinkBridge,MAVLinkHistory,MAVLinkStatus,definition
from mavlink.transport import TransportSerial

from logging import basicConfig, getLogger


def display_history(
    subscriber: MAVLinkHistory,
    status: MAVLinkStatus,
    interval: float,
    stop_event: threading.Event,
):
    logger = getLogger("history")
    while not stop_event.wait(interval):
        subscriber.sync(sync_timestamp=time.time_ns() // 1000)

        items = subscriber.items()
        snapshot = status.snapshot()

        if items:
            timestamps = [item.timestamp for item in items]
            logger.info(
                f"History messages "
                f"[{timestamps[0]} -> {timestamps[-1]}] "
                f"count: {len(items)}"
            )
        else:
            logger.info("No messages in history")
        logger.info("Status:")
        for (msgid,sysid,compid) in snapshot.observed_messages:
            if msgid not in definition.mavlink_map.keys():
                continue
            logger.info(f"\t{msgid=:4d}, {sysid=:2d}, {compid=:3d} : latest_timestamp={snapshot.last_received[(msgid,sysid,compid)]:17d} ({definition.mavlink_map[msgid].msgname})")

if __name__ == "__main__":

    basicConfig(level="DEBUG",format="%(asctime)s [%(levelname)s %(name)s] %(message)s")
    logger = getLogger()

    mavlink_topic = MAVLinkTopic()

    status = mavlink_topic.get_status()
    subscriber = mavlink_topic.create_history_subscriber(lambda msgid,sysid,compid :msgid==definition.MAVLINK_MSG_ID_HEARTBEAT,duration=5000_000)

    transport=TransportSerial(
        serialport=serial.Serial(port="COM5",baudrate=115200,timeout=0.1)
    )

    bridge=MAVLinkBridge(transport=transport,topic=mavlink_topic)

    stop_event = threading.Event()

    threads = [
        threading.Thread(
            target=bridge.run,
            args=(stop_event,),
            name="bridge-serialport",
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

        mavlink_topic.unsubscribe(subscriber)