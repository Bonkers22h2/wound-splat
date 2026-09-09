import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.db import Patient, Scan, ScanStatus, TissueResult
from app.routes import tissue
from app.services.tissue_service import TissueError

ANALYSED = {
    "frame": "/frames/0004.jpg",
    "box": [10, 20, 110, 220],
    "wound_fraction_of_box": 0.21,
    "percentages": {"fibrin": 10.0, "granulation": 70.0, "callus": 20.0},
    "no_wound_detected": False,
    "overlay": "/out/tissue_overlay.png",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    patient = Patient(name="Test", patient_code="T-1")
    rendered = Scan(id="scan-done", patient=patient, video_filename="v.mp4",
                    video_path="/v.mp4", status=ScanStatus.RENDERED)
    processing = Scan(id="scan-busy", patient=patient, video_filename="v.mp4",
                      video_path="/v.mp4", status=ScanStatus.PROCESSING)
    session.add_all([patient, rendered, processing])
    session.commit()

    frames = tmp_path / "data" / "scan_scan-done" / "input"
    frames.mkdir(parents=True)
    (frames / "0001.jpg").write_bytes(b"x")
    monkeypatch.setattr(tissue, "GAUSSIAN_SPLATTING_DIR", tmp_path)
    monkeypatch.setattr(tissue, "analyse", lambda *a, **k: dict(ANALYSED))

    app = FastAPI()
    app.include_router(tissue.router, prefix="/scans")
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app), session


def test_analysing_a_scan_stores_and_returns_the_percentages(client):
    api, session = client

    response = api.post("/scans/scan-done/tissue",
                        json={"left": 10, "top": 20, "right": 110, "bottom": 220})

    assert response.status_code == 200
    assert response.json()["percentages"]["granulation"] == 70.0
    stored = session.query(TissueResult).one()
    assert stored.granulation_percent == 70.0
    assert stored.frame_filename == "0004.jpg"


def test_analysing_an_unknown_scan_returns_404(client):
    api, _ = client

    response = api.post("/scans/nope/tissue",
                        json={"left": 1, "top": 2, "right": 3, "bottom": 4})

    assert response.status_code == 404


def test_analysing_a_scan_that_has_not_finished_returns_409(client):
    # Frames only exist once the scan has run, so this would otherwise fail
    # deep inside the subprocess with a confusing message.
    api, _ = client

    response = api.post("/scans/scan-busy/tissue",
                        json={"left": 10, "top": 20, "right": 110, "bottom": 220})

    assert response.status_code == 409


def test_a_backwards_box_is_rejected_as_a_client_error_not_a_server_error(client):
    api, _ = client

    response = api.post("/scans/scan-done/tissue",
                        json={"left": 110, "top": 20, "right": 10, "bottom": 220})

    assert response.status_code == 400


def test_a_failure_inside_the_model_is_reported_not_stored(client, monkeypatch):
    api, session = client

    def boom(*args, **kwargs):
        raise TissueError("checkpoint missing")

    monkeypatch.setattr(tissue, "analyse", boom)
    response = api.post("/scans/scan-done/tissue",
                        json={"left": 10, "top": 20, "right": 110, "bottom": 220})

    assert response.status_code == 500
    assert "checkpoint missing" in response.json()["detail"]
    assert session.query(TissueResult).count() == 0


def test_a_no_wound_result_is_stored_without_percentages(client, monkeypatch):
    api, session = client
    monkeypatch.setattr(tissue, "analyse", lambda *a, **k: {
        **ANALYSED, "percentages": None, "no_wound_detected": True,
        "wound_fraction_of_box": 0.002,
    })

    response = api.post("/scans/scan-done/tissue",
                        json={"left": 10, "top": 20, "right": 110, "bottom": 220})

    assert response.status_code == 200
    assert response.json()["no_wound_detected"] is True
    stored = session.query(TissueResult).one()
    assert stored.granulation_percent is None


def test_reanalysing_replaces_the_previous_result_rather_than_adding_one(client):
    api, session = client
    body = {"left": 10, "top": 20, "right": 110, "bottom": 220}

    api.post("/scans/scan-done/tissue", json=body)
    api.post("/scans/scan-done/tissue", json={**body, "right": 120})

    assert session.query(TissueResult).count() == 1
    assert session.query(TissueResult).one().box_right == 120


def test_fetching_a_result_that_does_not_exist_returns_404(client):
    api, _ = client

    assert api.get("/scans/scan-done/tissue").status_code == 404


def test_fetching_a_stored_result_returns_it(client):
    api, _ = client
    api.post("/scans/scan-done/tissue",
             json={"left": 10, "top": 20, "right": 110, "bottom": 220})

    response = api.get("/scans/scan-done/tissue")

    assert response.status_code == 200
    assert response.json()["percentages"]["fibrin"] == 10.0
