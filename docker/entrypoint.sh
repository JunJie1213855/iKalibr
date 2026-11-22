#!/usr/bin/env bash
set -e
export ROS_HOME=${ROS_HOME:-/tmp/ikalibr-ros-$(id -u)}
export ROS_LOG_DIR=${ROS_LOG_DIR:-$ROS_HOME/log}
mkdir -p "$ROS_HOME" "$ROS_LOG_DIR"
if [[ ! -w "$ROS_HOME" || ! -w "$ROS_LOG_DIR" ]]; then
  echo "ROS directories are not writable: $ROS_HOME, $ROS_LOG_DIR" >&2
  exit 1
fi
source /opt/ros/noetic/setup.bash
source /opt/ikalibr_ws/devel/setup.bash
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-2}
export OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-1}
exec "$@"
