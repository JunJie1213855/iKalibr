#!/usr/bin/env bash
# Explicit user invocation only; this script is never called by the build.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
image=${IKALIBR_IMAGE:-ikalibr:noetic-local}
datasets=${IKALIBR_DATASETS:-/home/ros/dataset/calib}
results=${IKALIBR_RESULTS:-/home/ros/dataset/calib/ikalibr-results}
mode=${1:-help}
name=${2:-}

if [[ "$mode" == help || -z "$name" ]]; then
  echo "Usage: $0 {calibrate|calibrate-gui|sfm|shell} CONFIG_NAME"
  echo 'Configurations:'
  find "$root/docker/calib-configs" -maxdepth 1 -name '*.yaml' -printf '  %f\n' | sort
  exit 0
fi

[[ "$name" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid config name' >&2; exit 1; }
[[ -f "$root/docker/calib-configs/$name.yaml" ]] || { echo 'Config does not exist' >&2; exit 1; }

docker image inspect "$image" >/dev/null

mkdir -p "$results/$name"

args=(--rm --pull=never --init --cpus=4 --memory=12g --memory-swap=12g --pids-limit=512
  --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=4 -e OPENBLAS_NUM_THREADS=1
  -e "ROS_LOG_DIR=/results/$name/ros-log"
  -e LIBGL_ALWAYS_SOFTWARE=1
  -v "$datasets:/datasets:ro" -v "$results:/results:rw"
  -v "$root/docker/calib-configs:/configs:ro" -v "$root/docker:/helpers:ro")

if [[ "$mode" == calibrate-gui ]]; then
  [[ -n "${DISPLAY:-}" ]] || { echo 'DISPLAY is unset. Run calibrate-gui from a terminal in your desktop session.' >&2; exit 1; }
  [[ -d /tmp/.X11-unix ]] || { echo 'Local X11/XWayland socket is unavailable.' >&2; exit 1; }
  command -v xauth >/dev/null || { echo 'Host xauth command is required.' >&2; exit 1; }
  auth_dir=$(mktemp -d /tmp/ikalibr-xauth.XXXXXX)
  trap 'rm -rf "$auth_dir"' EXIT
  auth_entries=$(xauth nlist "$DISPLAY")
  [[ -n "$auth_entries" ]] || { echo 'No X11 cookie found for DISPLAY; check XAUTHORITY in your desktop terminal.' >&2; exit 1; }
  touch "$auth_dir/Xauthority"
  chmod 600 "$auth_dir/Xauthority"
  # FamilyWild lets the local desktop cookie work with the container hostname.
  printf '%s\n' "$auth_entries" | sed 's/^..../ffff/' | xauth -f "$auth_dir/Xauthority" nmerge -
  args+=(-e "DISPLAY=$DISPLAY" -e XAUTHORITY=/tmp/ikalibr.Xauthority
    -e QT_QPA_PLATFORM=xcb -e QT_X11_NO_MITSHM=1
    -v /tmp/.X11-unix:/tmp/.X11-unix:ro
    -v "$auth_dir/Xauthority:/tmp/ikalibr.Xauthority:ro")
else
  args+=(-e IKALIBR_AUTO_CLOSE_VIEWER=1 -e QT_QPA_PLATFORM=offscreen)
fi

case "$mode" in
  calibrate|calibrate-gui)
    # The upstream binary catches exceptions and returns 0; inspect its log and
    # completion marker instead of treating the exit code alone as success.
    docker run "${args[@]}" "$image" bash -c '
      set -o pipefail
      log="/results/$1/run-$(date +%Y%m%d-%H%M%S).log"
      if [[ "$2" == calibrate-gui ]]; then
        roslaunch /helpers/ikalibr-batch.launch config_path:="/configs/$1.yaml" 2>&1 | tee "$log"
      else
        xvfb-run -a -s "-screen 0 1280x1024x24" roslaunch /helpers/ikalibr-batch.launch config_path:="/configs/$1.yaml" 2>&1 | tee "$log"
      fi
      grep -q "solving and outputting finished" "$log" && test -s "/results/$1/ikalibr_param.yaml"
    ' bash "$name" "$mode"
    ;;
  sfm)
    docker run "${args[@]}" "$image" python3 /helpers/run-sfm.py "/results/$name"
    ;;
  shell)
    docker run -it "${args[@]}" "$image" bash
    ;;
  *) echo "Unknown mode: $mode" >&2; exit 1 ;;
esac
