import json

import pytest

from app.services.tissue_service import (
    TissueError,
    build_command,
    parse_output,
    validate_box,
)


def test_command_uses_the_tissue_environment_not_the_backend_one():
    # The backend must not need torch-vision packages of its own; the model
    # runs under tissue-venv exactly as wound_segment.py runs under its own.
    command = build_command("frames", (1, 2, 3, 4), "out")

    assert "tissue-venv" in command[0]
    assert command[1:4] == ["-m", "tissue.segment_image", "--frames-dir"]
    assert "--box" in command
    assert command[command.index("--box") + 1: command.index("--box") + 5] == [
        "1", "2", "3", "4"
    ]


def test_parse_output_reads_the_json_summary():
    payload = {"percentages": {"fibrin": 10.0, "granulation": 70.0, "callus": 20.0},
               "no_wound_detected": False, "overlay": "o.png", "frame": "0004.jpg",
               "wound_fraction_of_box": 0.2}

    result = parse_output(json.dumps(payload))

    assert result["percentages"]["granulation"] == 70.0
    assert result["no_wound_detected"] is False


def test_parse_output_raises_when_the_subprocess_reported_an_error():
    with pytest.raises(TissueError, match="no frames"):
        parse_output(json.dumps({"error": "no frames in x"}))


def test_parse_output_raises_on_unparseable_output_rather_than_returning_junk():
    # A crashed subprocess prints a traceback, not JSON. Failing loudly beats
    # storing an empty result that looks like a real measurement.
    with pytest.raises(TissueError, match="could not read"):
        parse_output("Traceback (most recent call last):\n  ...")


@pytest.mark.parametrize(
    "box",
    [(10, 10, 5, 50), (10, 10, 50, 5), (10, 10, 10, 50), (-1, 0, 10, 10)],
)
def test_validate_box_rejects_boxes_that_are_backwards_empty_or_negative(box):
    with pytest.raises(TissueError):
        validate_box(box)


def test_validate_box_accepts_a_sensible_box():
    assert validate_box((10, 20, 110, 220)) == (10, 20, 110, 220)
