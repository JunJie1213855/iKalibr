#!/usr/bin/env python3
"""Prepare configurations only; never invokes a calibration program."""
import copy
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'docker/calib-configs'
IN_IMAGE = '/opt/ikalibr_ws/src/ikalibr'
TEMPLATE = yaml.safe_load((ROOT / 'config/ikalibr-config.yaml').read_text())['Configor']


def load(path):
    old = yaml.safe_load((ROOT / path).read_text())['Configor']
    cfg = copy.deepcopy(TEMPLATE)
    for group in ('DataStream', 'Prior', 'Preference'):
        cfg[group].update(old.get(group, {}))
    for key in ('IMUTopics', 'RadarTopics', 'LiDARTopics', 'CameraTopics', 'RGBDTopics'):
        cfg['DataStream'][key] = old['DataStream'].get(key) or []
    cfg['Prior']['MapDownSample'] = 0.1
    cfg['Preference'].update(UseCudaInSolving=False, ThreadsToUse=4,
                             Outputs=['BSplines', 'AlignedInertialMes'], OutputDataFormat='YAML')
    return cfg


def save(name, cfg, bag):
    cfg['DataStream']['BagPath'] = '/datasets/' + bag
    cfg['DataStream']['OutputPath'] = '/results/' + name
    for item in cfg['DataStream']['CameraTopics']:
        item['value']['ScaleSplineType'] = 'LIN_POS_SPLINE'
    text = yaml.safe_dump({'Configor': cfg}, sort_keys=False)
    text = text.replace('/home/csl/ros_ws/iKalibr/src/ikalibr', IN_IMAGE)
    (DEST / (name + '.yaml')).write_text(text)


DEST.mkdir(parents=True, exist_ok=True)
for seq in ('Court-01', 'Court-02', 'Court-03', 'Garage-01'):
    cfg = load(f'data/li-calib/{seq}/config-real.yaml')
    cfg['Prior']['SpatTempPrioriPath'] = ''
    save('li-' + seq.lower(), cfg, f'LI-CALIB/{seq}.bag')

for name, seq, bag in (
    ('ikalibr-data', '2024-06-25-16-42-32', 'ikalibr-data.bag'),
    ('ikalibr-data-1', '2024-06-25-14-52-11', 'ikalibr-data-1.bag'),
):
    cfg = load(f'data/real-world/iKalibr-data-{seq}/config-real.yaml')
    # The bag's own readme explicitly rules out radar_1 for the 16:42 recording.
    if name == 'ikalibr-data':
        cfg['DataStream']['RadarTopics'] = [i for i in cfg['DataStream']['RadarTopics'] if i['key'].endswith('radar_0')]
    # The datatype is RadarScan, but its embedded definition contains the custom
    # fields. MD5 ca47afe7b19c0dbeb8f6b51574599509 matches RadarScanCustom.
    for radar in cfg['DataStream']['RadarTopics']:
        radar['value']['Type'] = 'AWR1843BOOST_CUSTOM'
    save(name + '-full', cfg, 'ikalibr/' + bag)
    cfg['DataStream']['CameraTopics'] = []
    save(name + '-lidar-radar-imu', cfg, 'ikalibr/' + bag)

# VECtor image_mono is raw/distorted. Repository examples with zero distortion
# refer to image_mono_undistort and must not be applied to these bags.
for scale in ('small', 'large'):
    cams = yaml.safe_load((DEST / 'intrinsics' / (scale + '-cam.yaml')).read_text())
    cfg = copy.deepcopy(TEMPLATE)
    cfg['DataStream'].update(
        IMUTopics=[{'key': '/imu/data', 'value': {'Type': 'SENSOR_IMU', 'Intrinsics': IN_IMAGE + '/config/imu-intri.yaml', 'AcceWeight': 17.68, 'GyroWeight': 57.66}}],
        RadarTopics=[], LiDARTopics=[], CameraTopics=[], RGBDTopics=[], ReferIMU='/imu/data', BeginTime=1, Duration=-1)
    for key, cam in cams.items():
        intr = yaml.safe_load((ROOT / 'config/cam-intri-pinhole-brown.yaml').read_text())
        dst = intr['Intrinsics']['ptr_wrapper']['data']
        dst['img_width'], dst['img_height'] = cam['resolution']
        dst['focal_length'] = cam['intrinsics'][:2]
        dst['principal_point'] = cam['intrinsics'][2:]
        k1, k2, p1, p2 = cam['distortion_coeffs']
        dst['disto_param'] = [k1, k2, 0.0, p1, p2]
        filename = f'vector-{scale}-{key}.yaml'
        (DEST / 'intrinsics' / filename).write_text(yaml.safe_dump(intr, sort_keys=False))
        cfg['DataStream']['CameraTopics'].append({'key': cam['rostopic'], 'value': {
            'Type': 'SENSOR_IMAGE_GS', 'Intrinsics': '/configs/intrinsics/' + filename,
            'Weight': 50.0, 'TrackLengthMin': 5, 'ScaleSplineType': 'LIN_POS_SPLINE'}})
    cfg['Prior']['SpatTempPrioriPath'] = ''
    cfg['Preference'].update(UseCudaInSolving=False, ThreadsToUse=4,
                             Outputs=['BSplines', 'AlignedInertialMes'], OutputDataFormat='YAML')
    save('vector-' + scale, cfg, f'VECtor/{scale}_scale_camera_imu_extrinsic_data1.synced.bag')

print('Generated', len(list(DEST.glob('*.yaml'))), 'configurations in', DEST)
