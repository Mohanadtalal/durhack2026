"""Conservative image-plane movement warnings for stationary Nicla cameras.

Tracks are supplied by a separate object tracker (for example YOLO ByteTrack).
Pixel motion is NOT calibrated distance, velocity, collision probability or
a reliable indication that someone is walking backward.
"""
from dataclasses import dataclass
from math import hypot

from .nicla_geometry import DebouncedOccupancy
from .zone_editor import point_in_polygon


@dataclass(frozen=True)
class MotionWarning:
    hazard_type: str
    source_id: int
    target_id: int
    seconds_ahead: float
    gap: float


@dataclass
class _Track:
    class_id: int
    xy: tuple
    timestamp: float
    vx: float = 0.0
    vy: float = 0.0
    samples: int = 1


def _distance(a, b):
    return hypot(a[0] - b[0], a[1] - b[1])


def _point_to_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return _distance(p, a), a
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    nearest = (a[0] + t * dx, a[1] + t * dy)
    return _distance(p, nearest), nearest


def _polygon_distance(p, polygon):
    if point_in_polygon(p, polygon):
        return 0.0, p
    nearest = None
    best = float("inf")
    for i, a in enumerate(polygon):
        distance, projected = _point_to_segment(p, a, polygon[(i + 1) % len(polygon)])
        if distance < best:
            best, nearest = distance, projected
    return best, nearest


class PredictiveMotionMonitor:
    """Detect screen-space path convergence using consistent tracked IDs.

    A vehicle must be visibly moving *toward* a person, not just standing near
    them. Sharp zones are manually selected saved polygons, not automatically
    recognized sharp tools. Both require consecutive positive observations.
    """

    def __init__(self, horizon_seconds=2.0, confirm_frames=2):
        if not 0.5 <= horizon_seconds <= 5.0:
            raise ValueError("Prediction horizon must be 0.5–5 seconds")
        if confirm_frames < 1:
            raise ValueError("Confirm frames must be positive")
        self.horizon = horizon_seconds
        self.confirm_frames = confirm_frames
        self.tracks = {}
        self.states = {}
        self.active = []
        self._last_warnings = {}
        self.debug_summary = "Waiting for tracked detections"

    def reset(self):
        self.tracks.clear()
        self.states.clear()
        self.active = []
        self._last_warnings.clear()
        self.debug_summary = "Waiting for tracked detections"

    def _register(self, ident, class_id, box, when, width, height):
        x1, y1, x2, y2 = box
        position = ((x1 + x2) / (2.0 * width), y2 / float(height))
        previous = self.tracks.get(ident)
        velocity = (0.0, 0.0)
        count = 1
        if previous and previous.class_id == class_id:
            dt = when - previous.timestamp
            if 0.03 <= dt <= 2.0:
                new_x = (position[0] - previous.xy[0]) / dt
                new_y = (position[1] - previous.xy[1]) / dt
                if previous.samples < 2:
                    velocity = (new_x, new_y)
                else:
                    velocity = (0.6 * new_x + 0.4 * previous.vx,
                                0.6 * new_y + 0.4 * previous.vy)
                count = previous.samples + 1
        self.tracks[ident] = _Track(class_id, position, when,
                                    velocity[0], velocity[1], count)
        return self.tracks[ident]

    def explain_vehicle_pair(self, vehicle, person):
        """Explain a *single* failed/pending vehicle prediction.

        Mirrors the screening conditions in _vehicle_person; use for
        diagnostics only, never to weaken or override safety thresholds.
        """
        if vehicle.samples < 2 or person.samples < 2:
            return "WAITING FOR STABLE TRACK IDS"
        dx = person.xy[0] - vehicle.xy[0]
        dy = person.xy[1] - vehicle.xy[1]
        separation = hypot(dx, dy)
        if not 0.09 < separation < 0.8:
            return "OBJECTS TOO CLOSE/FAR IN FRAME"
        toward = (dx * vehicle.vx + dy * vehicle.vy) / separation
        if toward < 0.035:
            return "CAR NOT MOVING TOWARD PERSON"
        relative_x = vehicle.vx - person.vx
        relative_y = vehicle.vy - person.vy
        speed2 = relative_x ** 2 + relative_y ** 2
        if speed2 < 0.002:
            return "LITTLE RELATIVE MOTION"
        ahead = (dx * relative_x + dy * relative_y) / speed2
        if ahead <= 0.05:
            return "PATHS NOT CLOSING"
        if ahead > self.horizon:
            return "APPROACH OUTSIDE 2 SECOND HORIZON"
        closest = hypot(dx - relative_x * ahead, dy - relative_y * ahead)
        if closest > 0.11:
            return "PROJECTED PATHS TOO FAR APART"
        return "APPROACH CANDIDATE - CONFIRMING"

    def describe_vehicle_status(self, people, cars):
        """Human-readable check for the live --motion-debug overlay."""
        prefix = f"PEOPLE {len(people)} | CARS {len(cars)}"
        if not people:
            return prefix + " | NO PERSON DETECTED/TRACKED"
        if not cars:
            return prefix + " | NO CAR DETECTED/TRACKED"
        diagnoses = [
            (self.explain_vehicle_pair(car, person), cid, pid)
            for cid, car in cars.items()
            for pid, person in people.items()
        ]
        # Show the most actionable diagnosis, when multiple pairs exist.
        priority = [
            "APPROACH CANDIDATE - CONFIRMING",
            "APPROACH OUTSIDE 2 SECOND HORIZON",
            "PROJECTED PATHS TOO FAR APART",
            "CAR NOT MOVING TOWARD PERSON",
            "PATHS NOT CLOSING",
            "LITTLE RELATIVE MOTION",
            "WAITING FOR STABLE TRACK IDS",
            "OBJECTS TOO CLOSE/FAR IN FRAME",
        ]
        diagnoses.sort(key=lambda item: priority.index(item[0]))
        status, cid, pid = diagnoses[0]
        return f"{prefix} | CAR {cid} / PERSON {pid}: {status}"

    def _vehicle_person(self, vehicle_id, vehicle, person_id, person):
        if vehicle.samples < 2 or person.samples < 2:
            return None
        direction = (person.xy[0] - vehicle.xy[0],
                     person.xy[1] - vehicle.xy[1])
        separation = hypot(*direction)
        if not 0.09 < separation < 0.8:
            return None
        vehicle_toward = (direction[0] * vehicle.vx + direction[1] * vehicle.vy) / separation
        if vehicle_toward < 0.035:
            return None
        relative_v = (vehicle.vx - person.vx, vehicle.vy - person.vy)
        relative_speed2 = relative_v[0] ** 2 + relative_v[1] ** 2
        if relative_speed2 < 0.002:
            return None
        ahead = (direction[0] * relative_v[0] + direction[1] * relative_v[1]) / relative_speed2
        if not 0.05 < ahead <= self.horizon:
            return None
        closest = hypot(direction[0] - relative_v[0] * ahead,
                        direction[1] - relative_v[1] * ahead)
        if closest > 0.11:
            return None
        return MotionWarning("vehicle_approaching_person", vehicle_id,
                             person_id, ahead, closest)

    def _person_sharp_zone(self, person_id, person, zone_id, polygon):
        if person.samples < 2 or hypot(person.vx, person.vy) < 0.045:
            return None
        distance, nearest = _polygon_distance(person.xy, polygon)
        if not 0.03 < distance < 0.5:
            return None
        direction = ((nearest[0] - person.xy[0]) / distance,
                     (nearest[1] - person.xy[1]) / distance)
        if direction[0] * person.vx + direction[1] * person.vy < 0.035:
            return None
        # Require a projected near-intersection with the marked hazard area.
        for i in range(1, 9):
            future = self.horizon * i / 8
            predicted_xy = (person.xy[0] + person.vx * future,
                            person.xy[1] + person.vy * future)
            future_distance, _ = _polygon_distance(predicted_xy, polygon)
            if future_distance < 0.055 and future_distance < distance - 0.025:
                return MotionWarning("person_approaching_marked_sharp_zone",
                                     person_id, zone_id, future, future_distance)
        return None

    def update(self, detections, when, width, height, sharp_zones=()):
        """Return NEW confirmed warnings and update active warnings.

        detections: (track_id, class_id, (x1,y1,x2,y2)) where class 0 is
        person and class 2 is car; no detection IDs means no prediction.
        sharp_zones: iterable of (zone_number, polygon_px) set by operator.
        """
        if width <= 0 or height <= 0:
            raise ValueError("Invalid camera size")
        if not isinstance(when, (int, float)):
            raise ValueError("Invalid frame timestamp")
        current = {}
        for ident, class_id, box in detections:
            if ident is None or class_id not in (0, 2):
                continue
            ident = int(ident)
            current[ident] = self._register(ident, int(class_id), box, when, width, height)
        # Never predict with stale tracks that disappeared from the frame.
        self.tracks = {ident: track for ident, track in self.tracks.items()
                       if when - track.timestamp <= 2.0}
        people = {ident: track for ident, track in current.items() if track.class_id == 0}
        cars = {ident: track for ident, track in current.items() if track.class_id == 2}
        self.debug_summary = self.describe_vehicle_status(people, cars)
        candidates = {}
        for car_id, car in cars.items():
            for person_id, person in people.items():
                found = self._vehicle_person(car_id, car, person_id, person)
                if found is not None:
                    candidates[("vehicle", car_id, person_id)] = found
        for zone_id, px in sharp_zones:
            polygon = [(x / width, y / height) for x, y in px]
            if len(polygon) < 3:
                continue
            for person_id, person in people.items():
                found = self._person_sharp_zone(person_id, person, zone_id, polygon)
                if found is not None:
                    candidates[("sharp", person_id, zone_id)] = found

        events = []
        active = []
        for key in set(self.states) | set(candidates):
            state = self.states.setdefault(key, DebouncedOccupancy(self.confirm_frames))
            before = state.inside
            confirmed = state.update(key in candidates)
            if key in candidates:
                self._last_warnings[key] = candidates[key]
            if confirmed and key in self._last_warnings:
                active.append(self._last_warnings[key])
                if not before:
                    events.append(self._last_warnings[key])
            elif not confirmed and key not in candidates:
                self.states.pop(key, None)
                self._last_warnings.pop(key, None)
        self.active = sorted(active, key=lambda a: (a.hazard_type, a.source_id, a.target_id))
        if any(w.hazard_type == "vehicle_approaching_person" for w in self.active):
            self.debug_summary += " | VEHICLE WARNING ACTIVE"
        return events
