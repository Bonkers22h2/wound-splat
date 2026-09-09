from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.db import Patient, Scan, TissueResult


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def test_tissue_results_live_in_their_own_table():
    # The project has no migration tool: create_all adds missing tables but
    # never adds columns to an existing one. A separate table therefore
    # appears automatically, leaving the existing scans database intact.
    _, engine = _session()

    assert "tissue_results" in inspect(engine).get_table_names()


def test_existing_tables_gain_no_new_columns():
    _, engine = _session()

    scan_columns = {c["name"] for c in inspect(engine).get_columns("scans")}

    assert "tissue_percentages" not in scan_columns
    assert "granulation_percent" not in scan_columns


def test_a_tissue_result_round_trips_with_its_scan():
    session, _ = _session()
    patient = Patient(name="Test", patient_code="T-1")
    scan = Scan(patient=patient, video_filename="v.mp4", video_path="/v.mp4")
    session.add_all([patient, scan])
    session.commit()

    session.add(TissueResult(
        scan_id=scan.id, frame_filename="0004.jpg",
        box_left=10, box_top=20, box_right=110, box_bottom=220,
        fibrin_percent=10.0, granulation_percent=70.0, callus_percent=20.0,
        wound_fraction_of_box=0.21, overlay_path="o.png", no_wound_detected=False,
    ))
    session.commit()

    stored = session.query(TissueResult).one()
    assert stored.granulation_percent == 70.0
    assert stored.scan.id == scan.id
    assert scan.tissue_result.frame_filename == "0004.jpg"


def test_a_no_wound_result_can_be_stored_with_no_percentages():
    # "No wound in this box" is a real answer and must be recordable, rather
    # than being saved as zeroes that read like a measurement.
    session, _ = _session()
    patient = Patient(name="Test", patient_code="T-2")
    scan = Scan(patient=patient, video_filename="v.mp4", video_path="/v.mp4")
    session.add_all([patient, scan])
    session.commit()

    session.add(TissueResult(
        scan_id=scan.id, frame_filename="0001.jpg",
        box_left=0, box_top=0, box_right=10, box_bottom=10,
        no_wound_detected=True, wound_fraction_of_box=0.001,
    ))
    session.commit()

    stored = session.query(TissueResult).one()
    assert stored.no_wound_detected is True
    assert stored.granulation_percent is None
