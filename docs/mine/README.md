# iKalibr 本机部署与标定记录

更新日期：2026-11-22。项目目录：`/home/ros/lib/iKalibr`。

本文档记录本机已经完成的 Docker 部署、标定操作和故障处理，以实际脚本、配置、内核记录和结果文件为依据。

## 阅读入口

| 文档 | 内容 |
| --- | --- |
| [Docker 构建与维护](/home/ros/lib/iKalibr/docs/mine/docker-build.md) | 现有 Noetic 镜像、资源限制、依赖恢复、源码补丁和构建命令 |
| [标定命令与可视化](/home/ros/lib/iKalibr/docs/mine/calibration.md) | Robosense 成功流程、其他数据集、GUI、输出目录及最终参数含义 |
| [故障排查与内存问题](/home/ros/lib/iKalibr/docs/mine/troubleshooting.md) | 旋转初始化失败、6/12 GiB OOM、点云降采样、版权检查和日志目录问题 |

## 当前可用状态

- 运行环境：Docker 内 ROS1 Noetic；项目使用 catkin、roscpp 和 rosbag。
- 本地镜像：`ikalibr:noetic-local`。基础镜像使用本机已有的 `osrf/ros:noetic-desktop-full`；不拉取 Docker 镜像。
- 构建限制：容器 2 CPU / 6 GiB；依赖最多 2 线程，主程序 1 线程。
- 当前运行限制：4 CPU / 12 GiB，求解线程 4，不额外使用容器 swap。这是上限，不是内存预留。
- 已确认完成：LI-CALIB Court-01；Robosense `mapping.bag` 的降采样副本、20–75 秒 LiDAR–IMU 标定。
- Robosense 成功日志：`/home/ros/dataset/robosense/ikalibr-results/robosense-mapping-lowmem/run-20261122-095625.log`。
- Robosense 最终参数：`/home/ros/dataset/robosense/ikalibr-results/robosense-mapping-lowmem/ikalibr_param.yaml`。

完成标定以日志中的 `solving and outputting finished!!! Everything is fine!!!` 和最终参数文件为依据。初始化阶段打印的参数不能当作最终结果；程序跑完也不等于已完成独立精度验证。

## Robosense 日常运行命令

降采样副本已经存在时，直接执行：

```bash
cd /home/ros/lib/iKalibr

IKALIBR_DATASETS=/home/ros/dataset/robosense \
IKALIBR_RESULTS=/home/ros/dataset/robosense/ikalibr-results \
./docker/run.sh calibrate-gui robosense-mapping-lowmem
```

启动后必须看到：

```text
DataStream::BagPath: /datasets/mapping-voxel10cm.bag
DataStream::BeginTime: 20
DataStream::Duration: 55
DataStream::OutputPath: /results/robosense-mapping-lowmem
```

如果显示 `/datasets/mapping.bag` 或输出目录仍是 `robosense-mapping-extended`，说明还在使用原始数据配置。该配置曾在点面关联阶段耗尽内存。

标定命令由用户自行执行，构建和文档整理不自动触发标定。
