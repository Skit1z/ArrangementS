import uuid
from datetime import datetime

from pydantic import BaseModel

class ManualSlotCreate(BaseModel):
    venue_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    required_people: int
