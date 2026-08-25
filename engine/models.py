"""
Pure Python Domain Models for Placement Week Scheduler.
Decoupled from storage and framework dependencies.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any


class PriorityTier(Enum):
    MASS_RECRUITER = 1
    MID_TIER = 2
    NICHE = 3
    DREAM = 4


class InterviewStatus(Enum):
    SCHEDULED = "SCHEDULED"
    UNSCHEDULED = "UNSCHEDULED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class DisruptionType(Enum):
    COMPANY_DELAY = "COMPANY_DELAY"
    PANEL_DROPOUT = "PANEL_DROPOUT"
    STUDENT_WITHDRAWAL = "STUDENT_WITHDRAWAL"
    ROOM_UNAVAILABLE = "ROOM_UNAVAILABLE"


@dataclass
class Company:
    id: str
    name: str
    priority_tier: PriorityTier
    interview_day_mask: List[int]  # e.g. [1] or [2, 3]
    interview_duration_mins: int
    panel_count: int
    cgpa_cutoff: float


@dataclass
class Student:
    id: str
    name: str
    cgpa: float
    branch: str
    shortlisted_company_ids: List[str] = field(default_factory=list)


@dataclass
class Panel:
    id: str
    company_id: str
    panel_number: int


@dataclass
class Room:
    id: str
    name: str
    capacity: int = 4
    has_whiteboard: bool = True
    has_projector: bool = False


@dataclass
class TimeSlot:
    id: str
    day: int
    start_time: str  # "09:00"
    end_time: str    # "09:30"
    duration_mins: int
    slot_index: int


@dataclass
class Interview:
    id: str
    student_id: str
    company_id: str
    panel_id: Optional[str] = None
    room_id: Optional[str] = None
    slot_id: Optional[str] = None
    status: InterviewStatus = InterviewStatus.UNSCHEDULED
    unplacement_reason: Optional[str] = None

    def is_placed(self) -> bool:
        return self.status == InterviewStatus.SCHEDULED and self.slot_id is not None and self.panel_id is not None and self.room_id is not None


@dataclass
class Schedule:
    id: str
    scheduled_interviews: List[Interview] = field(default_factory=list)
    unscheduled_interviews: List[Interview] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DisruptionEvent:
    id: str
    type: DisruptionType
    timestamp: str
    payload: Dict[str, Any]
    status: str = "PENDING"
