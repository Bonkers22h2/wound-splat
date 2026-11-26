"""Dashboard summary, admin queue, and patient input validation tests.

The summary endpoint aggregates counts directly from SQLite instead of slicing
the 50-item queue, while the queue and patient routes preserve their existing
response contracts.
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

from app.database import Base, get_db  # noqa: E402
from app.models.db import Measurement, Patient, Scan, ScanStatus  # noqa: E402
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
    assert api.post(
        "/auth/signup",
        json={
            "full_name": "Dr. Dashboard Tester",
            "email": "dashboard@example.com",
            "password": "StrongPass123!",
        },
    ).status_code == 201
    assert api.post(
        "/auth/login",
        json={"email": "dashboard@example.com", "password": "StrongPass123!"},
    ).status_code == 200
    try:
        yield api, session
    finally:
        api.close()
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()


def _seed(session):
    t = datetime(2026, 9, 10, 8, 0, 0)
    patients = [
        Patient(id="pat-1", name="Alice Reyes", patient_code="PT-001"),
        Patient(id="pat-2", name="Bruno Cruz", patient_code="PT-002"),
        Patient(id="pat-3", name="Carla Lim", patient_code="PT-003"),
    ]
    scans = [
        Scan(id="s1", patient_id="pat-1", video_filename="q.mp4", video_path="/q.mp4",
             status=ScanStatus.QUEUED, created_at=t),
        Scan(id="s2", patient_id="pat-1", video_filename="p.mp4", video_path="/p.mp4",
             status=ScanStatus.PROCESSING, current_step=3,
             current_step_name="Training 3D Gaussian Splatting",
             progress_percent=42.5, created_at=t + timedelta(minutes=1)),
        # Only one of the two rendered scans has measurements so those counts differ.
        Scan(id="s3", patient_id="pat-2", video_filename="r1.mp4", video_path="/r1.mp4",
             status=ScanStatus.RENDERED, registration_rate=95.0,
             created_at=t + timedelta(minutes=2), completed_at=t + timedelta(minutes=25)),
        Scan(id="s4", patient_id="pat-3", video_filename="r2.mp4", video_path="/r2.mp4",
             status=ScanStatus.RENDERED, created_at=t + timedelta(minutes=3),
             completed_at=t + timedelta(minutes=30)),
        Scan(id="s5", patient_id="pat-3", video_filename="f.mp4", video_path="/f.mp4",
             status=ScanStatus.FAILED, error_message="COLMAP failed",
             created_at=t + timedelta(minutes=4)),
    ]
    measurement = Measurement(
        id="meas-1", scan_id="s3", surface_area_cm2=4.2, volume_cm3=1.1,
        max_depth_mm=5.5, width_cm=2.4, height_cm=1.9,
    )
    session.add_all([*patients, *scans, measurement])
    session.commit()


def test_admin_summary_counts_patients_assessments_and_statuses(client):
    api, session = client
    _seed(session)

    res = api.get("/scans/admin/summary")
    assert res.status_code == 200
    assert res.json() == {
        "patient_count": 3,
        "assessment_summary": {"total": 5, "completed": 2, "with_measurements": 1},
        "processing_status": {"queued": 1, "processing": 1, "completed": 2, "failed": 1},
    }


def test_admin_queue_remains_a_list_with_expected_fields(client):
    api, session = client
    _seed(session)

    res = api.get("/scans/admin/queue")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list) and len(items) == 5
    expected = {
        "id", "patient_id", "video_filename", "status", "created_at",
        "completed_at", "current_step", "current_step_name",
        "progress_percent", "registration_rate",
    }
    assert all(expected.issubset(item.keys()) for item in items)


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   ", "patient_code": "PT-010"},
        {"name": "Maria Santos", "patient_code": "  \t  "},
        {"name": "", "patient_code": "PT-010"},
        {"name": "Maria Santos", "patient_code": ""},
    ],
)
def test_blank_or_whitespace_patient_fields_return_422(client, payload):
    api, _ = client
    assert api.post("/patients", json=payload).status_code == 422


def test_creating_a_patient_normalizes_whitespace_and_rejects_duplicates(client):
    api, _ = client
    res = api.post("/patients", json={"name": "  Maria   Santos  ", "patient_code": "  PT-100  "})
    assert res.status_code == 200
    created = res.json()
    assert created["name"] == "Maria Santos" and created["patient_code"] == "PT-100"
    assert "id" in created and "created_at" in created

    for code in ("PT-100", "  PT-100  "):
        dup = api.post("/patients", json={"name": "Another Name", "patient_code": code})
        assert dup.status_code == 400
        assert dup.json()["detail"] == "Patient code already exists"
