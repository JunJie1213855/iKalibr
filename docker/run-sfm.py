#!/usr/bin/env python3
"""Run exported COLMAP commands with CPU limits and a sparse matching graph."""
import argparse
import os
from pathlib import Path
import shlex
import sqlite3
import subprocess


def option(args, key):
    return args[args.index(key) + 1]


def features_complete(args):
    db = Path(option(args, '--database_path'))
    image_dir = Path(option(args, '--image_path'))
    expected = {p.relative_to(image_dir).as_posix() for p in image_dir.rglob('*')
                if p.suffix.lower() in ('.jpg', '.jpeg', '.png') and p.is_file()}
    if not db.is_file() or not expected:
        return False
    try:
        with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True) as conn:
            complete = {row[0] for row in conn.execute(
                'SELECT i.name FROM images i JOIN keypoints k ON k.image_id=i.image_id '
                'JOIN descriptors d ON d.image_id=i.image_id')}
        return expected <= complete
    except sqlite3.DatabaseError:
        return False


def prepare_pairs(source):
    pairs = set()
    line_count = 0
    with source.open() as stream:
        for line in stream:
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            a, b = line.split()
            line_count += 1
            if a != b:
                pairs.add(tuple(sorted((a, b))))
    names = sorted({name for pair in pairs for name in pair})
    indices = {name: i for i, name in enumerate(names)}
    # Exported image names are timestamps, so sorting is chronological.
    selected = []
    for a, b in sorted(pairs):
        i, j = indices[a], indices[b]
        distance = abs(j - i)
        local = distance <= 10
        keyframes = i % 20 == 0 and j % 20 == 0
        longer = distance in (20, 40, 80, 160, 320) and (i % 10 == 0 or j % 10 == 0)
        if local or keyframes or longer:
            selected.append((a, b))
    if {name for pair in selected for name in pair} != set(names):
        raise RuntimeError('Sparse selection would isolate images; use IKALIBR_SFM_MODE=all')
    target = source.with_name('matches-fast.txt')
    target.write_text(''.join(f'{a} {b}\n' for a, b in selected))
    print(f'Pair candidates: {line_count} original lines, {len(pairs)} unique pairs, '
          f'{len(selected)} fast pairs across {len(names)} images', flush=True)
    print(f'Fast pair list: {target}', flush=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result_dir', type=Path)
    parser.add_argument('--prepare-only', action='store_true', help='Write pairs without running COLMAP')
    parser.add_argument('--resume-mapper', action='store_true',
                        help='Reuse completed features/matches; run only reconstruction and export')
    args = parser.parse_args()
    mode = os.environ.get('IKALIBR_SFM_MODE', 'fast')
    if mode not in ('fast', 'all'):
        parser.error('IKALIBR_SFM_MODE must be fast or all')
    files = sorted(args.result_dir.rglob('sfm-command-line.txt'))
    if not files:
        raise SystemExit('No SfM commands. Run calibration once to export images first.')
    for path in files:
        commands = {}
        for line in path.read_text().splitlines():
            if line.startswith('colmap '):
                command = shlex.split(line)
                commands[command[1]] = command
        for op in ('feature_extractor', 'matches_importer', 'mapper', 'model_converter'):
            if op not in commands:
                raise RuntimeError(f'Missing COLMAP command {op} in {path}')
        if args.resume_mapper:
            db = Path(option(commands['mapper'], '--database_path'))
            if not features_complete(commands['feature_extractor']):
                raise RuntimeError(f'Cannot resume: incomplete image features in {db}')
            with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True) as conn:
                verified = conn.execute(
                    'SELECT COUNT(*) FROM two_view_geometries WHERE rows > 0').fetchone()[0]
            if not verified:
                raise RuntimeError(f'Cannot resume: no verified image matches in {db}')
            print(f'Resuming mapper with {verified} verified image pairs from {db}', flush=True)
        elif mode == 'fast':
            matching = commands['matches_importer']
            fast = prepare_pairs(path.parent / 'matches.txt')
            matching[matching.index('--match_list_path') + 1] = str(fast)
        if args.prepare_only:
            continue
        for op in ('feature_extractor', 'matches_importer', 'mapper', 'model_converter'):
            if args.resume_mapper and op in ('feature_extractor', 'matches_importer'):
                continue
            command = commands[op]
            if op == 'feature_extractor':
                if features_complete(command):
                    print('Reusing existing features: all images have keypoints and descriptors.', flush=True)
                    continue
                command += ['--SiftExtraction.use_gpu', '0', '--SiftExtraction.num_threads', '4']
            elif op == 'matches_importer':
                command += ['--SiftMatching.use_gpu', '0', '--SiftMatching.num_threads', '4']
            elif op == 'mapper':
                command += ['--Mapper.num_threads', '4']
                # With all PINHOLE intrinsics fixed, old COLMAP otherwise creates
                # a zero-dimensional Ceres SubsetParameterization: PINHOLE has
                # no extra parameters. Explicitly disable every intrinsic group.
                for key in ('--Mapper.ba_refine_focal_length',
                            '--Mapper.ba_refine_principal_point',
                            '--Mapper.ba_refine_extra_params'):
                    if key in command:
                        command[command.index(key) + 1] = '0'
                    else:
                        command += [key, '0']
            print(shlex.join(command), flush=True)
            subprocess.run(command, check=True, env={**os.environ, 'OMP_NUM_THREADS': '4',
                                                    'OPENBLAS_NUM_THREADS': '1'})
        for filename in ('cameras.txt', 'images.txt', 'points3D.txt'):
            if not (path.parent / filename).is_file():
                raise SystemExit(f'Missing SfM output: {path.parent / filename}')


if __name__ == '__main__':
    main()
