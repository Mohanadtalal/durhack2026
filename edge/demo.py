"""Synthetic end-to-end events for camera-free demos. Run: python -m edge.demo"""
import time
from datetime import datetime, timezone
from uuid import uuid4
from .client import send_event
from .zone_rules import ZoneMonitor

def make_event(kind: str) -> dict:
    return {
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_id": "simulator-01",
        "zone_id": "cutting-station-a",
        "hazard_type": kind,
        "severity": "high" if kind == "prolonged_exposure" else "warning",
        "description": "Simulated " + kind.replace("_", " ") + " at mock machine",
        "metadata": {"simulated": True},
    }

def main():
    monitor = ZoneMonitor(dwell_seconds=3)
    print("SIMULATION: person enters mock restricted zone...")
    for elapsed in [0.0, 1.0, 2.0, 3.5, 4.0]:
        for kind in monitor.update(True, elapsed):
            print("[LOCAL ALERT]", kind)
            send_event(make_event(kind))
        time.sleep(0.8)
    monitor.update(False, 6.0)
    print("Exit detected. Done.")

if __name__ == "__main__":
    main()
