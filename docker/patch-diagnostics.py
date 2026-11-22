#!/usr/bin/env python3
"""Add initialization diagnostics; leave numerical behavior and checks intact."""
from pathlib import Path

root = Path('/opt/ikalibr_ws/src/ikalibr/src/core')


def patch(name, anchor, replacement, marker):
    path = root / name
    text = path.read_text()
    if marker in text:
        return
    assert text.count(anchor) == 1, (name, 'Inspect upstream changes before patching')
    text = text.replace(anchor, replacement)
    if '#include "spdlog/spdlog.h"' not in text:
        idx = text.index('#include ')
        text = text[:idx] + '#include "spdlog/spdlog.h"\n' + text[idx:]
    path.write_text(text)


patch('rotation_estimator.cpp', '    if (cov(2) > 0.25) {', '''    spdlog::info("[INIT-DIAG] rotation pairs={}, singular values=[{:.6f}, {:.6f}, {:.6f}, {:.6f}], required third > 0.25",
                 AMatSeq.size(), cov(0), cov(1), cov(2), cov(3));
    if (cov(2) > 0.25) {''', '[INIT-DIAG] rotation pairs=')

patch('lidar_odometer.cpp', '        curLtoM = ns_ctraj::Posed::FromT(pose, frame->GetTimestamp());', '''        curLtoM = ns_ctraj::Posed::FromT(pose, frame->GetTimestamp());
        if (_frames.size() % 25 == 0 || !_ndt->hasConverged()) {
            const auto delta = _poseSeq.back().so3.inverse() * curLtoM.so3;
            spdlog::info("[INIT-DIAG] NDT frame={}, converged={}, source points={}, map points={}, fitness={:.6f}, step angle={:.4f} deg, step translation={:.4f} m",
                         _frames.size(), _ndt->hasConverged(), filterCloud->size(), _map->size(),
                         _ndt->getFitnessScore(), delta.log().norm() * 180.0 / 3.141592653589793,
                         (curLtoM.t - _poseSeq.back().t).norm());
        }''', '[INIT-DIAG] NDT frame=')
