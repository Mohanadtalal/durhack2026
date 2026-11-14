from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

class Incident(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=6)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_id: str = Field(min_length=1, max_length=100)
    zone_id: str = Field(min_length=1, max_length=100)
    hazard_type: str = Field(min_length=1, max_length=100)
    severity: Literal["info", "warning", "high", "critical"] = "warning"
    description: str = Field(min_length=1, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)

class Insight(BaseModel):
    summary: str
    model: str
    events_analyzed: int
