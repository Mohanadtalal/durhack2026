"""Nicla Vision OpenMV firmware: RGB MJPEG video over private 2.4 GHz Wi-Fi.

This is an ALTERNATIVE to the current SiteGuardian USB 'raw0' main.py.
Run TEMPORARILY from OpenMV IDE first; do NOT save as /flash/main.py.
If flashed as main.py, it replaces USB command handling until restored.
The Linux/UNO Q consumer and inference still require integration/testing.

For a temporary OpenMV test, edit the placeholders below LOCALLY in the IDE.
Do NOT commit real Wi-Fi credentials or expose port 8080 to the Internet.
"""
import network
import csi
import socket
import time

# Edit these two lines LOCALLY in OpenMV IDE. Do not commit the changes.
WIFI_SSID = "YOUR_PRIVATE_2_4_GHZ_WIFI"
WIFI_PASSWORD = "YOUR_PRIVATE_WIFI_PASSWORD"

if WIFI_SSID.startswith("YOUR_") or WIFI_PASSWORD.startswith("YOUR_"):
    raise ValueError("Set the Wi-Fi SSID and password locally in OpenMV IDE.")

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
        client.settimeout(6.0)
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
