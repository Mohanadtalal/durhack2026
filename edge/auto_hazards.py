"""State and validation for *model-detected* hazardous objects.

A pretrained COCO person model does NOT detect knives. The caller must load
an explicit knife-capable open-vocabulary or custom detector and supply its
predictions; this module only filters labels and manages warning persistence.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class HazardDetection:
    label: str
    confidence: float
    box: tuple[int, int, int, int]
    track_id: int | None = None


def parse_labels(csv: str) -> tuple[str, ...]:
    labels = tuple(dict.fromkeys(word.strip().casefold() for word in csv.split(",")
                                 if word.strip()))
    if not labels:
        raise ValueError("At least one nonempty hazard label is required")
    return labels


def find_hazards(names, rows, allowed_labels, confidence=0.45):
    """Filter YOLO tracking outputs. rows=(class_id, score, xyxy, track_id)."""
    if not 0 < confidence <= 1:
        raise ValueError("Hazard confidence must be in (0, 1]")
    allowed = set(allowed_labels)
    found = []
    for class_id, score, box, track_id in rows:
        label = str(names[int(class_id)]).strip().casefold()
        if label not in allowed or float(score) < confidence:
            continue
        found.append(HazardDetection(
            label, float(score), tuple(int(v) for v in box),
            int(track_id) if track_id is not None else None,
        ))
    return found


class HazardMonitor:
    """Immediate ON at first detection; hold ON through brief missing frames."""

    def __init__(self, clear_after: int = 4):
        if clear_after < 1:
            raise ValueError("clear_after must be at least 1 frame")
        self.clear_after = clear_after
        self.active = False
        self.missed = 0

    def update(self, detections) -> bool:
        """Return True only on a new hazard episode for incident logging."""
        if detections:
            was_active = self.active
            self.active = True
            self.missed = 0
            return not was_active
        self.missed += 1
        if self.missed >= self.clear_after:
            self.active = False
        return False

    def reset(self):
        self.active = False
        self.missed = 0
