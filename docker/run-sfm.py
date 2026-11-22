#!/usr/bin/env python3
"""Run the COLMAP route exported by iKalibr, with CPU-only SIFT and two threads."""
import os
from pathlib import Path
import shlex
import subprocess
import sys

files = sorted(Path(sys.argv[1]).rglob('sfm-command-line.txt'))
if not files:
    raise SystemExit('No SfM command files. Run the camera calibration command once to export images first.')
for path in files:
    commands = {}
    for line in path.read_text().splitlines():
        if line.startswith('colmap '):
            args = shlex.split(line)
            commands[args[1]] = args
    for op in ('feature_extractor', 'matches_importer', 'mapper', 'model_converter'):
        args = commands[op]
        if op == 'feature_extractor':
            args += ['--SiftExtraction.use_gpu', '0', '--SiftExtraction.num_threads', '2']
        elif op == 'matches_importer':
            args += ['--SiftMatching.use_gpu', '0', '--SiftMatching.num_threads', '2']
        elif op == 'mapper':
            args += ['--Mapper.num_threads', '2']
        print(shlex.join(args), flush=True)
        subprocess.run(args, check=True, env={**os.environ, 'OMP_NUM_THREADS': '2'})
    for filename in ('cameras.txt', 'images.txt', 'points3D.txt'):
        if not (path.parent / filename).is_file():
            raise SystemExit(f'Missing SfM output: {path.parent / filename}')
