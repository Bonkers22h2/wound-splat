"""Calibration must work without the CUDA trainer and reject invalid scales."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gaussian-splatting'))
sys.path.insert(0,str(ROOT/'backend'))


def estimator():
    spec=importlib.util.spec_from_file_location('estimate_scale',ROOT/'gaussian-splatting/estimate_scale.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scale_estimator_does_not_require_torch():
    assert estimator().KNOWN_REFERENCES['coin:php_5'][1]==25.


def test_five_peso_versions_have_distinct_diameters():
    m=estimator()
    from app.services.scale_calibration import REFERENCE_CHOICES
    assert m.KNOWN_REFERENCES['coin:php_5_bsp'][1]==27.
    assert 'coin:php_5_bsp' in REFERENCE_CHOICES


@pytest.mark.parametrize('radius',[25,50,90])
def test_coin_edge_detection_does_not_inflate_diameter(radius):
    frame=np.full((800,1000,3),60,np.uint8)
    cv2.circle(frame,(400,400),radius,(200,200,200),-1)
    detected=estimator().detect_coin(frame)
    assert detected is not None
    assert abs(detected[0]-2*radius)<=2.0


@pytest.mark.parametrize('value',['nan','inf','-1','0'])
def test_invalid_scale_output_is_not_accepted_as_calibration(monkeypatch,value):
    from app.services import scale_calibration as service
    monkeypatch.setattr(service.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=f'SCALE_CM_PER_UNIT: {value}\n'))
    assert service.estimate_scan_scale('unused','coin:php_5') is None


def test_valid_scale_is_retained(monkeypatch):
    from app.services import scale_calibration as service
    monkeypatch.setattr(service.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout='SCALE_CM_PER_UNIT: 0.125\n'))
    assert service.estimate_scan_scale('unused','coin:php_5')==.125


@pytest.mark.parametrize('fy',[800.,1000.,1200.])
def test_synthetic_coin_capture_recovers_known_metric_scale(monkeypatch,tmp_path,fy):
    m=estimator()
    images=tmp_path/'images'
    images.mkdir()
    extrinsics={}
    for i in range(8):
        name=f'{i:03}.png'
        frame=np.full((1000,1000,3),60,np.uint8)
        cv2.ellipse(frame,(500,500),(100,int(fy/10)),0,0,360,(200,200,200),-1)
        cv2.imwrite(str(images/name),frame)
        extrinsics[i]=SimpleNamespace(name=name,camera_id=1,qvec=np.array([1,0,0,0]),tvec=np.zeros(3))
    camera=SimpleNamespace(model='PINHOLE',params=np.array([1000.,fy,500.,500.]))
    x,y=np.meshgrid(np.linspace(-.7,.7,15),np.linspace(-.7,.7,15))
    xyz=np.column_stack([x.ravel(),y.ravel(),np.full(x.size,10.)])
    monkeypatch.setattr(m,'read_extrinsics_binary',lambda p:extrinsics)
    monkeypatch.setattr(m,'read_intrinsics_binary',lambda p:{1:camera})
    monkeypatch.setattr(m,'read_points3D_binary',lambda p:(xyz,None,None))
    result=m.estimate_scale(str(tmp_path),'coin:php_5')
    assert result['scale_cm_per_unit']==pytest.approx(1.25,rel=.02)
