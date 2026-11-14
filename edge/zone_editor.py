"""Interactive Nicla camera zone configuration and pure polygon geometry.

Persist normalized coordinates so every zone remains camera-resolution
independent. The camera starts with no zones. Files are written on the laptop;
Nicla firmware is unchanged.
"""
import json
import math
from pathlib import Path

DEFAULT_ZONE_FILE = Path("data/nicla_zones.json")
MAX_VERTICES = 12
MAX_ZONES = 12


def _on_segment(a, b, p):
    ax, ay = a
    bx, by = b
    px, py = p
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    return (abs(cross) < 1e-9 and min(ax, bx) - 1e-9 <= px <= max(ax, bx) + 1e-9
            and min(ay, by) - 1e-9 <= py <= max(ay, by) + 1e-9)


def _orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _intersect(a, b, c, d):
    # Includes collinear overlaps, but callers skip adjacent polygon edges.
    ab_c = _orientation(a, b, c)
    ab_d = _orientation(a, b, d)
    cd_a = _orientation(c, d, a)
    cd_b = _orientation(c, d, b)
    if (ab_c > 0 > ab_d or ab_c < 0 < ab_d) and (cd_a > 0 > cd_b or cd_a < 0 < cd_b):
        return True
    return any((_on_segment(a, b, c), _on_segment(a, b, d),
                _on_segment(c, d, a), _on_segment(c, d, b)))


def validate_polygon(points):
    """Return validated normalized points; reject degenerate/crossing zones."""
    if not isinstance(points, (list, tuple)) or not 3 <= len(points) <= MAX_VERTICES:
        raise ValueError("A zone needs 3 to 12 corners.")
    normalized = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("Each corner must contain x and y.")
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) or not 0 <= v <= 1 for v in point):
            raise ValueError("Zone coordinates must be between 0 and 1.")
        normalized.append((float(point[0]), float(point[1])))
    if len(set(normalized)) != len(normalized):
        raise ValueError("Each zone corner must be distinct.")
    # Shoelace formula. Prevent zones too small to use in the camera feed.
    area2 = sum(normalized[i][0] * normalized[(i+1) % len(normalized)][1]
                - normalized[(i+1) % len(normalized)][0] * normalized[i][1]
                for i in range(len(normalized)))
    if abs(area2) < 0.002:
        raise ValueError("Zone is too small; choose a larger area.")
    n = len(normalized)
    for i in range(n):
        a, b = normalized[i], normalized[(i + 1) % n]
        for j in range(i + 1, n):
            # Adjacent segments share a corner by design.
            if (j == i + 1) or (i == 0 and j == n - 1):
                continue
            c, d = normalized[j], normalized[(j + 1) % n]
            if _intersect(a, b, c, d):
                raise ValueError("Zone edges cannot cross.")
    return normalized


def pixels_from_normalized(points, width, height):
    if width <= 0 or height <= 0:
        raise ValueError("Invalid frame dimensions")
    return [(min(width - 1, int(x * width)), min(height - 1, int(y * height)))
            for x, y in points]


def point_in_polygon(point, corners):
    """Ray casting, including the boundary, for convex or concave polygons."""
    x, y = point
    inside = False
    for i, a in enumerate(corners):
        b = corners[(i + 1) % len(corners)]
        if _on_segment(a, b, point):
            return True
        ax, ay = a
        bx, by = b
        if (ay > y) != (by > y):
            crossing_x = ax + (y - ay) * (bx - ax) / (by - ay)
            if x < crossing_x:
                inside = not inside
    return inside


def person_in_polygon(person_boxes, corners):
    """Approximate each person's position by the bottom centre of its box."""
    return any(point_in_polygon(((x1 + x2) // 2, y2), corners)
               for x1, y1, x2, y2 in person_boxes)


def load_zones(path=DEFAULT_ZONE_FILE):
    """Load version-2 saved zones, or start with none.

    An earlier single-zone file (data/nicla_zone.json) is intentionally
    ignored so upgrading starts with an empty camera view.
    """
    path = Path(path)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("version") != 2:
            raise ValueError("Unsupported zone configuration version.")
        zones = payload["zones"]
        if not isinstance(zones, list) or len(zones) > MAX_ZONES:
            raise ValueError("Expected at most 12 zones.")
        return [validate_polygon(points) for points in zones]
    except (ValueError, TypeError, KeyError, OSError, AttributeError) as exc:
        print("[ZONE] Invalid saved zones; starting empty:", exc)
        return []


class ZoneEditor:
    def __init__(self, path=DEFAULT_ZONE_FILE):
        self.path = Path(path)
        self.zones = load_zones(self.path)
        self.editing = False
        self.draft = []

    def pixels(self, width, height):
        """Return an independent polygon for each saved restricted zone."""
        return [pixels_from_normalized(points, width, height)
                for points in self.zones]

    def draft_pixels(self, width, height):
        return pixels_from_normalized(self.draft, width, height)

    def begin(self):
        self.draft = []
        self.editing = True

    def add_corner(self, x, y, width, height):
        if not self.editing or width <= 0 or height <= 0:
            return
        if 0 <= x < width and 0 <= y < height and len(self.draft) < MAX_VERTICES:
            self.draft.append((x / width, y / height))

    def undo(self):
        if self.editing and self.draft:
            self.draft.pop()

    def cancel(self):
        self.draft = []
        self.editing = False

    def save(self):
        """Append a new zone; never replace any previously saved polygon."""
        if not self.editing:
            return False
        new_points = validate_polygon(self.draft)
        if len(self.zones) >= MAX_ZONES:
            raise ValueError("Maximum of 12 zones reached. Press R to clear all.")
        new_zones = self.zones + [new_points]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temp_file.write_text(json.dumps({"version": 2, "zones": new_zones}, indent=2) + "\n",
                                 encoding="utf-8")
            temp_file.replace(self.path)
        finally:
            temp_file.unlink(missing_ok=True)
        self.zones = new_zones
        self.cancel()
        return True

    def reset(self):
        """Remove all configured zones and their saved file."""
        self.path.unlink(missing_ok=True)
        self.zones = []
        self.cancel()
