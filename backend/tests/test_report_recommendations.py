"""The report advises; it must not instruct or diagnose.

Wound-Splat is decision support. A clinician decides what a measurement
means. These tests hold the report to that, and to not producing clinical
advice from measurements whose scale is unknown.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generate_report import get_recommendation  # noqa: E402

DEEP = dict(surface_area=12.0, volume=8.0, max_depth=25.0)
SHALLOW = dict(surface_area=2.0, volume=1.0, max_depth=4.0)

# Words that turn an observation into an order.
COMMANDS = ["required", "must ", "immediate referral", "urgent",
            "is advised", "strongly advised"]


def _all_text(result):
    _, label, _, _, assessment, recs = result
    return " ".join([label, assessment]
                    + [f"{t} {b}" for t, b in recs]).lower()


def test_no_recommendation_is_phrased_as_an_order():
    text = _all_text(get_recommendation(**DEEP, scale_calibrated=True))

    found = [word for word in COMMANDS if word in text]
    assert not found, f"instruction wording in report: {found}"


def test_severity_is_not_stated_when_the_scale_was_never_calibrated():
    # Without a size reference in the video, millimetres are arbitrary units.
    # A severity grade computed from them would be meaningless.
    severity, label, _, _, _, _ = get_recommendation(**DEEP, scale_calibrated=False)

    assert severity == "unknown"
    assert "not assessed" in label.lower()


def test_uncalibrated_scans_get_no_depth_based_clinical_advice():
    # This is the serious case: an unmeasured depth driving a referral.
    text = _all_text(get_recommendation(**DEEP, scale_calibrated=False))

    assert "osteomyelitis" not in text
    assert "x-ray" not in text and "mri" not in text
    assert "specialist" not in text


def test_uncalibrated_scans_say_why_the_sizes_cannot_be_relied_on():
    _, _, _, _, assessment, _ = get_recommendation(**DEEP, scale_calibrated=False)

    assert "calibrat" in assessment.lower()


def test_a_deep_calibrated_wound_still_surfaces_specialist_review():
    # Reframing must not lose the clinical substance, only the posture.
    text = _all_text(get_recommendation(**DEEP, scale_calibrated=True))

    assert "specialist" in text or "podiatrist" in text
    assert "25.0" in text  # the measurement itself is still reported


def test_general_notes_are_framed_as_context_not_as_prescriptions():
    text = _all_text(get_recommendation(**SHALLOW, scale_calibrated=True))

    assert "offload" in text          # substance kept
    assert "hba1c" in text            # substance kept
    # but conditioned, since the system does not know the patient is diabetic
    assert "for patients with diabetes" in text


def test_measurements_are_reported_for_a_shallow_calibrated_wound():
    _, label, _, _, assessment, _ = get_recommendation(**SHALLOW, scale_calibrated=True)

    assert "4.0" in assessment
    assert "not assessed" not in label.lower()
