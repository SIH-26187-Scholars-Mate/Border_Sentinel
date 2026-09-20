from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class ZonePoint(BaseModel):
    x: float
    y: float

class ZoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    points: List[ZonePoint] = Field(min_length=3)
    enabled: bool = True
    trigger_object: str = 'person'

class ZoneOut(ZoneCreate):
    id: UUID
    camera_id: UUID
    created_at: datetime | None = None
