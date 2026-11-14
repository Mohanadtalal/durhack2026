"""Deterministic transition-based warning logic.

A zone-entry event fires once when occupancy begins. Prolonged exposure
fires once after the configured duration, not continuously every frame.
"""
from dataclasses import dataclass

@dataclass
class ZoneMonitor:
    dwell_seconds: float = 8.0
    entered_at: float | None = None
    prolonged_emitted: bool = False

    def update(self, inside: bool, now: float) -> list[str]:
        if not inside:
            self.entered_at = None
            self.prolonged_emitted = False
            return []
        if self.entered_at is None:
            self.entered_at = now
            self.prolonged_emitted = False
            return ["zone_entry"]
        if not self.prolonged_emitted and now - self.entered_at >= self.dwell_seconds:
            self.prolonged_emitted = True
            return ["prolonged_exposure"]
        return []
