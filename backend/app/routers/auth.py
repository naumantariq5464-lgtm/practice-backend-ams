"""
Authentication Router — Login & Signup endpoints.

POST /api/auth/signup   — Student self-registration
POST /api/auth/login    — Login for Admin, Teacher, and Student
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.schemas import SignupRequest, LoginRequest, TokenResponse
from app.auth import hash_password, verify_password, create_access_token
from app.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ── STUDENT SIGNUP ────────────────────────────────

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """
    Student self-registration.
    - Teachers cannot self-register (created by admin).
    - Admin cannot self-register (hardcoded credentials).
    - Email must be unique.
    - Role is always set to 'student' by backend.
    """
    # Check if email already exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Prevent using admin email for student signup
    if request.email.lower() == settings.ADMIN_EMAIL.lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is reserved.",
        )

    # Create new student user (role is ALWAYS student — never trust frontend)
    new_user = User(
        name=request.name,
        email=request.email,
        password_hash=hash_password(request.password),
        role=UserRole.student,
        semester=request.semester,
        department=request.department,
        subject=None,  # Student picks subject later on dashboard
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate JWT token
    token = create_access_token(data={
        "user_id": new_user.id,
        "email": new_user.email,
        "role": new_user.role.value,
    })

    return TokenResponse(
        access_token=token,
        role=new_user.role.value,
        user_id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        semester=new_user.semester,
        department=new_user.department,
        subject=new_user.subject,
    )


# ── LOGIN ─────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login for Admin, Teacher, and Student.
    Admin is checked first via hardcoded credentials (if condition).
    Then checks database for teacher/student.
    Returns JWT token + user info.
    """
    # ── ADMIN CHECK — hardcoded if condition ──
    if request.email.lower() == settings.ADMIN_EMAIL.lower():
        # Verify admin password against stored hash
        if settings.ADMIN_PASSWORD_HASH and verify_password(request.password, settings.ADMIN_PASSWORD_HASH):
            token = create_access_token(data={
                "user_id": 0,
                "email": settings.ADMIN_EMAIL,
                "role": "admin",
            })
            return TokenResponse(
                access_token=token,
                role="admin",
                user_id=0,
                name="Admin",
                email=settings.ADMIN_EMAIL,
                semester=1,
                department="Administration",
                subject=None,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

    # ── REGULAR USER CHECK (Teacher / Student) ──
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Generate JWT token
    token = create_access_token(data={
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value,
    })

    return TokenResponse(
        access_token=token,
        role=user.role.value,
        user_id=user.id,
        name=user.name,
        email=user.email,
        semester=user.semester,
        department=user.department,
        subject=user.subject,
    )
