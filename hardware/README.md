# Optional prototype warning hardware

A generic Arduino-compatible board receiving USB serial commands can illuminate a LED and sound a buzzer. The `edge/camera.py` script sends `ALERT` and `CLEAR` lines at 9600 baud.

1. Verify actual board/USB compatibility before connecting anything.
2. Install the sketch from `arduino_alert/arduino_alert.ino` to a **generic compatible board**.
3. Use a demo LED with resistor and low-power buzzer, never connect real machinery.
4. Install Python serial support: `pip install -r edge/requirements-hardware.txt`.
5. In local `.env` set `ARDUINO_PORT=COM3` (or actual serial port).

**Note:** the hackathon's Arduino UNO Q may require a different serial bridge, board support package or pin mapping. This sketch has NOT been verified on that board and must be adapted to the actual hardware.
