"""Arduino UNO Q / App Lab: HTTP bridge to the warning sign.

Add the Web UI Brick in App Lab. This server has no authentication:
use only on a trusted isolated development setup via USB/ADB.
"""
from arduino.app_utils import App, Bridge
from arduino.app_bricks.web_ui import WebUI

ui = WebUI(port=7000, cors_origins="")


def danger_on():
    Bridge.call("set_danger", True)
    return {"danger": True}


def danger_off():
    Bridge.call("set_danger", False)
    return {"danger": False}


def status():
    return {"device": "SiteGuardian UNO Q", "status": "online"}


ui.expose_api("POST", "/danger/on", danger_on)
ui.expose_api("POST", "/danger/off", danger_off)
ui.expose_api("GET", "/status", status)

print("SiteGuardian UNO Q warning service starting...", flush=True)
App.run()
