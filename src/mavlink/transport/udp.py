from typing import Callable
import socket,struct,threading,time

import queue
from mavlink.data import MAVLinkData
from mavlink.subscriber import MAVLinkSubscriber
from mavlink.publisher import MAVLinkPublisher
from .base import Sender,Reciever

class SenderUDPMulticast(Sender):
    def __init__(
        self,
        multicast_group: str = "224.1.1.1",
        port: int = 14540,
        timeout: float = 0.1,
    ):
        self.multicast_group = multicast_group
        self.port = port

        # UDPソケットの作成
        self.sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )

        # ポート再利用の許可（同一PC上で複数プロセスを起動可能にする）
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", self.port))

        # マルチキャストグループへの参加設定
        mreq = struct.pack(
            "4sl", socket.inet_aton(self.multicast_group), socket.INADDR_ANY
        )
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # 送信オプション: TTL=2 (ネットワーク内到達) / LOOP=1 (自マシン上の別ノード受信可)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

        self.sock.settimeout(timeout)

        self.writer_queue:queue.Queue[bytes]=queue.Queue(-1)

    def get_publisher(self,sys_id:int,comp_id:int):
        return MAVLinkPublisher(sys_id=sys_id,comp_id=comp_id,writer_buffer=self.writer_queue)
    def close(self):
        self.sock.close()
    def run(self,stop_event:threading.Event):
        while not stop_event.is_set():
            try:
                payload_bytes=self.writer_queue.get(timeout=1.0)
                self.sock.sendto(payload_bytes, (self.multicast_group, self.port))
            except queue.Empty:
                pass

class RecieverUDPMulticast(Reciever):
    def __init__(
        self,
        multicast_group: str = "224.1.1.1",
        port: int = 14540,
        timeout: float = 0.1,
    ):
        self.multicast_group = multicast_group
        self.port = port

        # UDPソケットの作成
        self.sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )

        # ポート再利用の許可（同一PC上で複数プロセスを起動可能にする）
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", self.port))

        # マルチキャストグループへの参加設定
        mreq = struct.pack(
            "4sl", socket.inet_aton(self.multicast_group), socket.INADDR_ANY
        )
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # 送信オプション: TTL=2 (ネットワーク内到達) / LOOP=1 (自マシン上の別ノード受信可)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

        self.sock.settimeout(timeout)

        self.mavlink_data=MAVLinkData()
    def get_subscriber(self,filter:Callable[[int,int,int],bool],maxsize=1000)->MAVLinkSubscriber:
        return self.mavlink_data.subscribe(filter=filter,maxsize=maxsize)

    def __read(self, bufsize: int = 2048) -> bytes:
        try:
            data, _ = self.sock.recvfrom(bufsize)
            return data
        except TimeoutError:
            return b""

    def close(self):
        self.sock.close()

    def run(self,stop_event:threading.Event):
        while not stop_event.is_set():
            data = self.__read()
            if data:
                self.mavlink_data.parse_bytes(data, int(time.time_ns() // 1000))