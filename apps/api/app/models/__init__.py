"""集中导入全部 ORM 模型，确保 Base.metadata 完整。"""

from app.db.base import Base
from app.models.audit import AuditLog
from app.models.availability import AvailabilityBlock, AvailabilityRequest
from app.models.config import SystemSetting
from app.models.constraint import PersonConstraint
from app.models.enums import (
    AssignmentSource,
    AvailabilitySource,
    AvailabilityStatus,
    BuildingType,
    DayType,
    ExecutionStatus,
    ImportBatchStatus,
    LeaveStatus,
    MonthlySummaryStatus,
    ParseStatus,
    PersonStatus,
    PlanAssignmentStatus,
    PlanStatus,
    RequestStatus,
    ReviewStatus,
    SlotSourceType,
    SlotStatus,
    SpecialDateSource,
    SwapCandidateStatus,
    SwapMode,
    SwapStatus,
    TaskStatus,
    UserRole,
    VenueType,
)
from app.models.import_batch import ImportBatch
from app.models.leave import LeaveRequest
from app.models.multiplier import MultiplierRule
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot, WeeklyPlan
from app.models.statistics import (
    HourAdjustment,
    MonthlyHourSummary,
    MonthlyVenueHourSummary,
)
from app.models.swap import SwapCandidate, SwapRequest
from app.models.overtime import OvertimeRequest
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
    "SystemSetting",
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
    "WeeklyPlan",
    "DutySlot",
    "Assignment",
    "LeaveRequest",
    "SwapRequest",
    "OvertimeRequest",
    "SwapCandidate",
    "MonthlyHourSummary",
    "MonthlyVenueHourSummary",
    "HourAdjustment",
    "MonthlySummaryStatus",
    "LeaveStatus",
    "SwapMode",
    "SwapStatus",
    "SwapCandidateStatus",
    "PlanStatus",
    "SlotSourceType",
    "SlotStatus",
    "AssignmentSource",
    "PlanAssignmentStatus",
    "ExecutionStatus",
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
