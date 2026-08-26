from pathlib import Path
from mavlink import TLogReader,MAVLinkTopic,MAVLinkPublisher,MAVLinkSubscriber,definition
import threading
import time
from logging import getLogger,basicConfig

def replay_log(
    publisher:MAVLinkPublisher,
    stop_event: threading.Event,
    start_timestamp:int=1787699674980000,
):
    logger=getLogger("reader")
    reader=TLogReader(Path("examples/sample.tlog"))
    prev_timestamp=start_timestamp
    for timestamp,message in reader:
        if stop_event.is_set():
            return
        publisher.publish(timestamp=timestamp,message=message,source=reader)
        time.sleep((timestamp - prev_timestamp)/1e6)
        prev_timestamp=timestamp
    logger.info("finished")

def display_subscriber(
    subscriber: MAVLinkSubscriber,
    stop_event: threading.Event,
):
    logger = getLogger("subscriber")
    while not stop_event.is_set():
        result = subscriber.get(timeout=0.01)
        if result:
            logger.info(f"[timestamp={result.timestamp}] {result.message}")

if __name__=="__main__":
    basicConfig(level="DEBUG",format="%(asctime)s [%(levelname)s %(name)s] %(message)s")
    logger=getLogger()

    topic=MAVLinkTopic()
    subscriber=topic.create_subscriber(lambda msgid,sysid,compid:(msgid==definition.MAVLINK_MSG_ID_GPS_RAW_INT)and(sysid==1)and(compid==1), 10000)
    publisher=topic.create_publisher()

    stop_event = threading.Event()

    threads = [
        threading.Thread(
            target=replay_log,
            args=(publisher,stop_event,),
            name="log to topic",
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
