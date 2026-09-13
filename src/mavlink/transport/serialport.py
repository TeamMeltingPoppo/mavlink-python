import serial
from mavlink.core import TransportBase,Receiver,Sender

class SerialSender(Sender):
    def __init__(self,serialport:serial.Serial):
        self.serialport=serialport
    def send(self, data):
        self.serialport.write(data)

class SerialReceiver(Receiver):
    def __init__(self,serialport:serial.Serial):
        self.serialport=serialport
    def recv(self, timeout):
        if self.serialport.in_waiting>0:
            return self.serialport.read_all()
        else:
            return None

class TransportSerial(TransportBase):
    """Serial portに対応するTransportの実装"""
    def __init__(self,serialport:serial.Serial):
        """Serial portに対応するTransportの実装

        Args:
            serialport (serial.Serial): TopicにbindするSerial
        """
        self.serialport=serialport
    def get_source_id(self):
        return f"serial:{self.serialport.port}"
    def get_receiver(self):
        return SerialReceiver(serialport=self.serialport)
    def get_sender(self):
        return SerialSender(serialport=self.serialport)
    def close(self):
        self.serialport.close()