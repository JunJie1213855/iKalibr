#!/usr/bin/env python3
"""Container-only viewer and non-unity build integration fixes."""
from pathlib import Path
p = Path('/opt/ikalibr_ws/src/ikalibr/src/solver/calib_solver_common_impl.cpp')
text = p.read_text()
old = 'if (!_solveFinished) {\n        pangolin::QuitAll();'
new = 'if (!_solveFinished || std::getenv("IKALIBR_AUTO_CLOSE_VIEWER") != nullptr) {\n        pangolin::QuitAll();'
if new not in text:
    assert old in text, 'Viewer shutdown code changed; inspect before patching'
    p.write_text(text.replace(old, new, 1))

# These functions are defined in feature_tracking.cpp. Non-unity builds need
# external definitions rather than inline declarations with invisible bodies.
p = Path('/opt/ikalibr_ws/src/ikalibr/include/core/feature_tracking.h')
text = p.read_text()
original = text
for name in ('Raw', 'Undistorted'):
    text = text.replace(f'inline Eigen::Vector2f {name}() const;', f'Eigen::Vector2f {name}() const;')
if text != original:
    p.write_text(text)

includes = {
    'src/solver/calib_solver_common_impl.cpp': ['<cstdlib>'],
    'src/sensor/event_data_loader.cpp': ['util/status.hpp'],
    'src/viewer/visual_colorized_cloud_map.cpp': ['core/visual_distortion.h'],
    'src/viewer/visual_gravity.cpp': ['core/visual_distortion.h'],
    'src/viewer/visual_lin_vel_drawer.cpp': ['core/visual_distortion.h'],
    'src/core/optical_flow_trace.cpp': ['core/visual_distortion.h'],
    'src/core/visual_distortion.cpp': [
        'util/status.hpp', 'opencv2/calib3d.hpp',
        'veta/camera/pinhole_brown.h', 'veta/camera/pinhole_fisheye.h'],
    'src/solver/calib_solver_init_prep_ei_align_circle_based_impl.cpp': ['opencv2/highgui.hpp'],
    'src/solver/calib_solver_init_prep_ei_align_line_based_impl.cpp': [
        'opencv2/highgui.hpp', 'core/event_preprocessing.h', 'factor/data_correspondence.h'],
    'src/solver/calib_solver_init_prep_ei_align_impl.cpp': [
        'opencv2/highgui.hpp', 'core/haste_data_io.h',
        'core/optical_flow_trace.h', 'core/rotation_estimator.h', 'factor/data_correspondence.h'],
}
for relative, headers in includes.items():
    p = Path('/opt/ikalibr_ws/src/ikalibr') / relative
    text = p.read_text()
    original = text
    # Migrate earlier patches too: the runtime attribution check reads the first
    # eleven lines. Keep the complete original notice at the beginning.
    leading = []
    while text.startswith('#include '):
        line, _, text = text.partition('\n')
        leading.append(line + '\n')
    assert text.startswith('// iKalibr:'), f'Unexpected file header: {p}'
    desired = leading + [f'#include {header}\n' if header.startswith('<')
                         else f'#include "{header}"\n' for header in headers]
    missing = []
    for directive in desired:
        if directive not in text and directive not in missing:
            missing.append(directive)
    index = text.index('#include ')
    text = text[:index] + ''.join(missing) + text[index:]
    if text != original:
        p.write_text(text)
