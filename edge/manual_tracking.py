"""Small, independent helpers for operator-selected multi-object tracking.

This is manual (T + ROI), not automatic hazard recognition. It adds visual
boxes only; it does not assert that a selected object is dangerous.
"""


def create_manual_tracker(cv2_module):
    """Prefer CSRT when available, with the standard OpenCV MIL fallback.

    CSRT is usually supplied by opencv-contrib-python, while MIL ships
    with many standard opencv-python builds. Do not require contrib just
    to launch the camera.
    """
    namespaces = (cv2_module, getattr(cv2_module, "legacy", None))
    for name in ("TrackerCSRT_create", "TrackerMIL_create"):
        for namespace in namespaces:
            if namespace is None:
                continue
            factory = getattr(namespace, name, None)
            if callable(factory):
                return factory()
    raise RuntimeError(
        "No compatible OpenCV object tracker is installed. "
        "Install opencv-contrib-python in the active virtual environment."
    )


def update_manual_trackers(trackers, frame):
    """Update every tracker once per camera frame; drop lost ones afterwards.

    Mutate the list in place, not from inside the iteration. Return the
    updated boxes and the number of trackers lost on this frame.
    """
    active = []
    boxes = []
    for tracker in trackers:
        success, box = tracker.update(frame)
        if success:
            active.append(tracker)
            boxes.append(tuple(map(int, box)))
    lost = len(trackers) - len(active)
    trackers[:] = active
    return boxes, lost
