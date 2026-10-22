"""Reproduce the local exploratory SALVE study without training or altering inputs."""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gaussian-splatting'))
import benchmark_wound_geometry as benchmark


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-root', type=Path,
                        default=ROOT / 'experiments/night2/datasets/salve/data/data_release')
    parser.add_argument('--prediction-root', type=Path,
                        default=ROOT / 'experiments/night2/runs/salve_pis3_iphone_50_a40')
    parser.add_argument('--output-dir', type=Path,
                        default=ROOT / 'experiments/salve_measurement_validation/reproduced')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        'status': 'exploratory_draft_references', 'clinical_validation': False,
        'correction_fitted': False, 'held_out_reconstruction_evaluated': False,
        'runtime': {'python': sys.version, **{p: importlib.metadata.version(p)
                    for p in ['numpy', 'scipy', 'plyfile', 'open3d']}},
        'scripts': {name: benchmark.file_record(ROOT / path) for name, path in [
            ('study', 'benchmarks/salve/run_study.py'),
            ('benchmark', 'gaussian-splatting/benchmark_wound_geometry.py'),
            ('pipeline_measurement', 'gaussian-splatting/wound_measure.py')]},
        'cases': {},
    }
    for case in ('PIS3', 'PIS4', 'SD'):
        reference_path = args.dataset_root / 'GT' / f'{case}_2.ply'
        ann_path = Path(__file__).parent / 'annotations' / f'{case}_draft.json'
        ann = json.loads(ann_path.read_text(encoding='utf-8'))
        record = benchmark.file_record(reference_path)
        if record['sha256'] != ann['reference_sha256']:
            raise ValueError(f'{case}: scanner hash differs from annotated scan')
        points = benchmark.load_points(reference_path)
        reference = benchmark.measure_reference(points, ann)
        result = {'inputs': {'scanner': record, 'annotation': benchmark.file_record(ann_path)},
                  'reference': reference, 'prediction_status': 'not_evaluated'}
        if case == 'PIS3':
            # Omit one patch at a time: this is sensitivity, not tuning to prediction.
            sensitivity = []
            for step in (.25, .5, 1.):
                candidate = copy.deepcopy(ann)
                candidate['grid_step_mm'] = step
                sensitivity.append({'condition': f'grid_step_{step}',
                                    'reference': benchmark.measure_reference(points, candidate)})
            for i in range(len(ann['skin_polygons_xy'])):
                candidate = copy.deepcopy(ann)
                candidate['skin_polygons_xy'].pop(i)
                sensitivity.append({'condition': f'omit_skin_patch_{i}',
                                    'reference': benchmark.measure_reference(points, candidate)})
            result['reference_sensitivity'] = sensitivity
            transform = args.dataset_root / 'transformations/Iphone/50/PIS3/transform4x4.txt'
            predictions = {}
            for label, filename in [('default_margin', 'wound_only.ply'),
                                     ('wider_margin', 'wound_only_margin1.ply')]:
                prediction = args.prediction_root / 'point_cloud/iteration_30000' / filename
                if prediction.exists():
                    predicted = benchmark.measure_prediction(prediction, transform)
                    predictions[label] = {'prediction': predicted,
                                          'errors': benchmark.compare_metrics(reference['metrics'], predicted['metrics'])}
            result['predictions'] = predictions
            result['prediction_status'] = 'measured' if predictions else 'missing_saved_prediction'
        report['cases'][case] = result
        write_json(args.output_dir / f'{case}_results.json', result)
        print(f'{case}: {reference["status"]}, coverage={reference["coverage"]:.4f}, '
              f'prediction={result["prediction_status"]}', flush=True)
    write_json(args.output_dir / 'study.json', report)
    print(f'Saved {args.output_dir / "study.json"}', flush=True)


if __name__ == '__main__':
    main()
