"""Compare experimental local surface measurements; never a held-out accuracy claim."""
import argparse
import json
from pathlib import Path
import platform
import sys

import numpy as np
import open3d
import scipy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gaussian-splatting'))
import benchmark_wound_geometry as benchmark
from evaluate_wound_overlap import compare_footprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-root', type=Path,
                        default=ROOT / 'experiments/night2/datasets/salve/data/data_release')
    parser.add_argument('--prediction-root', type=Path,
                        default=ROOT / 'experiments/night2/runs/salve_pis3_iphone_50_a40')
    parser.add_argument('--output-dir', type=Path,
                        default=ROOT / 'experiments/salve_measurement_followup/reproduced')
    parser.add_argument('--scanner-controls', action='store_true')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        'status': 'exploratory_draft_references', 'clinical_validation': False,
        'validation_scope': 'one PIS3 development reconstruction; optional scanner controls are not reconstructed or held-out cases',
        'runtime': {'python': platform.python_version(), 'numpy': np.__version__,
                    'scipy': scipy.__version__, 'open3d': open3d.__version__},
        'scripts': [benchmark.file_record(path) for path in
                    [Path(__file__), ROOT / 'gaussian-splatting/wound_surface.py',
                     ROOT / 'gaussian-splatting/wound_measure.py',
                     ROOT / 'gaussian-splatting/benchmark_wound_geometry.py',
                     ROOT / 'gaussian-splatting/evaluate_wound_overlap.py']],
        'references': {}, 'predictions': {}, 'scanner_controls': {},
    }

    def reference(case):
        annotation_path = Path(__file__).parent / 'annotations' / f'{case}_draft.json'
        annotation = json.loads(annotation_path.read_text())
        scanner = args.dataset_root / 'GT' / f'{case}_2.ply'
        scanner_record = benchmark.file_record(scanner)
        if scanner_record['sha256'] != annotation['reference_sha256']:
            raise ValueError('Annotation and scanner hashes do not match')
        measured = benchmark.measure_reference(benchmark.load_points(scanner), annotation)
        report['references'][case] = {'annotation': benchmark.file_record(annotation_path),
                                     'scanner': scanner_record, 'measurement': measured}
        return annotation, measured

    annotation, measured = reference('PIS3')
    transform = args.dataset_root / 'transformations/Iphone/50/PIS3/transform4x4.txt'
    for margin, filename in [('default', 'wound_only.ply'), ('wider', 'wound_only_margin1.ply')]:
        rows = report['predictions'][margin] = {}
        for mode in ('geometry', 'auto', 'surface'):
            footprint = args.output_dir / f'{margin}_{mode}.npz'
            prediction = benchmark.measure_prediction(
                args.prediction_root / 'point_cloud/iteration_30000' / filename,
                transform, mode, str(footprint),
                camera_path=args.prediction_root / 'cameras.json' if mode == 'surface' else None)
            with np.load(footprint) as fp:
                overlap = compare_footprint(fp, annotation['wound_polygon_xy'])
            rows[mode] = {'prediction': prediction, 'overlap': overlap,
                          'errors': benchmark.compare_metrics(measured['metrics'], prediction['metrics'])}
            print(f'{margin}/{mode}: {prediction["metrics"]}; Dice {overlap["dice"]:.2%}', flush=True)
    if args.scanner_controls:
        identity = args.output_dir / 'identity_mm.txt'
        np.savetxt(identity, np.eye(4))
        for case in ('PIS3', 'PIS4', 'SD'):
            annotation, measured = reference(case)
            footprint = args.output_dir / f'{case}_scanner_surface.npz'
            prediction = benchmark.measure_prediction(
                args.dataset_root / 'GT' / f'{case}_2.ply', identity, 'surface', str(footprint),
                outward_normal=[0, 0, 1])
            with np.load(footprint) as fp:
                overlap = compare_footprint(fp, annotation['wound_polygon_xy'])
            report['scanner_controls'][case] = {
                'scope': 'scanner geometry and explicit scanner +Z orientation, not camera-estimated reconstruction',
                'prediction': prediction, 'overlap': overlap,
                'errors': benchmark.compare_metrics(measured['metrics'], prediction['metrics'])}
            print(f'{case}/scanner: {prediction["metrics"]}; Dice {overlap["dice"]:.2%}', flush=True)
    (args.output_dir / 'surface_comparison.json').write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    main()
