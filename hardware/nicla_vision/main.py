# Nicla Vision: save as main.py ON THE BOARD via OpenMV IDE.
# USB VCP: snap -> little-endian uint32 size + JPEG; warn/safe -> red LED; ping -> PONG.
# For a harmless hackathon demonstration only, never a certified alarm.
import csi
import struct
from pyb import USB_VCP
try:
    from machine import LED
    red = LED("LED_RED")
except (ImportError, ValueError, TypeError):
    from pyb import LED
    red = LED(1)

red.off()
usb = USB_VCP()
camera = csi.CSI()
camera.reset()
camera.pixformat(csi.RGB565)
camera.framesize(csi.QVGA)
camera.snapshot(time=2000)

while True:
    command = usb.recv(4, timeout=1000)
    if command == b"snap":
        frame = camera.snapshot().to_jpeg()
        usb.send(struct.pack("<L", frame.size()))
        usb.send(frame)
    elif command == b"warn":
        red.on()
    elif command == b"safe":
        red.off()
    elif command == b"ping":
        usb.send(b"PONG")
