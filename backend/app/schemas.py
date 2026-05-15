"""
Pydantic schemas for request validation and response serialization.
Every API endpoint uses these schemas — no raw dicts.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


# ── ENUMS ──────────────────────────────────────────

class RoleEnum(str, Enum):
    admin = "admin"
    teacher = "teacher"
    student = "student"


class StatusEnum(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


# ════════════════════════════════════════════════════
#  AUTH SCHEMAS
# ════════════════════════════════════════════════════

class SignupRequest(BaseModel):
    """Student self-registration request."""
    name: str = Field(..., min_length=3, max_length=100, description="Full name")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password, min 8 chars")
    semester: int = Field(..., ge=1, le=8, description="Semester 1–8")
    department: str = Field(..., min_length=2, max_length=100, description="Department name")


class LoginRequest(BaseModel):
    """Login request for Admin, Teacher, and Student."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response after successful login."""
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    name: str
    email: str
    semester: int
    department: str
    subject: Optional[str] = None  # For teachers and students who have selected a subject


# ════════════════════════════════════════════════════
#  ADMIN SCHEMAS
# ════════════════════════════════════════════════════

class AdminTeacherCreate(BaseModel):
    """Admin creates a teacher with all required fields."""
    name: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    department: str = Field(..., min_length=2, max_length=100)
    semester: int = Field(..., ge=1, le=8)
    subject: str = Field(..., min_length=2, max_length=100)


class AdminTeacherUpdate(BaseModel):
    """Admin updates a teacher — all fields optional."""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    department: Optional[str] = Field(None, min_length=2, max_length=100)
    semester: Optional[int] = Field(None, ge=1, le=8)
    subject: Optional[str] = Field(None, min_length=2, max_length=100)


class TeacherOut(BaseModel):
    """Teacher info for admin view."""
    id: int
    name: str
    email: str
    department: str
    semester: int
    subject: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ════════════════════════════════════════════════════
#  STUDENT SCHEMAS
# ════════════════════════════════════════════════════

class StudentOut(BaseModel):
    """Student info in teacher's student list."""
    id: int
    name: str
    email: str
    department: str
    semester: int
    subject: Optional[str] = None

    class Config:
        from_attributes = True


class SubjectSelectRequest(BaseModel):
    """Student selects a subject from available list."""
    subject: str = Field(..., min_length=2, max_length=100)


class AvailableSubjectItem(BaseModel):
    """A subject available for student selection."""
    subject: str
    teacher_name: str
    teacher_id: int


class TeacherInfoOut(BaseModel):
    """Info about student's assigned teacher."""
    teacher_id: int
    teacher_name: str
    teacher_email: str
    subject: str
    department: str
    semester: int


# ════════════════════════════════════════════════════
#  ATTENDANCE SCHEMAS
# ════════════════════════════════════════════════════

class AttendanceRecord(BaseModel):
    """Single student attendance entry in a bulk submission."""
    student_id: int
    status: StatusEnum


class AttendanceSubmit(BaseModel):
    """Bulk attendance submission for a date."""
    date: date
    records: List[AttendanceRecord] = Field(..., min_length=1)


class AttendanceUpdate(BaseModel):
    """Update a single attendance record's status."""
    status: StatusEnum


class AttendanceOut(BaseModel):
    """Single attendance record response."""
    id: int
    student_id: int
    student_name: Optional[str] = None
    teacher_id: int
    subject_name: Optional[str] = None
    semester: int
    date: date
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ════════════════════════════════════════════════════
#  STUDENT DASHBOARD SCHEMAS
# ════════════════════════════════════════════════════

class AttendanceSummaryItem(BaseModel):
    """Subject-wise attendance summary for a student."""
    subject_name: str
    teacher_name: str
    present: int
    absent: int
    total: int
    percentage: float


class AttendanceSummaryResponse(BaseModel):
    """Full attendance summary response."""
    subjects: List[AttendanceSummaryItem]
    overall_present: int
    overall_absent: int
    overall_total: int
    overall_percentage: float


class PDFRequest(BaseModel):
    """Request params for monthly PDF download."""
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020, le=2100)


# ════════════════════════════════════════════════════
#  FEEDBACK SCHEMAS
# ════════════════════════════════════════════════════

class FeedbackCreate(BaseModel):
    """Submit feedback for a teacher."""
    teacher_id: int
    rating: int = Field(..., ge=1, le=5, description="1=Very Poor, 5=Excellent")
    comment: str = Field(..., min_length=10, description="Minimum 10 characters")


class FeedbackOut(BaseModel):
    """Feedback record response."""
    id: int
    student_id: int
    teacher_id: int
    teacher_name: Optional[str] = None
    rating: int
    comment: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ════════════════════════════════════════════════════
#  GENERIC
# ════════════════════════════════════════════════════

class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    detail: Optional[str] = None
