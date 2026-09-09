import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generate_report import tissue_flowables  # noqa: E402


def _text(flowables):
    """All readable text, from paragraphs and from table cells alike."""
    parts = []
    for flowable in flowables:
        if hasattr(flowable, "text"):
            parts.append(flowable.text)
        for row in getattr(flowable, "_cellvalues", []) or []:
            parts.extend(str(cell) for cell in row)
    return " ".join(parts)


def test_no_tissue_section_when_the_scan_was_never_analysed():
    # Tissue analysis is optional and user-triggered, so most reports have
    # none. The section must be absent, not empty or full of dashes.
    assert tissue_flowables(None) == []


def test_the_section_lists_all_three_tissues_with_their_percentages():
    tissue = {"fibrin_percent": 2.6, "granulation_percent": 93.4,
              "callus_percent": 4.0, "no_wound_detected": False,
              "wound_fraction_of_box": 0.18, "frame_filename": "0004.jpg"}

    text = _text(tissue_flowables(tissue))

    assert "Granulation" in text and "93.4%" in text
    assert "Fibrin" in text and "2.6%" in text
    assert "Callus" in text and "4.0%" in text


def test_the_section_says_the_percentages_are_of_the_wound_not_the_box():
    # A reader seeing "93.4% granulation" needs to know what the denominator
    # is, or they may read it as 93.4% of the photograph.
    tissue = {"fibrin_percent": 2.6, "granulation_percent": 93.4,
              "callus_percent": 4.0, "no_wound_detected": False,
              "wound_fraction_of_box": 0.18, "frame_filename": "0004.jpg"}

    text = _text(tissue_flowables(tissue)).lower()

    assert "wound" in text and "100" in text


def test_a_no_wound_result_is_stated_plainly_instead_of_showing_zeroes():
    tissue = {"fibrin_percent": None, "granulation_percent": None,
              "callus_percent": None, "no_wound_detected": True,
              "wound_fraction_of_box": 0.002, "frame_filename": "0001.jpg"}

    text = _text(tissue_flowables(tissue)).lower()

    assert "no wound" in text
    assert "0.0%" not in text


def test_the_section_records_which_frame_was_analysed():
    # The report must be traceable back to the photo it describes.
    tissue = {"fibrin_percent": 2.6, "granulation_percent": 93.4,
              "callus_percent": 4.0, "no_wound_detected": False,
              "wound_fraction_of_box": 0.18, "frame_filename": "0004.jpg"}

    assert "0004.jpg" in _text(tissue_flowables(tissue))
