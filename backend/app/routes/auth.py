from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime, timedelta
from app.models.db import AuthSession, Doctor
from sqlalchemy.orm import Session
from app.config import COOKIE_SECURE, SESSION_COOKIE_NAME, SESSION_TTL_HOURS

from app.database import get_db
from app.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)


router = APIRouter()

class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value:str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Full name is required")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

class DoctorResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    created_at: datetime

@router.post(
    "/signup",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(signup_data: SignupRequest, db: Session = Depends(get_db)):
    email = str(signup_data.email)

    existing_doctor = (
        db.query(Doctor)
        .filter(Doctor.email == email)
        .first()
    )

    if existing_doctor:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    doctor = Doctor(
        full_name=signup_data.full_name,
        email=email,
        password_hash=hash_password(signup_data.password),
    )

    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    return DoctorResponse(
        id=doctor.id,
        full_name=doctor.full_name,
        email=doctor.email,
        created_at=doctor.created_at,
    )

@router.post("/login", response_model=DoctorResponse)
def login(
    login_data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email = str(login_data.email)

    doctor = (
        db.query(Doctor)
        .filter(Doctor.email == email)
        .first()
    )

    if (
        not doctor
        or not doctor.is_active
        or not verify_password(login_data.password, doctor.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    raw_token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)

    auth_session = AuthSession(
        doctor_id=doctor.id,
        token_hash=hash_session_token(raw_token),
        expires_at=expires_at,
    )

    db.add(auth_session)
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL_HOURS * 60 * 60,
        path="/",
    )

    return DoctorResponse(
        id=doctor.id,
        full_name=doctor.full_name,
        email=doctor.email,
        created_at=doctor.created_at,
    )

def get_current_doctor(
    session_token: str | None = Cookie(
        default=None,
        alias=SESSION_COOKIE_NAME,
    ),
    db: Session = Depends(get_db),
) -> Doctor:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    auth_session = (
        db.query(AuthSession)
        .filter(
            AuthSession.token_hash == hash_session_token(session_token),
            AuthSession.revoked_at.is_(None),
        )
        .first()
    )

    if not auth_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again.",
        )

    if auth_session.expires_at <= datetime.utcnow():
        auth_session.revoked_at = datetime.utcnow()
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again.",
        )

    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.id == auth_session.doctor_id,
            Doctor.is_active.is_(True),
        )
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again.",
        )

    return doctor


@router.get("/me", response_model=DoctorResponse)
def get_me(current_doctor: Doctor = Depends(get_current_doctor)):
    return DoctorResponse(
        id=current_doctor.id,
        full_name=current_doctor.full_name,
        email=current_doctor.email,
        created_at=current_doctor.created_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session_token: str | None = Cookie(
        default=None,
        alias=SESSION_COOKIE_NAME,
    ),
    db: Session = Depends(get_db),
):
    if session_token:
        auth_session = (
            db.query(AuthSession)
            .filter(
                AuthSession.token_hash == hash_session_token(session_token),
                AuthSession.revoked_at.is_(None),
            )
            .first()
        )

        if auth_session:
            auth_session.revoked_at = datetime.utcnow()
            db.commit()

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )