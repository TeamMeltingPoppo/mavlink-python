import socket
from mavlink.transport.base import TransportBase,Receiver,Sender

class UDPSender(Sender):
    def __init__(self,address:str,port:int):
        self.address=address
        self.port=port
        self.tx_sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    def send(self,data):
        self.tx_sock.sendto(data,(self.address,self.port))
    def close(self):
        self.tx_sock.close()

class UDPMulticastReceiver(Receiver):
    def __init__(self,multicast_group:str,port:int):
        self.multicast_group=multicast_group
        self.port=port
        local_address   = socket.gethostbyname(socket.gethostname())

        self.rx_sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rx_sock.bind(('', port))
        self.rx_sock.setsockopt(socket.IPPROTO_IP,
            socket.IP_ADD_MEMBERSHIP,
            socket.inet_aton(multicast_group) + socket.inet_aton(local_address))
    def recv(self, timeout):
        self.rx_sock.settimeout(timeout)
        try:
            return self.rx_sock.recv(1024)
        except TimeoutError:
            return None
    def close(self):
        self.rx_sock.close()

class TransportUDPMulticast(TransportBase):
    def __init__(self,sender:UDPSender|None,receiver:UDPMulticastReceiver|None):
        self.sender=sender
        self.receiver=receiver
    def get_sender(self):
        return self.sender
    def get_receiver(self):
        return self.receiver
    def close(self):
        if self.sender:
            self.sender.close()
        if self.receiver:
            self.receiver.close()