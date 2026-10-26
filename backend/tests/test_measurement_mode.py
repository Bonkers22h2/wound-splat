"""The app must explicitly select experimental measurements and supply cameras."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
import json

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def test_surface_mode_passes_matching_camera_file(monkeypatch,tmp_path):
    from app.tasks import pipeline_direct as pipeline
    root=tmp_path/'run'
    cloud=root/'point_cloud/iteration_30000/wound_only.ply'
    cloud.parent.mkdir(parents=True)
    cloud.touch()
    (root/'cameras.json').write_text('[{"position":[0,0,10]}]')
    monkeypatch.setenv('WOUND_MEASUREMENT_MODE','surface')
    commands=[]
    def run(cmd,**kwargs):
        commands.append(cmd)
        return SimpleNamespace(returncode=0,stdout='Surface Area : 3.14 cm2\nVolume : unavailable\n',stderr='')
    monkeypatch.setattr(pipeline.subprocess,'run',run)
    result=pipeline._measure_wound(str(cloud),.1)
    assert commands[0][commands[0].index('--boundary-mode')+1]=='surface'
    assert Path(commands[0][commands[0].index('--camera-poses')+1])==root/'cameras.json'
    assert result=={'surface_area_cm2':3.14}


def test_unknown_mode_is_rejected_before_running(monkeypatch):
    from app.tasks import pipeline_direct as pipeline
    monkeypatch.setenv('WOUND_MEASUREMENT_MODE','typo')
    with pytest.raises(ValueError,match='WOUND_MEASUREMENT_MODE'):
        pipeline._measure_wound('unused',.1)


def test_surface_mode_requires_saved_camera_poses(monkeypatch,tmp_path):
    from app.tasks import pipeline_direct as pipeline
    monkeypatch.setenv('WOUND_MEASUREMENT_MODE','surface')
    with pytest.raises(ValueError,match='camera'):
        pipeline._measure_wound(str(tmp_path/'point_cloud/iteration_30000/wound_only.ply'),.1)


def test_saved_measurement_mode_is_not_reinterpreted_from_current_setting(monkeypatch,tmp_path):
    from app.services.measurements import saved_measurement_metadata
    directory=tmp_path/'point_cloud/iteration_30000'
    directory.mkdir(parents=True)
    (directory/'wound_measurements.json').write_text(json.dumps({'boundary_mode':'geometry'}))
    monkeypatch.setenv('WOUND_MEASUREMENT_MODE','surface')
    assert saved_measurement_metadata(str(tmp_path))['measurement_mode']=='geometry'
