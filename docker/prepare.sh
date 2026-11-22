#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends build-essential git ca-certificates ninja-build \
  python3-pip libgoogle-glog-dev libgflags-dev libsuitesparse-dev libeigen3-dev \
  libboost-all-dev libopencv-dev libpcl-dev libyaml-cpp-dev libcereal-dev libglew-dev \
  libepoxy-dev libgl1-mesa-dev libegl1-mesa-dev libwayland-dev libxkbcommon-dev \
  liblz4-dev libbz2-dev libssl-dev ros-noetic-velodyne xvfb xauth colmap mesa-utils
root=/opt/ikalibr_ws/src/ikalibr
mkdir -p "$root" /opt/deps
if [[ ! -f "$root/exe/solver/main.cpp" ]]; then
  tar -C /workspace/src/ikalibr --exclude=.git --exclude=thirdparty --exclude=docker -cf - . | tar -C "$root" -xf -
fi
# Upstream CTraj/veta/tiny-viewer URLs are unavailable. This public snapshot
# vendors their source; keep provenance explicit rather than changing .gitmodules.
if [[ ! -d /opt/deps/ikalibr-source-backup/.git ]]; then
  git clone https://github.com/TQK123/iKalibr-note.git /opt/deps/ikalibr-source-backup
fi
git -C /opt/deps/ikalibr-source-backup checkout d4349fa1794d6550873722240945ad9705bd162d
mkdir -p "$root/thirdparty"
for name in ctraj veta; do
  if [[ ! -f "$root/thirdparty/$name/CMakeLists.txt" ]]; then
    cp -a "/opt/deps/ikalibr-source-backup/thirdparty/$name" "$root/thirdparty/"
  fi
done
if [[ ! -f "$root/thirdparty/ufomap/ufomap/CMakeLists.txt" ]]; then
  git clone https://github.com/UnknownFreeOccupied/ufomap.git "$root/thirdparty/ufomap"
  git -C "$root/thirdparty/ufomap" checkout b9de35475d78ec9523493f7e7383cce48030ab9f
fi
if [[ ! -f "$root/thirdparty/opengv/CMakeLists.txt" ]]; then
  git clone https://github.com/laurentkneip/opengv.git "$root/thirdparty/opengv"
  git -C "$root/thirdparty/opengv" checkout 91f4b19c73450833a40e463ad3648aae80b3a7f3
fi
