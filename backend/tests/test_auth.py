"""Authentication, session revocation, and route protection tests.

Doctor passwords must be hashed with Argon2, browser sessions stored only as
SHA-256 token hashes behind HttpOnly cookies, and clinical routes locked with
401 whenever a session is missing, logged out, or expired.
"""
from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import SESSION_COOKIE_NAME  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.models.db import AuthSession, Doctor  # noqa: E402
from app.security import hash_session_token, verify_password  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    app.dependency_overrides[get_db] = lambda: session
    # Construct directly rather than `with TestClient(app):` so startup hooks
    # do not open or alter the real woundsplat.db file on disk.
    api = TestClient(app)
    try:
        yield api, session
    finally:
        api.close()
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()


def _signup(
    api,
    full_name="  Dr.   Jane   Doe  ",
    email="Dr.Jane@Example.COM",
    password="StrongPass123!",
):
    return api.post(
        "/auth/signup",
        json={"full_name": full_name, "email": email, "password": password},
    )


def test_signup_normalizes_inputs_and_hashes_password_with_argon2(client):
    api, session = client
    res = _signup(api)

    assert res.status_code == 201
    body = res.json()
    assert body["full_name"] == "Dr. Jane Doe"
    assert body["email"] == "dr.jane@example.com"
    assert "id" in body and "created_at" in body
    assert "password" not in body and "password_hash" not in body

    doctor = session.query(Doctor).filter(Doctor.id == body["id"]).one()
    assert doctor.password_hash != "StrongPass123!"
    assert doctor.password_hash.startswith("$argon2")
    assert verify_password("StrongPass123!", doctor.password_hash)


def test_a_duplicate_email_is_rejected_regardless_of_case(client):
    api, _ = client
    assert _signup(api, email="clinician@example.com").status_code == 201
    assert _signup(api, email="CLINICIAN@EXAMPLE.COM").status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"full_name": "Dr. Jane Doe", "email": "not-an-email", "password": "StrongPass123!"},
        {"full_name": "Dr. Jane Doe", "email": "jane@example.com", "password": "shortpass11"},
        {"full_name": "   ", "email": "jane@example.com", "password": "StrongPass123!"},
    ],
)
def test_invalid_signup_payloads_return_422(client, payload):
    api, _ = client
    assert api.post("/auth/signup", json=payload).status_code == 422


def test_login_sets_an_httponly_cookie_and_stores_only_the_token_hash(client):
    api, session = client
    _signup(api, email="doc@example.com")

    res = api.post("/auth/login", json={"email": "DOC@EXAMPLE.COM", "password": "StrongPass123!"})
    assert res.status_code == 200
    assert res.json()["email"] == "doc@example.com"
    assert "password_hash" not in res.json()

    raw_token = res.cookies.get(SESSION_COOKIE_NAME)
    set_cookie = res.headers.get("set-cookie", "").lower()
    assert raw_token and f"{SESSION_COOKIE_NAME}=" in set_cookie and "httponly" in set_cookie

    stored = session.query(AuthSession).one()
    assert stored.token_hash != raw_token
    assert stored.token_hash == hash_session_token(raw_token)
    assert len(stored.token_hash) == 64
    assert stored.revoked_at is None and stored.expires_at > datetime.utcnow()


def test_login_rejects_a_wrong_password_unknown_email_or_inactive_account(client):
    api, session = client
    _signup(api, email="doc@example.com")

    assert api.post("/auth/login", json={"email": "doc@example.com", "password": "WrongPassword123!"}).status_code == 401
    assert api.post("/auth/login", json={"email": "nobody@example.com", "password": "StrongPass123!"}).status_code == 401

    doctor = session.query(Doctor).filter(Doctor.email == "doc@example.com").one()
    doctor.is_active = False
    session.commit()
    assert api.post("/auth/login", json={"email": "doc@example.com", "password": "StrongPass123!"}).status_code == 401


def test_me_requires_a_session_and_returns_the_logged_in_doctor(client):
    api, _ = client
    assert api.get("/auth/me").status_code == 401

    _signup(api, full_name="Dr. Alex Rivera", email="alex@example.com")
    assert api.post("/auth/login", json={"email": "alex@example.com", "password": "StrongPass123!"}).status_code == 200

    me = api.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["full_name"] == "Dr. Alex Rivera" and me.json()["email"] == "alex@example.com"


def test_logout_revokes_the_session_so_a_replayed_cookie_fails(client):
    api, session = client
    _signup(api, email="doc@example.com")
    raw_token = api.post(
        "/auth/login", json={"email": "doc@example.com", "password": "StrongPass123!"}
    ).cookies.get(SESSION_COOKIE_NAME)

    logout_res = api.post("/auth/logout")
    assert logout_res.status_code == 204
    assert SESSION_COOKIE_NAME not in api.cookies
    assert f"{SESSION_COOKIE_NAME}=" in logout_res.headers.get("set-cookie", "")

    stored = session.query(AuthSession).one()
    session.refresh(stored)
    assert stored.revoked_at is not None

    assert api.get("/auth/me").status_code == 401
    # Even if an old cookie is replayed manually, the revoked DB row blocks it.
    assert api.get("/auth/me", cookies={SESSION_COOKIE_NAME: raw_token}).status_code == 401


def test_an_expired_session_is_rejected_and_marked_revoked(client):
    api, session = client
    _signup(api, email="doc@example.com")
    assert api.post("/auth/login", json={"email": "doc@example.com", "password": "StrongPass123!"}).status_code == 200

    stored = session.query(AuthSession).one()
    stored.expires_at = datetime.utcnow() - timedelta(minutes=5)
    session.commit()

    assert api.get("/auth/me").status_code == 401
    session.refresh(stored)
    assert stored.revoked_at is not None


@pytest.mark.parametrize(
    "path",
    [
        "/patients",
        "/scans/admin/queue",
        "/scans/admin/summary",
        "/reports/fake-id/pdf",
        "/scans/fake-id/tissue",
    ],
)
def test_clinical_routes_reject_unauthenticated_requests(client, path):
    api, _ = client
    assert api.get(path).status_code == 401


def test_health_stays_public(client):
    api, _ = client
    res = api.get("/health")
    assert res.status_code == 200 and res.json() == {"status": "ok"}
