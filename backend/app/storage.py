
from threading import Lock
from pymongo import MongoClient, DESCENDING
from pymongo.errors import DuplicateKeyError #prevents dup incidents, no 2 indiecents with the same id
from .config import MONGODB_URI, MONGODB_DB #the mongo db address and the name of DB name 
from .models import Incident #takes the incident from the python file mdoels.py and taktes that incident as an object 


#class to manage our database operations 
class MongoStore:
    mode = "mongodb"
    def __init__(self, uri, db):
        client = MongoClient(uri) #current databse uri
        self.events = client[db]["incidents"] #database name 

        self.events.create_index("event_id", unique=True)#database primary key event_id
        self.events.create_index("timestamp")#column timestamp 

    #saves event into db
    def save(self, event: Incident) -> Incident:
        try:
            self.events.insert_one(event.model_dump(mode="json")) # inserts created event object into the db 

        except DuplicateKeyError: #if there is a dup id, don"t save
            pass

        return event

    #displays any number of recent db incidents 
    def recent(self, limit: int) -> list[dict]: #put the limit of incidents
        return list(
            self.events.find({}, {"_id": 0}) #reads the json format 
            .sort("timestamp", -1)
            .limit(limit) # stops at limit 
        )

#temporary python storage incase mongodb is not online
class MemoryStore:
    mode = "memory"

    def __init__(self):
        self.events = {}
        self.lock = Lock()

    def save(self, event: Incident) -> Incident:
        with self.lock:
            if event.event_id not in self.events:
                self.events[event.event_id] = event.model_dump(mode="json")

        return event

    def recent(self, limit: int) -> list[dict]:
        with self.lock:
            return sorted(
                self.events.values(),
                key=lambda event: event["timestamp"],
                reverse=True
            )[:limit]
if MONGODB_URI:
    store = MongoStore(MONGODB_URI, MONGODB_DB) #creates a new object that uses current uri and db name to save and retrieve using our functions 
else:
    store = MemoryStore()

