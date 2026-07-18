import uuid
from datetime import datetime

from pydantic import BaseModel

class OvertimeRequestCreate(BaseModel):
    venue_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    reason: str

class OvertimeRequestOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    person_name: str | None = None
    venue_id: uuid.UUID
    venue_name: str | None = None
    start_at: datetime
    end_at: datetime
    reason: str
    status: str
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
