# SiteGuardian AI — Nicla Vision OpenMV firmware.
# Raw grayscale USB streaming avoids JPEG encoder failures seen on v5.0.1.
# The 'snap' command remains for diagnostic JPEG attempts; 'raw0' is preferred.
# Save as /flash/main.py (Windows USB drive: main.py), EJECT, then power-cycle.
# Hackathon prototype only. Not a certified construction safety system.
import csi
import struct
from pyb import USB_VCP

from machine import LED
red = LED("LED_RED")
red.off()

usb = USB_VCP()
usb.setinterrupt(-1)  # Disable Ctrl-C character handling for raw binary frames.
camera = csi.CSI()
camera.reset()
camera.pixformat(csi.GRAYSCALE)  # One byte per pixel; no JPEG dependency.
camera.framesize(csi.QVGA)       # 320 x 240 = 76,800 bytes per frame.
camera.framebuffers(1)
camera.snapshot(time=2000)

# Initialise the ToF sensor lazily; normal camera mode is unaffected.
tof = None
tof_initialised = False

def send_all(data):
    # A USB send is allowed to write fewer bytes than requested.
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        count = usb.send(view[offset:offset + 512], timeout=5000)
        if not count:
            raise OSError("USB transfer timed out")
        offset += count

while True:
    command = usb.recv(4, timeout=1000)
    if command == b"raw0":
        image = camera.snapshot()
        pixels = image.bytearray()
        send_all(struct.pack("<L", len(pixels)))
        send_all(pixels)
    elif command == b"snap":
        # Optional diagnostic path only. Avoid breaking the serial protocol
        # if this board's JPEG encoder cannot compress the image.
        try:
            jpg = camera.snapshot().to_jpeg(quality=35, copy=True)
            send_all(struct.pack("<L", jpg.size()))
            send_all(jpg)
        except OSError:
            send_all(struct.pack("<L", 0))
    elif command == b"dist":
        # A 4-byte unsigned distance in mm, 0xFFFFFFFF if unavailable.
        # Arduino's Nicla board uses a VL53L1 on internal I2C bus 2.
        if not tof_initialised:
            tof_initialised = True
            try:
                from machine import I2C
                from vl53l1x import VL53L1X
                tof = VL53L1X(I2C(2))
            except Exception:
                tof = None
        mm = 0xFFFFFFFF
        if tof is not None:
            try:
                value = int(tof.read())
                if 20 <= value <= 4000:
                    mm = value
            except Exception:
                pass
        send_all(struct.pack("<L", mm))
    elif command == b"warn":
        red.on()
    elif command == b"safe":
        red.off()
    elif command == b"ping":
        send_all(b"PONG")
