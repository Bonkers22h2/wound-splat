import json

import pytest

from app.services.tissue_service import (
    TissueError,
    build_command,
    parse_output,
    select_frame,
    tissue_python,
    validate_box,
)


def test_command_uses_the_tissue_environment_not_the_backend_one():
    # The backend must not need torch-vision packages of its own; the model
    # runs under tissue-venv exactly as wound_segment.py runs under its own.
    command = build_command("frames", (1, 2, 3, 4), "out")

    assert "tissue-venv" in command[0]
    assert command[1:4] == ["-m", "tissue.segment_image", "--image"]
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


def test_selected_frame_is_the_sharpest_of_the_opening_frames(tmp_path):
    # The screen must show the same frame the model analyses, or the box the
    # user drew lands somewhere else. One chooser, here, avoids that.
    import numpy as np
    from PIL import Image

    sharp = (np.indices((64, 64)).sum(axis=0) % 2 * 255).astype("uint8")
    blurred = np.full((64, 64), 128, dtype="uint8")
    for i, data in enumerate([blurred, blurred, sharp, blurred, blurred], start=1):
        Image.fromarray(np.stack([data] * 3, -1)).save(tmp_path / f"{i:04d}.jpg")

    assert select_frame(tmp_path).name == "0003.jpg"


def test_selected_frame_ignores_frames_after_the_opening_ones(tmp_path):
    # Later frames are shot from the side, so they are not candidates.
    import numpy as np
    from PIL import Image

    sharp = (np.indices((64, 64)).sum(axis=0) % 2 * 255).astype("uint8")
    blurred = np.full((64, 64), 128, dtype="uint8")
    for i in range(1, 9):
        data = sharp if i == 8 else blurred
        Image.fromarray(np.stack([data] * 3, -1)).save(tmp_path / f"{i:04d}.jpg")

    assert select_frame(tmp_path).name != "0008.jpg"


def test_selecting_a_frame_from_an_empty_directory_raises(tmp_path):
    with pytest.raises(TissueError, match="no frames"):
        select_frame(tmp_path)


def test_tissue_interpreter_is_found_on_a_linux_layout(tmp_path):
    # The stack is deployed to a Linux GPU pod, where a virtualenv puts its
    # interpreter in bin/python, not Scripts/python.exe.
    posix = tmp_path / "tissue-venv" / "bin"
    posix.mkdir(parents=True)
    (posix / "python").write_text("")

    assert tissue_python(tmp_path).as_posix().endswith("tissue-venv/bin/python")


def test_tissue_interpreter_is_found_on_a_windows_layout(tmp_path):
    windows = tmp_path / "tissue-venv" / "Scripts"
    windows.mkdir(parents=True)
    (windows / "python.exe").write_text("")

    assert tissue_python(tmp_path).name == "python.exe"


def test_tissue_interpreter_falls_back_to_this_platform_when_missing(tmp_path):
    # Nothing installed yet: still return a sensible path so the error names
    # the interpreter we expected rather than failing obscurely.
    import os

    expected = "python.exe" if os.name == "nt" else "python"
    assert tissue_python(tmp_path).name == expected
