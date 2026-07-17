"""集中导入全部 ORM 模型，确保 Base.metadata 完整。"""
from app.db.base import Base
from app.models.audit import AuditLog
from app.models.constraint import PersonConstraint
from app.models.enums import (
    BuildingType,
    ImportBatchStatus,
    PersonStatus,
    UserRole,
)
from app.models.import_batch import ImportBatch
from app.models.person import PersonProfile
from app.models.semester import BuildingCodeRule, CoursePeriodRule, Semester
from app.models.user import User
from app.models.vacation import VacationAvailability, VacationPeriod

__all__ = [
    "Base",
    "AuditLog",
    "ImportBatch",
    "PersonProfile",
    "PersonConstraint",
    "User",
    "Semester",
    "CoursePeriodRule",
    "BuildingCodeRule",
    "VacationPeriod",
    "VacationAvailability",
    "UserRole",
    "PersonStatus",
    "ImportBatchStatus",
    "BuildingType",
]
