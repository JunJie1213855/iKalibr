#!/usr/bin/env python3
"""Plot saved LiDAR/IMU calibration results without running calibration."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml


def read_yaml(path):
    with path.open() as stream:
        return yaml.load(stream, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))


def vector(value):
    return [value[f"r{i}c0"] for i in range(3)]


def rotation(q):
    x, y, z, w = np.array([q[k] for k in ("qx", "qy", "qz", "qw")], dtype=float)
    norm = np.linalg.norm([x, y, z, w])
    x, y, z, w = np.array([x, y, z, w]) / norm
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def equal_axes(ax, points, padding=0.1):
    center = (points.min(axis=0) + points.max(axis=0)) / 2
    radius = max(np.ptp(points, axis=0).max() * (0.5 + padding), 0.05)
    for setter, mid in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim), center):
        setter(mid-radius, mid+radius)
    ax.set_box_aspect((1, 1, 1))
    ax.set(xlabel="X (m)", ylabel="Y (m)", zlabel="Z (m)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_dir", type=Path)
    args = parser.parse_args()
    root = args.result_dir.resolve()
    params = read_yaml(root / "ikalibr_param.yaml")["CalibParam"]
    # For configurations integrating LiDAR, the saved scale spline is position.
    if not params["EXTRI"].get("POS_LkInBr"):
        parser.error("This plotter expects LiDAR results with a position spline.")
    out = root / "visualizations"
    out.mkdir(exist_ok=True)
    poses = read_yaml(root / "splines/samples.yaml")["pose_seq"]
    time = np.array([p["timeStamp"] for p in poses])
    time -= time[0]
    xyz = np.array([vector(p["t"]) for p in poses])
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False})
    fig = plt.figure(figsize=(12, 5), layout="constrained")
    ax = fig.add_subplot(121, projection="3d")
    ax.plot(*xyz.T, color="#2563eb", linewidth=1)
    ax.scatter(*xyz[0], color="#16a34a", label="Start", s=35)
    ax.scatter(*xyz[-1], color="#dc2626", label="End", s=35)
    equal_axes(ax, xyz)
    ax.legend()
    ax.set_title("Reference IMU trajectory (spline frame)")
    ax = fig.add_subplot(122)
    for i, label in enumerate("XYZ"):
        ax.plot(time, xyz[:, i], label=label, linewidth=1)
    ax.set(xlabel="Time since first sample (s)", ylabel="Position (m)",
           title="Spline position components")
    ax.grid(alpha=0.2)
    ax.legend()
    fig.savefig(out / "trajectory.png", dpi=180)
    plt.close(fig)

    fig = plt.figure(figsize=(8, 7), layout="constrained")
    ax = fig.add_subplot(111, projection="3d")
    extr = params["EXTRI"]
    origins, endpoints = [], []
    axis_length = 0.045
    for suffix in ("Bi", "Lk", "Rj", "Cm", "Dn", "Es"):
        rotations = {p["key"]: rotation(p["value"])
                     for p in extr.get(f"SO3_{suffix}ToBr", [])}
        for entry in extr.get(f"POS_{suffix}InBr", []):
            origin = np.array(vector(entry["value"]))
            origins.append(origin)
            ax.scatter(*origin, color="#334155", s=25)
            ax.text(*(origin + 0.008), entry["key"], fontsize=9)
            for axis, color in zip(rotations[entry["key"]].T, ("#dc2626", "#16a34a", "#2563eb")):
                delta = axis_length * axis
                endpoints.append(origin + delta)
                ax.quiver(*origin, *delta, color=color, arrow_length_ratio=0.2)
    equal_axes(ax, np.array(origins + endpoints), padding=0.25)
    ax.set_title("Sensor extrinsics in reference IMU frame\nRed: local X  |  Green: local Y  |  Blue: local Z")
    fig.savefig(out / "sensor_extrinsics.png", dpi=180)
    plt.close(fig)
    for path in sorted(out.glob("*.png")):
        print(path)


if __name__ == "__main__":
    main()
