"""Nicla Vision OpenMV firmware: RGB MJPEG video over private 2.4 GHz Wi-Fi.

This is an ALTERNATIVE to the current SiteGuardian USB 'raw0' main.py.
Run TEMPORARILY from OpenMV IDE first; do NOT save as /flash/main.py.
If flashed as main.py, it replaces USB command handling until restored.
The Linux/UNO Q consumer and inference still require integration/testing.

For first test, create sg_wifi.py on the Nicla filesystem with:
    WIFI_SSID = "your-private-2.4-ghz-ssid"
    WIFI_PASSWORD = "your-password"
Do NOT commit credentials or expose port 8080 to the Internet.
"""
import network
import csi
import socket
import time

from sg_wifi import WIFI_SSID, WIFI_PASSWORD

PORT = 8080
JPEG_QUALITY = 48

cam = csi.CSI()
cam.reset()
cam.pixformat(csi.RGB565)  # Keep color detail for small-object recognition.
cam.framesize(csi.QVGA)
cam.framebuffers(1)
cam.snapshot(time=1500)

wifi = network.WLAN(network.WLAN.IF_STA)
wifi.active(True)
wifi.connect(WIFI_SSID, WIFI_PASSWORD)
deadline = time.ticks_add(time.ticks_ms(), 30000)
while not wifi.isconnected():
    if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
        raise RuntimeError("Nicla Wi-Fi connection timed out")
    time.sleep_ms(250)

print("SiteGuardian Nicla Wi-Fi:", wifi.ifconfig())
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT))
server.listen(1)
print("MJPEG camera ready at http://%s:%d/stream.mjpg" %
      (wifi.ifconfig()[0], PORT))

while True:
    client, address = server.accept()
    try:
        request = client.recv(1024)
        if not (b"GET /stream.mjpg " in request or b"GET / " in request):
            client.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            continue
        client.sendall(
            b"HTTP/1.1 200 OK\r\n"
            b"Cache-Control: no-cache\r\n"
            b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
            b"Connection: close\r\n\r\n"
        )
        while wifi.isconnected():
            jpeg = cam.snapshot().to_jpeg(quality=JPEG_QUALITY, copy=True)
            client.sendall(
                ("--frame\r\n"
                 "Content-Type: image/jpeg\r\n"
                 "Content-Length: %d\r\n\r\n" % jpeg.size()).encode()
            )
            client.sendall(jpeg)
            client.sendall(b"\r\n")
    except OSError as error:
        print("Stream client disconnected:", error)
    finally:
        client.close()
