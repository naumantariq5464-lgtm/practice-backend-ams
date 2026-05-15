"""
Student Router — Subject Selection, Attendance View, Summary, Feedback, PDF Download.

All endpoints require Student JWT authentication.
All queries enforce student_id and semester isolation at ORM level.
"""

from typing import Optional
from io import BytesIO
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, UserRole, Attendance, AttendanceStatus, Feedback as FeedbackModel
from app.schemas import (
    AttendanceOut, AttendanceSummaryItem, AttendanceSummaryResponse,
    FeedbackCreate, FeedbackOut, MessageResponse,
    AvailableSubjectItem, SubjectSelectRequest, TeacherInfoOut,
)
from app.auth import require_student
from app.pdf_generator import generate_attendance_pdf

router = APIRouter(prefix="/api/student", tags=["Student"])


# ════════════════════════════════════════════════════
#  SUBJECT SELECTION & TEACHER INFO
# ════════════════════════════════════════════════════

@router.get("/subjects", response_model=list[AvailableSubjectItem])
def get_available_subjects(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Get subjects available for this student based on their department + semester.
    These subjects come from teachers who match the student's dept + sem.
    """
    teachers = (
        db.query(User)
        .filter(
            User.role == UserRole.teacher,
            User.department == current_user.department,
            User.semester == current_user.semester,
            User.subject.isnot(None),
        )
        .all()
    )

    return [
        AvailableSubjectItem(
            subject=t.subject,
            teacher_name=t.name,
            teacher_id=t.id,
        )
        for t in teachers
    ]


@router.put("/subject", response_model=MessageResponse)
def select_subject(
    data: SubjectSelectRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Student selects a subject. This auto-links them to the matching teacher.
    The subject must exist (i.e., a teacher with matching dept+sem+subject must exist).
    """
    # Verify a teacher exists for this subject in student's dept+sem
    teacher = db.query(User).filter(
        User.role == UserRole.teacher,
        User.department == current_user.department,
        User.semester == current_user.semester,
        User.subject == data.subject,
    ).first()

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No teacher found for subject '{data.subject}' in your department and semester.",
        )

    # Link student to subject
    current_user.subject = data.subject
    db.commit()

    return MessageResponse(
        message=f"Subject '{data.subject}' selected. You are now linked to {teacher.name}.",
        detail=f"Teacher: {teacher.name} ({teacher.email})",
    )


@router.get("/teacher", response_model=TeacherInfoOut)
def get_my_teacher(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Get the student's assigned teacher based on dept + sem + subject match."""
    if not current_user.subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You haven't selected a subject yet. Please select a subject first.",
        )

    teacher = db.query(User).filter(
        User.role == UserRole.teacher,
        User.department == current_user.department,
        User.semester == current_user.semester,
        User.subject == current_user.subject,
    ).first()

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No teacher found for your subject. Please contact administration.",
        )

    return TeacherInfoOut(
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        teacher_email=teacher.email,
        subject=teacher.subject,
        department=teacher.department,
        semester=teacher.semester,
    )


# ════════════════════════════════════════════════════
#  ATTENDANCE VIEW
# ════════════════════════════════════════════════════

@router.get("/attendance", response_model=list[AttendanceOut])
def get_my_attendance(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Get all attendance records for the logged-in student.
    Filtered by student's semester.
    """
    records = (
        db.query(Attendance)
        .filter(
            Attendance.student_id == current_user.id,
            Attendance.semester == current_user.semester,
        )
        .order_by(Attendance.date.desc())
        .all()
    )

    result = []
    for r in records:
        teacher = db.query(User).filter(User.id == r.teacher_id).first()
        result.append(AttendanceOut(
            id=r.id,
            student_id=r.student_id,
            student_name=current_user.name,
            teacher_id=r.teacher_id,
            subject_name=r.subject_name,
            semester=r.semester,
            date=r.date,
            status=r.status.value,
            created_at=r.created_at,
        ))

    return result


# ════════════════════════════════════════════════════
#  ATTENDANCE SUMMARY (PERCENTAGE)
# ════════════════════════════════════════════════════

@router.get("/attendance/summary", response_model=AttendanceSummaryResponse)
def get_attendance_summary(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Get subject-wise attendance percentage summary.
    Formula: (Present Days / Total Days) × 100 per subject.
    """
    # Get all teachers for this student's department + semester
    teachers = (
        db.query(User)
        .filter(
            User.role == UserRole.teacher,
            User.department == current_user.department,
            User.semester == current_user.semester,
            User.subject.isnot(None),
        )
        .all()
    )

    subjects = []
    overall_present = 0
    overall_absent = 0

    for teacher in teachers:
        # Count present and absent
        present_count = (
            db.query(func.count(Attendance.id))
            .filter(
                Attendance.student_id == current_user.id,
                Attendance.teacher_id == teacher.id,
                Attendance.semester == current_user.semester,
                Attendance.status == AttendanceStatus.PRESENT,
            )
            .scalar()
        )

        absent_count = (
            db.query(func.count(Attendance.id))
            .filter(
                Attendance.student_id == current_user.id,
                Attendance.teacher_id == teacher.id,
                Attendance.semester == current_user.semester,
                Attendance.status == AttendanceStatus.ABSENT,
            )
            .scalar()
        )

        total = present_count + absent_count
        percentage = round((present_count / total) * 100, 2) if total > 0 else 0.0

        subjects.append(AttendanceSummaryItem(
            subject_name=teacher.subject,
            teacher_name=teacher.name,
            present=present_count,
            absent=absent_count,
            total=total,
            percentage=percentage,
        ))

        overall_present += present_count
        overall_absent += absent_count

    overall_total = overall_present + overall_absent
    overall_pct = round((overall_present / overall_total) * 100, 2) if overall_total > 0 else 0.0

    return AttendanceSummaryResponse(
        subjects=subjects,
        overall_present=overall_present,
        overall_absent=overall_absent,
        overall_total=overall_total,
        overall_percentage=overall_pct,
    )


# ════════════════════════════════════════════════════
#  FEEDBACK
# ════════════════════════════════════════════════════

@router.post("/feedback", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    data: FeedbackCreate,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Submit feedback for a teacher (rating 1–5 + comment).
    Feedback is immutable after submission.
    """
    # Validate teacher exists and is actually a teacher
    teacher = db.query(User).filter(
        User.id == data.teacher_id,
        User.role == UserRole.teacher,
    ).first()

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found.",
        )

    # Create feedback
    feedback = FeedbackModel(
        student_id=current_user.id,
        teacher_id=data.teacher_id,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(feedback)
    db.commit()

    return MessageResponse(
        message="Feedback submitted successfully. Thank you!",
        detail=f"Teacher: {teacher.name}, Rating: {data.rating}/5",
    )


@router.get("/feedback", response_model=list[FeedbackOut])
def get_my_feedback(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Get all feedback submitted by this student."""
    feedbacks = (
        db.query(FeedbackModel)
        .filter(FeedbackModel.student_id == current_user.id)
        .order_by(FeedbackModel.created_at.desc())
        .all()
    )

    result = []
    for f in feedbacks:
        teacher = db.query(User).filter(User.id == f.teacher_id).first()
        result.append(FeedbackOut(
            id=f.id,
            student_id=f.student_id,
            teacher_id=f.teacher_id,
            teacher_name=teacher.name if teacher else "Unknown",
            rating=f.rating,
            comment=f.comment,
            created_at=f.created_at,
        ))

    return result


# ════════════════════════════════════════════════════
#  PDF DOWNLOAD
# ════════════════════════════════════════════════════

@router.get("/attendance/pdf")
def download_attendance_pdf(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Generate and download monthly attendance PDF report.
    Filters attendance records by student, semester, month, and year.
    Only strictly completed months can be downloaded.
    """
    now = datetime.now()
    if year > now.year or (year == now.year and month >= now.month):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can only download reports for completed months. Please wait until this month ends."
        )

    # Get attendance records for the specified month
    records = (
        db.query(Attendance)
        .filter(
            Attendance.student_id == current_user.id,
            Attendance.semester == current_user.semester,
            func.extract("month", Attendance.date) == month,
            func.extract("year", Attendance.date) == year,
        )
        .all()
    )

    # Aggregate by subject_name
    subject_data = {}
    
    # Pre-populate with all teachers in dept and sem so even 0 attendance subjects show up
    teachers = db.query(User).filter(
        User.role == UserRole.teacher,
        User.department == current_user.department,
        User.semester == current_user.semester,
        User.subject.isnot(None)
    ).all()
    
    for t in teachers:
        subject_data[t.subject] = {
            "subject_name": t.subject,
            "teacher_name": t.name,
            "present": 0,
            "absent": 0,
        }

    for r in records:
        if r.subject_name not in subject_data:
            teacher = db.query(User).filter(User.id == r.teacher_id).first()
            subject_data[r.subject_name] = {
                "subject_name": r.subject_name,
                "teacher_name": teacher.name if teacher else "Unknown",
                "present": 0,
                "absent": 0,
            }

        if r.status == AttendanceStatus.PRESENT:
            subject_data[r.subject_name]["present"] += 1
        else:
            subject_data[r.subject_name]["absent"] += 1

    # Build data list for PDF
    pdf_rows = []
    for sname, data in subject_data.items():
        total = data["present"] + data["absent"]
        pct = round((data["present"] / total) * 100, 2) if total > 0 else 0.0
        pdf_rows.append({
            "subject": data["subject_name"],
            "teacher": data["teacher_name"],
            "present": data["present"],
            "absent": data["absent"],
            "total": total,
            "percentage": pct,
        })

    # Student info for the header
    student_info = {
        "name": current_user.name,
        "email": current_user.email,
        "semester": current_user.semester,
        "department": current_user.department,
    }

    # Generate PDF
    pdf_buffer = generate_attendance_pdf(
        student_info=student_info,
        month=month,
        year=year,
        rows=pdf_rows,
    )

    # Return as downloadable file
    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    filename = f"AMS_Attendance_{current_user.name.replace(' ', '_')}_{month_names[month]}_{year}.pdf"

    return StreamingResponse(
        BytesIO(pdf_buffer),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
