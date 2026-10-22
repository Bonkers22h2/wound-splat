"""Before/after opening-area and Dice evaluation, without fitting to references."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gaussian-splatting'))
import benchmark_wound_geometry as benchmark
from evaluate_wound_overlap import compare_footprint, rasterize_footprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-root', type=Path,
                        default=ROOT / 'experiments/night2/datasets/salve/data/data_release')
    parser.add_argument('--prediction-root', type=Path,
                        default=ROOT / 'experiments/night2/runs/salve_pis3_iphone_50_a40')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'experiments/salve_boundary_fix')
    parser.add_argument('--scanner-controls', action='store_true',
                        help='Also test opening extraction on PIS3/PIS4/SD scanner RGB, not held-out reconstructions')
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ann_path = Path(__file__).parent / 'annotations/PIS3_draft.json'
    ann = json.loads(ann_path.read_text())
    scanner_path = args.dataset_root / 'GT/PIS3_2.ply'
    if benchmark.file_record(scanner_path)['sha256'] != ann['reference_sha256']:
        raise ValueError('PIS3 annotation does not match scanner hash')
    reference = benchmark.measure_reference(benchmark.load_points(scanner_path), ann)
    report = {
        'status': 'exploratory_draft_reference', 'clinical_validation': False,
        'alignment': 'supplied similarity transform, unverified; no ICP fitted for these scores',
        'evaluation': 'single reconstructed development phantom PIS3; not a dataset mean',
        'reference': reference, 'annotation': benchmark.file_record(ann_path),
        'scanner': benchmark.file_record(scanner_path), 'script': benchmark.file_record(__file__),
        'cases': {},
    }
    transform = args.dataset_root / 'transformations/Iphone/50/PIS3/transform4x4.txt'
    for margin, filename in [('default', 'wound_only.ply'), ('wider', 'wound_only_margin1.ply')]:
        report['cases'][margin] = {}
        for mode in ('geometry', 'auto'):
            footprint_path = args.output_dir / f'PIS3_{margin}_{mode}_footprint.npz'
            prediction = benchmark.measure_prediction(
                args.prediction_root / 'point_cloud/iteration_30000' / filename, transform,
                boundary_mode=mode, footprint_output=str(footprint_path))
            with np.load(footprint_path) as footprint:
                overlap = compare_footprint(footprint, ann['wound_polygon_xy'])
            row = {'prediction': prediction, 'overlap': overlap,
                   'errors': benchmark.compare_metrics(reference['metrics'], prediction['metrics'])}
            report['cases'][margin][mode] = row
            print(f'{margin}/{mode}: area={prediction["metrics"]["surface_area_cm2"]:.2f} cm2, '
                  f'Dice={100*overlap["dice"]:.2f}%', flush=True)
    if args.scanner_controls:
        identity = args.output_dir / 'identity_mm_transform.txt'
        np.savetxt(identity, np.eye(4))
        report['scanner_controls'] = {}
        for case in ('PIS3', 'PIS4', 'SD'):
            case_ann_path = Path(__file__).parent / 'annotations' / f'{case}_draft.json'
            case_ann = json.loads(case_ann_path.read_text())
            scanner = args.dataset_root / 'GT' / f'{case}_2.ply'
            if benchmark.file_record(scanner)['sha256'] != case_ann['reference_sha256']:
                raise ValueError(f'{case} annotation does not match scanner hash')
            fp_path = args.output_dir / f'{case}_scanner_auto_footprint.npz'
            prediction = benchmark.measure_prediction(scanner, identity, 'auto', str(fp_path))
            with np.load(fp_path) as fp:
                overlap = compare_footprint(fp, case_ann['wound_polygon_xy'])
            report['scanner_controls'][case] = {
                'purpose': 'RGB opening extraction on scanner geometry, not reconstructed geometry',
                'prediction': prediction, 'overlap': overlap,
                'annotation': benchmark.file_record(case_ann_path)}
            print(f'{case}/scanner control: Dice={100*overlap["dice"]:.2f}%', flush=True)
    (args.output_dir / 'opening_comparison.json').write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    if args.plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap
        fig, axes = plt.subplots(1, 2, figsize=(12, 6))
        for ax, mode, title in zip(axes, ('geometry', 'auto'), ('Before: depression footprint', 'After: color opening')):
            with np.load(args.output_dir / f'PIS3_default_{mode}_footprint.npz') as fp:
                predicted, target, lower = rasterize_footprint(fp, ann['wound_polygon_xy'])
            categories = target.astype(int) + 2 * predicted.astype(int)
            ax.imshow(categories, origin='lower', interpolation='nearest', vmin=0, vmax=3,
                      cmap=ListedColormap(['#f4f4f4', '#df735e', '#568dc2', '#66ac86']),
                      extent=[lower[0], lower[0]+categories.shape[1]*.25,
                              lower[1], lower[1]+categories.shape[0]*.25])
            dice = report['cases']['default'][mode]['overlap']['dice']
            ax.set_title(f'{title}\nDraft-reference Dice {dice:.1%}')
            ax.set_xlim(60, 125); ax.set_ylim(20, 90)
            ax.set_xlabel('Scanner X (mm)'); ax.set_ylabel('Scanner Y (mm)')
        fig.suptitle('PIS3: green = overlap | red = missed reference | blue = extra prediction\n'
                     'Single development reconstruction; draft outline and unverified alignment', fontsize=11)
        fig.tight_layout(); fig.savefig(args.output_dir / 'opening_comparison.png', dpi=160)


if __name__ == '__main__':
    main()
