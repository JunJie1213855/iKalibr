#!/usr/bin/env python3
"""Read-only checks of paths, bag topics, and custom message MD5s; no solving."""
from pathlib import Path
import rosbag
import roslib.message
import yaml

cache = {}
for path in sorted(Path('/configs').glob('*.yaml')):
    cfg = yaml.safe_load(path.read_text())['Configor']
    data = cfg['DataStream']
    bagpath = data['BagPath']
    if bagpath not in cache:
        with rosbag.Bag(bagpath) as bag:
            _, topics = bag.get_type_and_topic_info()
            md5 = {c.topic: c.md5sum for c in bag._get_connections()}
            cache[bagpath] = topics, md5, bag.get_end_time() - bag.get_start_time()
    topics, md5, duration = cache[bagpath]
    assert data['BeginTime'] < duration, (path, 'begin outside bag')
    if data['Duration'] > 0:
        assert max(0, data['BeginTime']) + data['Duration'] <= duration + 0.1, (path, 'duration outside bag')
    for key in ('IMUTopics', 'LiDARTopics', 'RadarTopics', 'CameraTopics', 'RGBDTopics'):
        for item in data[key]:
            topic, value = item['key'], item['value']
            assert topic in topics, (path, 'missing topic', topic)
            if 'Intrinsics' in value:
                assert Path(value['Intrinsics']).is_file(), (path, value['Intrinsics'])
            local_msg = {'AWR1843BOOST_RAW': 'ikalibr/AWR1843RadarScan',
                         'AWR1843BOOST_CUSTOM': 'ikalibr/AWR1843RadarScanCustom',
                         'LIVOX_CUSTOM': 'ikalibr/LivoxCustomMsg'}.get(value['Type'])
            if local_msg:
                cls = roslib.message.get_message_class(local_msg)
                assert cls is not None and cls._md5sum == md5[topic], (path, local_msg, md5[topic])
    prior = cfg['Prior']['SpatTempPrioriPath']
    assert not prior or Path(prior).is_file(), (path, prior)
    assert cfg['Preference']['ThreadsToUse'] == 4
    print(path.name, 'OK', flush=True)
