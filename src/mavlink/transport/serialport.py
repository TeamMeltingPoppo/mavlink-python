import serial
from mavlink.transport.base import TransportBase

class TransportSerial(TransportBase):
    def __init__(self,serialport:serial.Serial):
        self.serialport=serialport
    def recv(self, timeout):
        if self.serialport.in_waiting>0:
            return self.serialport.read_all()
        else:
            return None
    def send(self,data):
        self.serialport.write(data)
    def close(self):
        self.serialport.close()