"""Pure helper rules for optional PPE model and forward ToF alerts."""
from dataclasses import dataclass

PPE_HAZARDS = ("missing_helmet", "missing_vest")
PPE_ALIASES = {
    "no_helmet": "missing_helmet", "without_helmet": "missing_helmet",
    "missing_helmet": "missing_helmet", "bare_head": "missing_helmet",
    "no_hardhat": "missing_helmet", "no_hard_hat": "missing_helmet",
    "no_vest": "missing_vest", "without_vest": "missing_vest",
    "no_safety_vest": "missing_vest",
    "missing_vest": "missing_vest", "no_safety_vest": "missing_vest",
}


def ppe_hazard_from_label(name):
    key = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    return PPE_ALIASES.get(key)


def supported_ppe_classes(names):
    values = names.values() if isinstance(names, dict) else names
    return {hazard for name in values if (hazard := ppe_hazard_from_label(name))}


def extract_ppe_hazards(names, detections, min_confidence=0.45):
    """Only EXPLICIT missing-PPE labels count, not absent helmet detections.

    detections is iterable of (class_id, confidence, [x1, y1, x2, y2]).
    """
    findings = []
    for class_id, confidence, box in detections:
        if confidence < min_confidence:
            continue
        hazard = ppe_hazard_from_label(names[int(class_id)])
        if hazard:
            findings.append((hazard, tuple(int(x) for x in box), float(confidence)))
    return findings


@dataclass
class ProximityAlert:
    threshold_mm: int
    required_samples: int = 2
    near: bool = False
    streak: int = 0

    def __post_init__(self):
        if not 50 <= self.threshold_mm <= 4000:
            raise ValueError("Proximity threshold must be 50–4000 mm.")
        if self.required_samples < 1:
            raise ValueError("Required samples must be positive.")

    def update(self, distance_mm):
        """Return (entered, cleared). Invalid/unknown samples leave state unchanged."""
        if distance_mm is None:
            self.streak = 0
            return False, False
        observed = distance_mm <= self.threshold_mm
        if observed == self.near:
            self.streak = 0
            return False, False
        self.streak += 1
        if self.streak < self.required_samples:
            return False, False
        self.near = observed
        self.streak = 0
        return (self.near, not self.near)
