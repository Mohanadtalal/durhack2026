"""Development memory storage or actual MongoDB incidents. No silent fallback if MongoDB configured."""
from threading import Lock
from pymongo import MongoClient, DESCENDING
from pymongo.errors import DuplicateKeyError
from .config import MONGODB_URI, MONGODB_DB
from .models import Incident

class MemoryStore:
    mode = "memory"
    def __init__(self):
        self._items: dict[str, dict] = {}
        self._lock = Lock()

    def save(self, event: Incident) -> Incident:
        with self._lock:
            self._items.setdefault(event.event_id, event.model_dump(mode="json"))
        return event

    def recent(self, limit: int) -> list[dict]:
        with self._lock:
            return sorted(self._items.values(), key=lambda x: x["timestamp"], reverse=True)[:limit]

class MongoStore:
    mode = "mongodb"
    def __init__(self, uri: str, db: str):
        client = MongoClient(uri, serverSelectionTimeoutMS=4000)
        self.events = client[db].incidents
        self.events.create_index("event_id", unique=True)
        self.events.create_index([("timestamp", DESCENDING)])

    def save(self, event: Incident) -> Incident:
        try:
            self.events.insert_one(event.model_dump(mode="json"))
        except DuplicateKeyError:
            pass
        return event

    def recent(self, limit: int) -> list[dict]:
        return list(self.events.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit))

store = MongoStore(MONGODB_URI, MONGODB_DB) if MONGODB_URI else MemoryStore()
