#!/usr/bin/env python3
"""Keep one original point per spatial voxel; preserve IMU, headers and timestamps."""
import argparse
from pathlib import Path
import numpy as np
import rosbag


def thin(msg, voxel):
    fields = {f.name: f for f in msg.fields}
    if not all(k in fields and fields[k].datatype == 7 and fields[k].count == 1
               for k in ('x', 'y', 'z')):
        raise ValueError('Expected FLOAT32 x/y/z fields')
    endian = '>' if msg.is_bigendian else '<'
    dtype = np.dtype({'names': ['x', 'y', 'z'],
                      'formats': [endian + 'f4'] * 3,
                      'offsets': [fields[k].offset for k in ('x', 'y', 'z')],
                      'itemsize': msg.point_step})
    array = np.ndarray((msg.height, msg.width), dtype=dtype, buffer=msg.data,
                       strides=(msg.row_step, msg.point_step)).reshape(-1)
    xyz = np.column_stack([array[k] for k in ('x', 'y', 'z')])
    valid = np.flatnonzero(np.isfinite(xyz).all(axis=1))
    cells = np.floor(xyz[valid].astype(np.float64) / voxel).astype(np.int64)
    _, first = np.unique(cells, axis=0, return_index=True)
    indices = np.sort(valid[first])
    # Copy complete records, including ring, intensity and the exact timestamp.
    records = array.view(np.dtype('V' + str(msg.point_step)))
    before = len(array)
    msg.data = records[indices].tobytes()
    msg.height, msg.width = 1, len(indices)
    msg.row_step = msg.width * msg.point_step
    msg.is_dense = True
    return before, len(indices)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('destination', type=Path)
    p.add_argument('--topic', default='/rslidar_points')
    p.add_argument('--voxel', type=float, default=0.1)
    args = p.parse_args()
    if not np.isfinite(args.voxel) or args.voxel <= 0:
        p.error('voxel must be finite and positive')
    if args.destination.exists() or args.source.resolve() == args.destination.resolve():
        p.error('destination must be a new file')
    temporary = args.destination.with_name(args.destination.name + '.partial')
    if temporary.exists():
        p.error('partial output already exists; inspect it before retrying')
    scans = input_points = output_points = 0
    try:
        with rosbag.Bag(str(args.source)) as source, rosbag.Bag(str(temporary), 'w') as dest:
            for topic, msg, stamp in source.read_messages():
                if topic == args.topic:
                    if msg._type != 'sensor_msgs/PointCloud2':
                        raise ValueError('Target topic must be PointCloud2')
                    before, after = thin(msg, args.voxel)
                    scans += 1
                    input_points += before
                    output_points += after
                    if scans % 100 == 0:
                        print(f'{scans} scans; kept {output_points}/{input_points} points', flush=True)
                dest.write(topic, msg, stamp)
        if not scans:
            raise ValueError('No scans found on target topic')
        temporary.rename(args.destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    print(f'Wrote {args.destination}: {scans} scans, {output_points}/{input_points} points', flush=True)


if __name__ == '__main__':
    main()
