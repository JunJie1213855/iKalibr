#!/usr/bin/env python3
"""Load library static initializers, including attribution checks; no calibration."""
import ctypes
import ctypes.util
import os
from pathlib import Path

for variable in ('ROS_HOME', 'ROS_LOG_DIR'):
    directory = Path(os.environ[variable])
    probe = directory / '.ikalibr-write-check'
    probe.write_text('ok')
    probe.unlink()
    print(variable, directory, 'writable', flush=True)

# yaml-cpp is linked by the executable rather than each individual library.
ctypes.CDLL(ctypes.util.find_library('yaml-cpp'), mode=os.RTLD_LAZY | os.RTLD_GLOBAL)
third = Path('/opt/ikalibr_ws/src/ikalibr/thirdparty')
# Match libraries normally made available by the executable's RUNPATH.
for relative in ('ctraj/thirdparty/tiny-viewer-install/lib/libtiny-viewer.so',
                 'ctraj-install/lib/libctraj.so', 'ufomap-install/lib/libMap.so',
                 'veta-install/lib/libveta.so'):
    ctypes.CDLL(str(third / relative), mode=os.RTLD_LAZY | os.RTLD_GLOBAL)
for name in ('util', 'config', 'sensor', 'viewer', 'core', 'factor', 'calib', 'solver'):
    ctypes.CDLL('/opt/ikalibr_ws/devel/lib/libikalibr_' + name + '.so',
                mode=os.RTLD_LAZY | os.RTLD_GLOBAL)
    print(name, 'static initializers OK', flush=True)
