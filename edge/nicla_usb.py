"""Nicla USB Virtual COM bridge. Laptop requests 4-byte commands."""
import struct

MAX_JPEG_BYTES = 1_000_000

class NiclaProtocolError(RuntimeError):
    pass

class NiclaUSB:
    def __init__(self, transport):
        self.transport = transport
        self._warning = None

    @classmethod
    def connect(cls, port: str, timeout: float = 4.0):
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("Install pyserial: pip install -r edge/requirements-hardware.txt") from exc
        transport = serial.Serial(port=port, baudrate=115200, timeout=timeout,
                                  write_timeout=timeout, dsrdtr=True)
        transport.setDTR(True)
        return cls(transport)

    def _send(self, command: bytes):
        if len(command) != 4:
            raise ValueError("Command must be 4 bytes")
        self.transport.write(command)
        self.transport.flush()

    def _read_exact(self, size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            chunk = self.transport.read(size-len(data))
            if not chunk:
                raise NiclaProtocolError("USB timed out while reading %d of %d bytes" % (len(data), size))
            data.extend(chunk)
        return bytes(data)

    def ping(self) -> bool:
        self._send(b"ping")
        return self._read_exact(4) == b"PONG"

    def snapshot_jpeg(self) -> bytes:
        self._send(b"snap")
        (size,) = struct.unpack("<L", self._read_exact(4))
        if not 100 <= size <= MAX_JPEG_BYTES:
            raise NiclaProtocolError("Unexpected JPEG size %d. Check firmware and serial port." % size)
        data = self._read_exact(size)
        if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
            raise NiclaProtocolError("Malformed camera JPEG")
        return data

    def set_warning(self, active: bool, force: bool = False):
        if not force and self._warning is active:
            return
        self._send(b"warn" if active else b"safe")
        self._warning = active

    def close(self):
        try:
            self.set_warning(False, force=True)
        finally:
            self.transport.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
