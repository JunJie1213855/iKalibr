#!/usr/bin/env bash
# No image pulls. All compilation runs inside one resource-limited container.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
image=${IKALIBR_IMAGE:-ikalibr:noetic-local}
container=${IKALIBR_BUILDER:-ikalibr-noetic-builder}
base=osrf/ros:noetic-desktop-full
docker image inspect "$base" >/dev/null
if ! docker container inspect "$container" >/dev/null 2>&1; then
  docker run -d --pull=never --name "$container" --cpus=2 --memory=6g --memory-swap=6g \
    --pids-limit=512 -v "$root:/workspace/src/ikalibr:ro" "$base" sleep infinity
fi
# Refuse to reuse an unrelated or unconstrained container.
docker inspect "$container" | python3 -c '
import json,sys
c=json.load(sys.stdin)[0]; h=c["HostConfig"]
assert c["Config"]["Image"]=="osrf/ros:noetic-desktop-full", "Unexpected base image"
assert h["NanoCpus"]==2000000000 and h["Memory"]==6*1024**3 and h["MemorySwap"]==h["Memory"], "Unexpected resource limits"
'
docker start "$container" >/dev/null
mkdir -p "$root/docker/logs"
docker exec "$container" bash /workspace/src/ikalibr/docker/prepare.sh 2>&1 | tee "$root/docker/logs/prepare.log"
docker cp "$root/docker/compile.sh" "$container:/opt/ikalibr-compile.sh"
docker exec "$container" nice -n 10 bash /opt/ikalibr-compile.sh 2>&1 | tee "$root/docker/logs/build.log"
docker exec "$container" bash -c 'cp /workspace/src/ikalibr/docker/entrypoint.sh /usr/local/bin/ikalibr-entrypoint; chmod +x /usr/local/bin/ikalibr-entrypoint; ldconfig; test -x /opt/ikalibr_ws/devel/lib/ikalibr/ikalibr_prog'
docker exec "$container" mkdir -p /opt/ikalibr-build-scripts
tar -C "$root/docker" --exclude=logs --exclude=__pycache__ -cf - . | docker exec -i "$container" tar -C /opt/ikalibr-build-scripts -xf -
docker stop "$container" >/dev/null
docker commit --change 'ENTRYPOINT ["/usr/local/bin/ikalibr-entrypoint"]' \
  --change 'CMD ["bash"]' --change 'WORKDIR /opt/ikalibr_ws' \
  --change 'ENV OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 CMAKE_BUILD_PARALLEL_LEVEL=2 MAKEFLAGS=-j2' \
  "$container" "$image"
docker run --rm --pull=never --cpus=2 --memory=1g --memory-swap=1g "$image" \
  bash -c 'set -e; python3 /opt/ikalibr-build-scripts/check-startup.py; rospack find ikalibr; for binary in /opt/ikalibr_ws/devel/lib/ikalibr/*; do ldd -r "$binary"; done; colmap help' \
  > "$root/docker/logs/image-check.log" 2>&1
if rg -q 'not found|undefined symbol' "$root/docker/logs/image-check.log"; then
  cat "$root/docker/logs/image-check.log"; exit 1
fi
echo "Image ready: $image"
