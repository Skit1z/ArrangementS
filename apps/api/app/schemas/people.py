"""人员相关请求 / 响应。默认脱敏，敏感字段仅显示掩码。"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import PersonStatus


class PeerOut(BaseModel):
    id: uuid.UUID
    full_name: str
    class_name: str


def _mask(last4: str | None, width: int) -> str | None:
    if not last4:
        return None
    return "*" * max(width - len(last4), 0) + last4


class PersonOut(BaseModel):
    id: uuid.UUID
    student_no: str
    class_name: str
    full_name: str
    phone: str
    difficulty_level: str | None = None
    id_card_masked: str | None = None
    bank_card_masked: str | None = None
    status: PersonStatus
    is_in_scheduling_pool: bool

    @classmethod
    def from_profile(cls, p) -> "PersonOut":
        return cls(
            id=p.id,
            student_no=p.student_no,
            class_name=p.class_name,
            full_name=p.full_name,
            phone=p.phone,
            difficulty_level=p.difficulty_level,
            id_card_masked=_mask(p.id_card_last4, 18),
            bank_card_masked=_mask(p.bank_card_last4, 16),
            status=p.status,
            is_in_scheduling_pool=p.is_in_scheduling_pool,
        )


class PersonCreateIn(BaseModel):
    student_no: str = Field(..., description="学号")
    class_name: str = Field("", description="班级（可选）")
    full_name: str = Field(..., description="姓名")
    phone: str = Field(..., description="手机号")
    difficulty_level: str | None = None
    id_card: str | None = None
    bank_card: str | None = None
    is_in_scheduling_pool: bool = True


class PersonUpdateIn(BaseModel):
    student_no: str | None = None
    class_name: str | None = None
    full_name: str | None = None
    phone: str | None = None
    difficulty_level: str | None = None
    id_card: str | None = None
    bank_card: str | None = None
    is_in_scheduling_pool: bool | None = None
    status: PersonStatus | None = None


class PersonCreateOut(BaseModel):
    person: PersonOut
    initial_password: str


class ImportPreviewRow(BaseModel):
    row_no: int
    student_no: str
    class_name: str
    full_name: str
    phone: str
    status: str
    errors: list[str]


class ImportPreviewOut(BaseModel):
    batch_id: uuid.UUID
    total_rows: int
    new_rows: int
    updated_rows: int
    error_rows: int
    rows: list[ImportPreviewRow]


class CreatedAccountOut(BaseModel):
    student_no: str
    full_name: str
    initial_password: str


class ImportConfirmOut(BaseModel):
    created_count: int
    accounts: list[CreatedAccountOut]


class SchedulingPoolRequest(BaseModel):
    person_ids: list[uuid.UUID]
    enabled: bool


class ConstraintCreate(BaseModel):
    constraint_type: str = Field(min_length=1, max_length=64)
    constraint_value: dict | None = None
    is_hard: bool = True


class ConstraintOut(BaseModel):
    id: uuid.UUID
    constraint_type: str
    constraint_value: dict | None
    is_hard: bool
    is_active: bool

    model_config = {"from_attributes": True}


class SensitiveOut(BaseModel):
    id_card: str | None = None
    bank_card: str | None = None
