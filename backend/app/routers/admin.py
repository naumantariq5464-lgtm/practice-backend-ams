"""
Admin Router — Teacher Management.

All endpoints require Admin JWT authentication.

POST   /api/admin/teachers     — Create a new teacher
GET    /api/admin/teachers     — List all teachers
DELETE /api/admin/teachers/{id} — Remove a teacher
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.schemas import AdminTeacherCreate, AdminTeacherUpdate, TeacherOut, MessageResponse
from app.auth import require_admin, hash_password

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ════════════════════════════════════════════════════
#  CREATE TEACHER
# ════════════════════════════════════════════════════

@router.post("/teachers", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
def create_teacher(
    data: AdminTeacherCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin creates a new teacher account.
    Sets role to 'teacher' automatically — cannot be overridden.
    """
    # Check if email already exists
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email '{data.email}' already exists.",
        )

    # Create teacher user
    teacher = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=UserRole.teacher,
        department=data.department,
        semester=data.semester,
        subject=data.subject,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)

    return TeacherOut.model_validate(teacher)


# ════════════════════════════════════════════════════
#  LIST TEACHERS
# ════════════════════════════════════════════════════

@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all teacher accounts."""
    teachers = (
        db.query(User)
        .filter(User.role == UserRole.teacher)
        .order_by(User.created_at.desc())
        .all()
    )
    return [TeacherOut.model_validate(t) for t in teachers]


# ════════════════════════════════════════════════════
#  DELETE TEACHER
# ════════════════════════════════════════════════════

@router.delete("/teachers/{teacher_id}", response_model=MessageResponse)
def delete_teacher(
    teacher_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a teacher account.
    All associated attendance records will be cascade-deleted.
    """
    teacher = db.query(User).filter(
        User.id == teacher_id,
        User.role == UserRole.teacher,
    ).first()

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found.",
        )

    name = teacher.name
    db.delete(teacher)
    db.commit()

    return MessageResponse(message=f"Teacher '{name}' has been removed.")


# ════════════════════════════════════════════════════
#  UPDATE TEACHER
# ════════════════════════════════════════════════════

@router.put("/teachers/{teacher_id}", response_model=TeacherOut)
def update_teacher(
    teacher_id: int,
    data: AdminTeacherUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin updates a teacher's info.
    Only provided (non-None) fields are updated.
    """
    teacher = db.query(User).filter(
        User.id == teacher_id,
        User.role == UserRole.teacher,
    ).first()

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found.",
        )

    # Check email uniqueness if being changed
    if data.email and data.email != teacher.email:
        existing = db.query(User).filter(User.email == data.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An account with email '{data.email}' already exists.",
            )
        teacher.email = data.email

    if data.name is not None:
        teacher.name = data.name
    if data.department is not None:
        teacher.department = data.department
    if data.semester is not None:
        teacher.semester = data.semester
    if data.subject is not None:
        teacher.subject = data.subject
    if data.password is not None:
        teacher.password_hash = hash_password(data.password)

    db.commit()
    db.refresh(teacher)

    return TeacherOut.model_validate(teacher)
