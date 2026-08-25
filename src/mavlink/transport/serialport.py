import serial
from mavlink.transport.base import TransportBase,Receiver,Sender

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
    def __init__(self,serialport:serial.Serial):
        self.serialport=serialport
    def get_receiver(self):
        return SerialReceiver(serialport=self.serialport)
    def get_sender(self):
        return SerialSender(serialport=self.serialport)
    def close(self):
        self.serialport.close()