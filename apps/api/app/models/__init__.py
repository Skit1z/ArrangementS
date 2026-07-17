"""集中导入全部 ORM 模型，确保 Base.metadata 完整。"""
from app.db.base import Base
from app.models.audit import AuditLog
from app.models.availability import AvailabilityBlock, AvailabilityRequest
from app.models.constraint import PersonConstraint
from app.models.enums import (
    AvailabilitySource,
    AvailabilityStatus,
    BuildingType,
    DayType,
    ImportBatchStatus,
    ParseStatus,
    PersonStatus,
    RequestStatus,
    ReviewStatus,
    SpecialDateSource,
    TaskStatus,
    UserRole,
    VenueType,
)
from app.models.import_batch import ImportBatch
from app.models.multiplier import MultiplierRule
from app.models.person import PersonProfile
from app.models.semester import BuildingCodeRule, CoursePeriodRule, Semester
from app.models.special_date import SpecialDate
from app.models.timetable import CourseRule, TimetableUpload
from app.models.user import User
from app.models.vacation import VacationAvailability, VacationPeriod
from app.models.venue import ShiftTemplate, Venue
from app.models.venue_task import VenueTask

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
    "TimetableUpload",
    "CourseRule",
    "AvailabilityBlock",
    "AvailabilityRequest",
    "Venue",
    "ShiftTemplate",
    "SpecialDate",
    "VenueTask",
    "MultiplierRule",
    "UserRole",
    "PersonStatus",
    "ImportBatchStatus",
    "BuildingType",
    "ParseStatus",
    "ReviewStatus",
    "AvailabilitySource",
    "AvailabilityStatus",
    "RequestStatus",
    "VenueType",
    "DayType",
    "SpecialDateSource",
    "TaskStatus",
]
