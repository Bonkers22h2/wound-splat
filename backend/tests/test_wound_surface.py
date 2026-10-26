"""Analytic regressions for camera-oriented, color-bounded surface measurements."""
from pathlib import Path
import sys
import numpy as np
import pytest
import json
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'gaussian-splatting'))


def scene(depth=.3, raised=False, contamination=False, hole=False):
    x,y=np.meshgrid(np.arange(-3.,3.001,.04),np.arange(-3.,3.001,.04))
    r=np.hypot(x,y)
    bed=r<1.
    z=np.where(bed, depth if raised else -depth, 0.)
    pts=np.column_stack([x.ravel(),y.ravel(),z.ravel()])
    colors=np.tile([.7,.65,.6],(len(pts),1))
    colors[bed.ravel()]=[.6,.12,.12]
    if contamination:
        ids=np.flatnonzero(~bed.ravel())[::12]
        colors[ids]=[.6,.12,.12]
    if hole:
        keep=~((x.ravel()>.1)&(x.ravel()<.7)&(abs(y.ravel())<.5))
        pts,colors=pts[keep],colors[keep]
    return pts,colors


def measure(points,colors,normal=(0,0,1),scale=1.):
    from wound_surface import measure_surface
    return measure_surface(points,colors,np.array(normal),scale=scale)


def test_raised_bed_does_not_become_a_cavity():
    result=measure(*scene(raised=True))
    assert result['metrics']['volume_cm3']==pytest.approx(0.,abs=1e-8)
    assert result['metrics']['max_depth_mm']==pytest.approx(0.,abs=1e-8)
    assert result['metrics']['surface_area_cm2']==pytest.approx(np.pi,rel=.12)


def test_cylindrical_cavity_measures_depth_volume_and_axes():
    m=measure(*scene())['metrics']
    assert m['volume_cm3']==pytest.approx(np.pi*.3,rel=.12)
    assert m['max_depth_mm']==pytest.approx(3.,rel=.05)
    assert m['width_cm']==pytest.approx(2.,rel=.12)
    assert m['height_cm']==pytest.approx(2.,rel=.12)


def test_red_contamination_spanning_skin_requires_review():
    with pytest.raises(ValueError,match='crop'):
        measure(*scene(contamination=True))


def test_sparse_red_annulus_cannot_silently_double_reported_area():
    p,c=scene()
    radius=np.linalg.norm(p[:,:2],axis=1)
    c[np.flatnonzero((radius>1)&(radius<1.6))[::12]]=[.6,.12,.12]
    result=measure(p,c)
    assert result['status']=='boundary_review_required'
    assert all(value is None for value in result['metrics'].values())


def test_missing_surface_withholds_depth_and_volume():
    result=measure(*scene(hole=True))
    assert result['coverage']<.98
    assert result['metrics']['volume_cm3'] is None
    assert result['metrics']['max_depth_mm'] is None


def test_rotation_and_calibrated_units_preserve_measurements():
    p,c=scene()
    rotation=np.array([[1,0,0],[0,.6,-.8],[0,.8,.6]])
    original=measure(p,c)['metrics']
    rotated=measure((p@rotation.T)*10+[7,8,9],c,rotation@np.array([0,0,1]),scale=.1)['metrics']
    for key in original:
        assert rotated[key]==pytest.approx(original[key],rel=.08,abs=.01)


def test_missing_orientation_is_rejected():
    with pytest.raises(ValueError,match='outward'):
        measure(*scene(),normal=(0,0,0))


def test_missing_color_is_rejected():
    p,c=scene()
    with pytest.raises(ValueError,match='color|RGB|opening'):
        measure(p,np.zeros_like(c))


def test_camera_direction_requires_consistent_surface_side():
    from wound_surface import camera_outward
    p,_=scene()
    assert camera_outward(p,[[0,0,10],[1,0,10]])[2]>.99
    with pytest.raises(ValueError,match='Ambiguous|agree'):
        camera_outward(p,[[0,0,10],[0,0,-10]])


def test_surface_cli_uses_camera_poses_and_writes_quality_metadata(tmp_path):
    import open3d as o3d
    p,c=scene(raised=True)
    cloud=o3d.geometry.PointCloud()
    cloud.points=o3d.utility.Vector3dVector(p)
    cloud.colors=o3d.utility.Vector3dVector(c)
    path=tmp_path/'wound.ply'
    o3d.io.write_point_cloud(str(path),cloud)
    cameras=tmp_path/'cameras.json'
    cameras.write_text(json.dumps([{'position':[0,0,10]},{'position':[1,0,10]}]))
    script=Path(__file__).resolve().parents[2]/'gaussian-splatting/wound_measure.py'
    run=subprocess.run([sys.executable,str(script),'--ply',str(path),'--scale','1',
                        '--boundary-mode','surface','--camera-poses',str(cameras)],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    report=json.loads((tmp_path/'wound_measurements.json').read_text())
    assert report['metrics']['volume_cm3']==pytest.approx(0.,abs=1e-8)
    assert report['orientation_source']=='capture_cameras'
    assert report['clinical_validation'] is False
