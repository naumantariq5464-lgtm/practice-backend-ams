"""
SQLAlchemy ORM models — maps to all 3 database tables.

Tables:
  - users            (Admin + Teachers + Students)
  - attendance        (Attendance records)
  - feedback          (Student → Teacher feedback)
"""

import enum
from datetime import datetime, date, timezone

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Enum, Text,
    ForeignKey, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ── ENUMS ──────────────────────────────────────────

class UserRole(str, enum.Enum):
    """User role — determines dashboard and permissions."""
    admin = "admin"
    teacher = "teacher"
    student = "student"


class AttendanceStatus(str, enum.Enum):
    """Attendance status for a single record."""
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


# ── USERS TABLE ────────────────────────────────────

class User(Base):
    """
    Stores admins, teachers, and students.
    The 'role' field determines access level and dashboard type.
    'subject' is assigned by admin (for teachers) or selected by student.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    department = Column(String(100), nullable=False)
    semester = Column(Integer, nullable=False)
    subject = Column(String(100), nullable=True)  # Set by admin for teachers, selected by students
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Check constraint: semester must be 1–8
    __table_args__ = (
        CheckConstraint("semester >= 1 AND semester <= 8", name="ck_users_semester_range"),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


# ── ATTENDANCE TABLE ────────────────────────────────

class Attendance(Base):
    """
    Individual attendance record. Uniquely identified by the combination of
    (student_id, teacher_id, date).
    subject_name stored as string for historical reference.
    """
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_name = Column(String(100), nullable=False)
    semester = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    status = Column(Enum(AttendanceStatus), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Unique constraint prevents duplicate entries
    __table_args__ = (
        UniqueConstraint(
            "student_id", "teacher_id", "date",
            name="uq_attendance_record"
        ),
        CheckConstraint("semester >= 1 AND semester <= 8", name="ck_attendance_semester_range"),
    )

    # Relationships
    student = relationship("User", foreign_keys=[student_id])
    teacher = relationship("User", foreign_keys=[teacher_id])

    def __repr__(self):
        return f"<Attendance(student={self.student_id}, teacher={self.teacher_id}, date={self.date}, status={self.status})>"


# ── FEEDBACK TABLE ──────────────────────────────────

class Feedback(Base):
    """
    Student-to-teacher feedback. One-way, immutable after submission.
    """
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Check constraint: rating 1–5
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_feedback_rating_range"),
    )

    # Relationships
    student = relationship("User", foreign_keys=[student_id])
    teacher = relationship("User", foreign_keys=[teacher_id])

    def __repr__(self):
        return f"<Feedback(student={self.student_id}, teacher={self.teacher_id}, rating={self.rating})>"
