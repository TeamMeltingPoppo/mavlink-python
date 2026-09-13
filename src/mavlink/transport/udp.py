import socket
from mavlink.core import TransportBase,Receiver,Sender

class UDPSender(Sender):
    """UDPで送信するためのSenderの実装"""
    def __init__(self,address:str,port:int):
        """UDPで送信するためのSenderの実装

        Args:
            address (str): 送信先のaddress
            port (int): 送信先のport
        """
        self.address=address
        self.port=port
        self.tx_sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    def send(self,data):
        self.tx_sock.sendto(data,(self.address,self.port))
    def close(self):
        self.tx_sock.close()

class UDPMulticastReceiver(Receiver):
    """UDP multicastで受信するためのReceiverの実装"""
    def __init__(
        self,
        multicast_group: str,
        port: int,
        interface: str | None = None,
    ):
        """UDP multicastで受信するためのReceiverの実装

        Args:
            multicast_group (str): 受信するaddress
            port (int): 受信するport
            interface (str | None, optional): multicast_groupに対応づけるaddress
        """
        self.multicast_group = multicast_group
        self.port = port

        self.rx_sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        )
        self.rx_sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )
        self.rx_sock.bind(("", port))

        interface = interface or "0.0.0.0"

        self.rx_sock.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_ADD_MEMBERSHIP,
            socket.inet_aton(multicast_group)
            + socket.inet_aton(interface),
        )
    def recv(self, timeout):
        self.rx_sock.settimeout(timeout)
        try:
            return self.rx_sock.recv(1024)
        except TimeoutError:
            return None
    def close(self):
        self.rx_sock.close()

class TransportUDPMulticast(TransportBase):
    """UDPで送受信を行うためのTransportの実装"""
    def __init__(self,sender:UDPSender|None,receiver:UDPMulticastReceiver|None):
        """UDPで送受信を行うためのTransportの実装

        Args:
            sender (UDPSender | None): UDPで送信を行うためのSenderのインスタンス。Noneが指定された場合は送信を行わない
            receiver (UDPMulticastReceiver | None): UDPで受信を行うためのReceiverのインスタンス。Noneの場合は受信を行わない。
        """
        self.sender=sender
        self.receiver=receiver
    def get_source_id(self):
        if self.receiver:
            return f"udp:{self.receiver.multicast_group}:{self.receiver.port}"
        else:
            return "udp:unknown"
    def get_sender(self):
        return self.sender
    def get_receiver(self):
        return self.receiver
    def close(self):
        if self.sender:
            self.sender.close()
        if self.receiver:
            self.receiver.close()