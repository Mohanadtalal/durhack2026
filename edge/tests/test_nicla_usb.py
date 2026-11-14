import struct
import pytest
from edge.nicla_usb import NiclaUSB, NiclaProtocolError

JPEG = b"\xff\xd8" + b"x"*120 + b"\xff\xd9"

class SerialStub:
    def __init__(self, reply=b""):
        self.reply = reply
        self.writes = []
        self.closed = False
    def write(self, data):
        self.writes.append(data)
    def flush(self):
        pass
    def read(self, size):
        part = self.reply[:min(size, 7)]
        self.reply = self.reply[len(part):]
        return part
    def close(self):
        self.closed = True

def test_chunked_snapshot():
    stub = SerialStub(struct.pack("<L", len(JPEG)) + JPEG)
    assert NiclaUSB(stub).snapshot_jpeg() == JPEG
    assert stub.writes == [b"snap"]

def test_ping_and_warning():
    stub = SerialStub(b"PONG")
    client = NiclaUSB(stub)
    assert client.ping()
    client.set_warning(True)
    client.set_warning(True)
    client.set_warning(False)
    client.close()
    assert stub.writes == [b"ping", b"warn", b"safe", b"safe"]
    assert stub.closed

def test_bad_size_and_timeout():
    with pytest.raises(NiclaProtocolError):
        NiclaUSB(SerialStub(struct.pack("<L", 4))).snapshot_jpeg()
    with pytest.raises(NiclaProtocolError):
        NiclaUSB(SerialStub()).snapshot_jpeg()

def test_raw_frame_transfer():
    pixels = bytes(range(32))
    stub = SerialStub(struct.pack("<L", len(pixels)) + pixels)
    assert NiclaUSB(stub).snapshot_gray(width=8, height=4) == pixels
    assert stub.writes == [b"raw0"]

def test_raw_size_validation():
    stub = SerialStub(struct.pack("<L", 100))
    with pytest.raises(NiclaProtocolError, match="Unexpected raw frame size"):
        NiclaUSB(stub).snapshot_gray(width=8, height=4)
