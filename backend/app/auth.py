"""
Authentication utilities — password hashing, JWT tokens, and FastAPI dependencies.

Security:
  - Bcrypt with 12 salt rounds for password hashing
  - HS256 JWT tokens with configurable expiry (default 24h)
  - Role-based dependencies: require_admin, require_teacher, require_student
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()

# ── PASSWORD HASHING ───────────────────────────────

def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using Bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a Bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


# ── JWT TOKEN ──────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    Payload includes user data + expiry timestamp.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=settings.JWT_EXPIRY_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    Raises HTTPException if token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FASTAPI DEPENDENCIES ──────────────────────────

# Bearer token security scheme
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate the current user from the JWT token.
    Used as a dependency on all protected endpoints.
    For admin: returns None user (admin is not in DB), but role is checked from token.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    role = payload.get("role")

    # Admin is not in the database — return a virtual admin user object
    if role == "admin":
        from app.models import UserRole
        admin_user = User(
            id=0,
            name="Admin",
            email=payload.get("email", "admin"),
            password_hash="",
            role=UserRole.admin,
            department="Administration",
            semester=1,
        )
        # Don't add to session — this is a virtual object
        return admin_user

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that ensures the current user is an admin.
    Returns 403 if the user is not an admin.
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required.",
        )
    return current_user


def require_teacher(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that ensures the current user is a teacher.
    Returns 403 if the user is not a teacher.
    """
    if current_user.role.value != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Teacher role required.",
        )
    return current_user


def require_student(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that ensures the current user is a student.
    Returns 403 if the user is not a student.
    """
    if current_user.role.value != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Student role required.",
        )
    return current_user
