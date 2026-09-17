"""Scan timestamps must go out marked as UTC.

The database stores naive datetimes produced by datetime.utcnow(). Serialised
without a timezone designator, a browser's new Date() reads them as *local*
time, shifting every displayed time by the viewer's UTC offset.
"""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.db import Patient, Scan, ScanStatus
from app.routes import scans

# Stored the way the pipeline stores them: naive, and meaning UTC.
SUBMITTED = datetime(2026, 9, 10, 1, 39, 16)
COMPLETED = datetime(2026, 9, 10, 2, 4, 32)


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    patient = Patient(id="pat-1", name="Test", patient_code="T-1")
    session.add_all([
        patient,
        Scan(id="scan-1", patient_id="pat-1", video_filename="v.mp4",
             video_path="/v.mp4", status=ScanStatus.RENDERED,
             created_at=SUBMITTED, completed_at=COMPLETED),
        Scan(id="scan-running", patient_id="pat-1", video_filename="v.mp4",
             video_path="/v.mp4", status=ScanStatus.PROCESSING,
             created_at=SUBMITTED, completed_at=None),
    ])
    session.commit()

    app = FastAPI()
    app.include_router(scans.router, prefix="/scans")
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app)


def queue_row(client, scan_id):
    # Both fixture scans share a created_at, so the queue's sort order between
    # them is unspecified - always select the row by id, never by position.
    rows = {row["id"]: row for row in client.get("/scans/admin/queue").json()}
    return rows[scan_id]


def test_queue_timestamps_carry_an_explicit_utc_offset(client):
    row = queue_row(client, "scan-1")

    submitted = datetime.fromisoformat(row["created_at"])
    completed = datetime.fromisoformat(row["completed_at"])

    # An offset-less string parses to a naive datetime, which is exactly the
    # ambiguity that lets the browser read UTC as local time.
    assert submitted.tzinfo is not None, "created_at has no timezone designator"
    assert completed.tzinfo is not None, "completed_at has no timezone designator"
    assert submitted == SUBMITTED.replace(tzinfo=timezone.utc)
    assert completed == COMPLETED.replace(tzinfo=timezone.utc)


def test_patient_scan_list_timestamps_carry_an_explicit_utc_offset(client):
    rows = {row["id"]: row for row in client.get("/scans/patient/pat-1").json()}
    row = rows["scan-1"]

    submitted = datetime.fromisoformat(row["created_at"])

    assert submitted.tzinfo is not None, "created_at has no timezone designator"
    assert submitted == SUBMITTED.replace(tzinfo=timezone.utc)


def test_an_unfinished_scan_reports_no_completion_time(client):
    """A running scan must stay null, not get stamped with a bogus time."""
    assert queue_row(client, "scan-running")["completed_at"] is None


def test_the_stored_instant_is_labelled_not_shifted(client):
    """Guards against a fix that converts the value instead of labelling it.

    The stored wall-clock reading already *is* UTC, so re-reading it as UTC
    must return the same numbers. Converting it would move the instant by the
    machine's offset - the same class of bug, in the other direction.
    """
    submitted = datetime.fromisoformat(queue_row(client, "scan-1")["created_at"])

    assert submitted.astimezone(timezone.utc).replace(tzinfo=None) == SUBMITTED
