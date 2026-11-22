#!/usr/bin/env bash
set -euo pipefail
export CMAKE_BUILD_PARALLEL_LEVEL=2 MAKEFLAGS=-j2 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
python3 /workspace/src/ikalibr/docker/patch-container.py
python3 /workspace/src/ikalibr/docker/patch-viewer.py
python3 /workspace/src/ikalibr/docker/patch-diagnostics.py
mkdir -p /opt/deps
fetch() {
  local name=$1 url=$2 ref=$3
  if [[ ! -d /opt/deps/$name/.git ]]; then
    git clone --depth 1 --branch "$ref" "$url" "/opt/deps/$name"
  fi
}
build() {
  local name=$1; shift
  cmake -S "/opt/deps/$name" -B "/opt/deps/$name-build" -DCMAKE_BUILD_TYPE=Release "$@"
  cmake --build "/opt/deps/$name-build" --parallel 2
  cmake --install "/opt/deps/$name-build"
}
fetch eigen https://gitlab.com/libeigen/eigen.git 3.4.0
cmake -S /opt/deps/eigen -B /opt/deps/eigen-build -DBUILD_TESTING=OFF
cmake --install /opt/deps/eigen-build
fetch ceres https://github.com/ceres-solver/ceres-solver.git 2.2.0
build ceres -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF -DBUILD_BENCHMARKS=OFF -DUSE_CUDA=OFF -DBUILD_SHARED_LIBS=ON
fetch sophus https://github.com/strasdat/Sophus.git 1.22.10
build sophus -DSOPHUS_USE_BASIC_LOGGING=ON -DBUILD_SOPHUS_TESTS=OFF -DBUILD_SOPHUS_EXAMPLES=OFF
fetch spdlog https://github.com/gabime/spdlog.git v1.12.0
build spdlog -DSPDLOG_BUILD_SHARED=ON -DSPDLOG_BUILD_EXAMPLE=OFF
fetch magic_enum https://github.com/Neargye/magic_enum.git v0.9.6
build magic_enum -DMAGIC_ENUM_OPT_BUILD_EXAMPLES=OFF -DMAGIC_ENUM_OPT_BUILD_TESTS=OFF
fetch pangolin https://github.com/stevenlovegrove/Pangolin.git v0.8
build pangolin -DBUILD_EXAMPLES=OFF -DBUILD_TOOLS=OFF -DBUILD_PANGOLIN_PYTHON=OFF -DBUILD_PANGOLIN_VIDEO=OFF

root=/opt/ikalibr_ws/src/ikalibr
third=$root/thirdparty
cmake -S "$third/ctraj/thirdparty/tiny-viewer" -B "$third/tiny-viewer-build" -DCMAKE_INSTALL_PREFIX="$third/ctraj/thirdparty/tiny-viewer-install"
cmake --build "$third/tiny-viewer-build" --target tiny-viewer --parallel 2
cmake --install "$third/tiny-viewer-build"
cmake -S "$third/ctraj" -B "$third/ctraj-build" -DCMAKE_INSTALL_PREFIX="$third/ctraj-install"
cmake --build "$third/ctraj-build" --target ctraj --parallel 2
cmake --install "$third/ctraj-build"
cmake -S "$third/ufomap/ufomap" -B "$third/ufomap-build" -DCMAKE_INSTALL_PREFIX="$third/ufomap-install"
cmake --build "$third/ufomap-build" --parallel 2
cmake --install "$third/ufomap-build"
cmake -S "$third/veta" -B "$third/veta-build" -DCMAKE_INSTALL_PREFIX="$third/veta-install"
cmake --build "$third/veta-build" --target veta --parallel 2
cmake --install "$third/veta-build"
cmake -S "$third/opengv" -B "$third/opengv-build" -DCMAKE_INSTALL_PREFIX="$third/opengv-install" -DBUILD_TESTS=OFF
cmake --build "$third/opengv-build" --parallel 2
cmake --install "$third/opengv-build"
set +u
source /opt/ros/noetic/setup.bash
set -u
cd /opt/ikalibr_ws
catkin_make ikalibr_generate_messages -j2 -l2 -DPYTHON_EXECUTABLE=/usr/bin/python3 -DUSE_CMAKE_UNITY_BUILD=OFF
# iKalibr's template-heavy translation units can exceed 3 GiB each. Build the
# application serially inside the 6 GiB limit; dependencies above use at most 2.
catkin_make -j1 -l1 -DPYTHON_EXECUTABLE=/usr/bin/python3 -DUSE_CMAKE_UNITY_BUILD=OFF
ldconfig
