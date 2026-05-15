"""
Teacher Router — Student List, Attendance CRUD.

All endpoints require Teacher JWT authentication.
All queries enforce teacher isolation: only students matching
the teacher's department + semester + subject are visible.
"""

from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, Attendance, AttendanceStatus, Feedback
from app.schemas import (
    StudentOut, AttendanceSubmit, AttendanceUpdate,
    AttendanceOut, MessageResponse,
)
from app.auth import require_teacher

router = APIRouter(prefix="/api/teacher", tags=["Teacher"])


# ════════════════════════════════════════════════════
#  PROFILE / INFO
# ════════════════════════════════════════════════════

@router.get("/profile")
def get_profile(current_user: User = Depends(require_teacher)):
    """Get current teacher's profile information."""
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "department": current_user.department,
        "semester": current_user.semester,
        "subject": current_user.subject,
    }


# ════════════════════════════════════════════════════
#  STUDENT LIST (Auto-linked by dept + sem + subject)
# ════════════════════════════════════════════════════

@router.get("/students", response_model=list[StudentOut])
def get_students(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """
    Get all students linked to this teacher.
    Linking is automatic — students must match:
      - Same department
      - Same semester
      - Same subject
    This ensures complete teacher isolation.
    """
    students = (
        db.query(User)
        .filter(
            User.role == UserRole.student,
            User.department == current_user.department,
            User.semester == current_user.semester,
        )
        .order_by(User.name)
        .all()
    )
    return [StudentOut.model_validate(s) for s in students]


# ════════════════════════════════════════════════════
#  ATTENDANCE
# ════════════════════════════════════════════════════

@router.post("/attendance", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def submit_attendance(
    data: AttendanceSubmit,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """
    Submit bulk attendance for a date.
    Subject is automatically the teacher's assigned subject.
    Cannot mark attendance for future dates.
    Only students matching this teacher's dept+sem+subject can be marked.
    """
    # Validate: no future dates
    if data.date > date_type.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mark attendance for future dates.",
        )

    created = 0
    updated = 0

    for record in data.records:
        # Validate student belongs to this teacher's group
        student = db.query(User).filter(
            User.id == record.student_id,
            User.role == UserRole.student,
            User.department == current_user.department,
            User.semester == current_user.semester,
        ).first()

        if not student:
            continue  # Skip invalid students silently

        # Check for existing record (upsert)
        existing = db.query(Attendance).filter(
            Attendance.student_id == record.student_id,
            Attendance.teacher_id == current_user.id,
            Attendance.date == data.date,
        ).first()

        if existing:
            existing.status = AttendanceStatus(record.status.value)
            updated += 1
        else:
            att = Attendance(
                student_id=record.student_id,
                teacher_id=current_user.id,
                subject_name=current_user.subject,
                semester=current_user.semester,
                date=data.date,
                status=AttendanceStatus(record.status.value),
            )
            db.add(att)
            created += 1

    db.commit()

    return MessageResponse(
        message=f"Attendance saved: {created} new, {updated} updated.",
        detail=f"Date: {data.date}, Subject: {current_user.subject}",
    )


@router.get("/attendance", response_model=list[AttendanceOut])
def get_attendance_records(
    date: Optional[date_type] = Query(None, description="Filter by date"),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """
    Get all attendance records submitted by this teacher.
    Teacher can ONLY see their own records — complete isolation.
    """
    query = (
        db.query(Attendance)
        .filter(Attendance.teacher_id == current_user.id)
    )

    if date:
        query = query.filter(Attendance.date == date)

    records = query.order_by(Attendance.date.desc(), Attendance.student_id).all()

    result = []
    for r in records:
        student = db.query(User).filter(User.id == r.student_id).first()
        result.append(AttendanceOut(
            id=r.id,
            student_id=r.student_id,
            student_name=student.name if student else "Unknown",
            teacher_id=r.teacher_id,
            subject_name=r.subject_name,
            semester=r.semester,
            date=r.date,
            status=r.status.value,
            created_at=r.created_at,
        ))

    return result


@router.put("/attendance/{record_id}", response_model=MessageResponse)
def update_attendance(
    record_id: int,
    data: AttendanceUpdate,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Update a specific attendance record (teacher can only update their OWN records)."""
    record = db.query(Attendance).filter(
        Attendance.id == record_id,
        Attendance.teacher_id == current_user.id,
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found or you don't own it.",
        )

    record.status = AttendanceStatus(data.status.value)
    db.commit()

    return MessageResponse(message=f"Attendance record #{record_id} updated to {data.status.value}.")


@router.delete("/attendance/{record_id}", response_model=MessageResponse)
def delete_attendance(
    record_id: int,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Delete a specific attendance record (teacher can only delete their OWN records)."""
    record = db.query(Attendance).filter(
        Attendance.id == record_id,
        Attendance.teacher_id == current_user.id,
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found or you don't own it.",
        )

    db.delete(record)
    db.commit()

    return MessageResponse(message=f"Attendance record #{record_id} deleted.")


# ════════════════════════════════════════════════════
#  DELETE STUDENT
# ════════════════════════════════════════════════════

@router.delete("/students/{student_id}", response_model=MessageResponse)
def delete_student(
    student_id: int,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """
    Delete a student from the teacher's group.
    Only students matching this teacher's department + semester + subject can be deleted.
    Associated attendance and feedback records are also removed.
    """
    student = db.query(User).filter(
        User.id == student_id,
        User.role == UserRole.student,
        User.department == current_user.department,
        User.semester == current_user.semester,
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found or does not belong to your group.",
        )

    name = student.name
    db.delete(student)
    db.commit()

    return MessageResponse(message=f"Student '{name}' has been removed.")


# ════════════════════════════════════════════════════
#  FEEDBACK RECEIVED (from students)
# ════════════════════════════════════════════════════

@router.get("/feedback")
def get_my_feedback(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """
    Get all feedback submitted by students for this teacher.
    Teacher can only see feedback addressed to them — complete isolation.
    """
    feedbacks = (
        db.query(Feedback)
        .filter(Feedback.teacher_id == current_user.id)
        .order_by(Feedback.created_at.desc())
        .all()
    )

    result = []
    for f in feedbacks:
        student = db.query(User).filter(User.id == f.student_id).first()
        result.append({
            "id": f.id,
            "student_id": f.student_id,
            "student_name": student.name if student else "Unknown",
            "student_email": student.email if student else "",
            "teacher_id": f.teacher_id,
            "rating": f.rating,
            "comment": f.comment,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })

    return result

