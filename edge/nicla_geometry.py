"""Pure, testable virtual-zone geometry and frame-based debouncing."""
from dataclasses import dataclass

def zone_from_fractions(width, height, left=.35, top=.20, right=.80, bottom=.90):
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError("Invalid fractional zone bounds")
    return (int(left*width), int(top*height), int(right*width), int(bottom*height))

def person_in_zone(person_boxes, zone):
    """Foot position estimated by the bottom centre of each person box."""
    zx1, zy1, zx2, zy2 = zone
    for x1, y1, x2, y2 in person_boxes:
        foot_x = (x1+x2)//2
        if zx1 <= foot_x <= zx2 and zy1 <= y2 <= zy2:
            return True
    return False

@dataclass
class DebouncedOccupancy:
    required_frames: int = 2
    inside: bool = False
    streak: int = 0

    def update(self, observed: bool) -> bool:
        if observed == self.inside:
            self.streak = 0
        else:
            self.streak += 1
            if self.streak >= self.required_frames:
                self.inside = observed
                self.streak = 0
        return self.inside
